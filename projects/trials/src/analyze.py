"""Build SQLite and a deterministic summary from the captured registry snapshot."""

from __future__ import annotations

import argparse
from calendar import monthrange
from collections import Counter
from dataclasses import dataclass
from datetime import date
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from registry import COHORTS, DEFAULT_SNAPSHOT, FIRST_YEAR, LAST_YEAR, write_bytes

ROOT = Path(__file__).resolve().parents[1]
WINDOW_DAYS = 365
NCT_ID = re.compile(r"NCT[0-9]{8}")
REGISTRY_DATE = re.compile(r"([0-9]{4})(?:-([0-9]{2})(?:-([0-9]{2}))?)?")
COUNTS = """
    COUNT(*) AS count,
    COUNT(*) FILTER (WHERE overall_status = 'COMPLETED') AS completed,
    COUNT(*) FILTER (WHERE overall_status = 'TERMINATED') AS terminated,
    COUNT(*) FILTER (WHERE overall_status = 'WITHDRAWN') AS withdrawn,
    COUNT(*) FILTER (WHERE overall_status NOT IN ('COMPLETED', 'TERMINATED', 'WITHDRAWN')) AS other,
    COUNT(*) FILTER (WHERE timing != 'not_eligible') AS eligible,
    COUNT(*) FILTER (WHERE timing != 'not_eligible' AND has_results = 1) AS posted,
    COUNT(*) FILTER (WHERE timing = 'within_365') AS posted_365,
    COUNT(*) FILTER (WHERE timing = 'after_365') AS after_365,
    COUNT(*) FILTER (WHERE timing = 'not_posted') AS not_posted,
    COUNT(*) FILTER (WHERE timing = 'unknown') AS unknown_timing
"""


@dataclass(frozen=True)
class DateInterval:
    earliest: date
    latest: date


def date_interval(value):
    """Interpret registry day, month, and year precision as closed intervals."""
    match = REGISTRY_DATE.fullmatch(value or "")
    if match is None:
        raise ValueError(f"Invalid registry date: {value!r}")
    year, month, day = (int(part) if part else None for part in match.groups())
    if day is not None:
        exact = date(year, month, day)
        return DateInterval(exact, exact)
    if month is not None:
        return DateInterval(date(year, month, 1), date(year, month, monthrange(year, month)[1]))
    return DateInterval(date(year, 1, 1), date(year, 12, 31))


def posting_timing(completion, posted, has_results, as_of):
    if not has_results and not posted.get("date"):
        return "not_posted", "no_registry_results"
    if not has_results:
        return "unknown", "posting_flag_disagrees_with_date"
    if posted.get("type") != "ACTUAL":
        return "unknown", "missing_or_nonactual_posting_date"
    try:
        publication = date_interval(posted.get("date"))
    except ValueError:
        return "unknown", "missing_or_invalid_posting_date"
    if publication.earliest > as_of:
        return "unknown", "posting_date_after_snapshot"
    if publication.latest < completion.earliest:
        return "unknown", "posting_date_before_primary_completion"
    minimum = (publication.earliest - completion.latest).days
    maximum = (min(publication.latest, as_of) - completion.earliest).days
    if minimum < 0:
        return "unknown", "date_precision_overlaps_primary_completion"
    if maximum <= WINDOW_DAYS:
        return "within_365", "interval_within_window"
    if minimum > WINDOW_DAYS:
        return "after_365", "interval_after_window"
    return "unknown", "date_precision_crosses_window"


def normalized_study(nct_id, record, as_of):
    protocol = record["protocolSection"]
    status = protocol["statusModule"]
    if not NCT_ID.fullmatch(nct_id) or protocol["identificationModule"]["nctId"] != nct_id:
        raise ValueError(f"Invalid or inconsistent NCT ID: {nct_id}")
    design = protocol.get("designModule", {})
    if design.get("studyType") != "INTERVENTIONAL":
        return None, "not_interventional"
    completion = status.get("primaryCompletionDateStruct", {})
    if completion.get("type") != "ACTUAL":
        return None, "missing_or_estimated_primary_completion"
    try:
        interval = date_interval(completion.get("date"))
    except ValueError:
        return None, "invalid_primary_completion_date"
    if interval.earliest.year < FIRST_YEAR or interval.latest.year > LAST_YEAR:
        return None, "primary_completion_outside_cohort"
    if (as_of - interval.latest).days < WINDOW_DAYS:
        raise ValueError("Snapshot gives less than 365 days of follow-up for the date cohort")
    raw_has_results = record.get("hasResults")
    if not isinstance(raw_has_results, bool):
        raise ValueError(f"Missing or invalid hasResults flag for {nct_id}")
    overall_status = status.get("overallStatus", "UNKNOWN")
    sponsor = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("class", "UNKNOWN")
    posted = status.get("resultsFirstPostDateStruct", {})
    timing, detail = (
        posting_timing(interval, posted, raw_has_results, as_of)
        if overall_status == "COMPLETED"
        else ("not_eligible", "registry_status_not_completed")
    )
    return (
        nct_id, overall_status, sponsor, ",".join(sorted(set(design.get("phases", [])))),
        completion["date"], interval.earliest.year, int(raw_has_results), posted.get("date"), timing, detail,
    ), None


def load_snapshot(path):
    compressed = path.read_bytes()
    checksum = hashlib.sha256(compressed).hexdigest()
    expected = path.with_suffix(path.suffix + ".sha256").read_text().strip()
    if checksum != expected:
        raise ValueError(f"Snapshot SHA-256 mismatch: {path}")
    snapshot = json.loads(gzip.decompress(compressed))
    if snapshot["schema_version"] != 1 or set(snapshot["cohorts"]) != set(COHORTS):
        raise ValueError("Unsupported snapshot schema or cohort definitions")
    return snapshot, checksum


def ingest(connection, snapshot, checksum):
    connection.executescript((ROOT / "src/schema.sql").read_text())
    as_of = date.fromisoformat(snapshot["source_version"]["dataTimestamp"][:10])
    for key, value in (
        ("source", snapshot["source"]),
        ("source_version", snapshot["source_version"]),
        ("capture", snapshot["captured_at_utc"]),
        ("snapshot_sha256", checksum),
        ("cohort_filter", snapshot["filter"]),
        ("fields", snapshot["fields"]),
    ):
        connection.execute("INSERT INTO metadata VALUES (?, ?)", (key, json.dumps(value, sort_keys=True)))
    selected = set()
    exclusions = Counter()
    for nct_id, record in sorted(snapshot["studies"].items()):
        row, issue = normalized_study(nct_id, record, as_of)
        if issue:
            exclusions[issue] += 1
            continue
        connection.execute("INSERT INTO study VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
        selected.add(nct_id)
    observed = set()
    for cohort_id, label in COHORTS.items():
        group = snapshot["cohorts"][cohort_id]
        group_ids = set(group["ids"])
        if group["term"] != label or len(group_ids) != group["api_matches"] or len(group_ids) != len(group["ids"]):
            raise ValueError(f"Inconsistent cohort metadata: {cohort_id}")
        observed.update(group_ids)
        connection.execute("INSERT INTO cohort VALUES (?, ?, ?)", (cohort_id, label, group["api_matches"]))
        connection.executemany(
            "INSERT INTO membership VALUES (?, ?)",
            ((cohort_id, nct_id) for nct_id in sorted(group_ids & selected)),
        )
    if observed != set(snapshot["studies"]):
        raise ValueError("Inconsistent source study set and search memberships")
    return as_of, exclusions


def metrics(row):
    result = dict(row)
    denominator = result["eligible"]
    if result["completed"] != denominator:
        raise ValueError("Posting denominator and completed status count do not agree")
    buckets = ("posted_365", "after_365", "not_posted", "unknown_timing")
    if sum(result[key] for key in buckets) != denominator:
        raise ValueError("Posting timing buckets do not sum to the denominator")
    result["coverage_lower"] = result["posted_365"] / denominator if denominator else None
    result["coverage_upper"] = (result["posted_365"] + result["unknown_timing"]) / denominator if denominator else None
    return result


def summarize(connection, snapshot, checksum, as_of, exclusions):
    overall = metrics(connection.execute(f"SELECT {COUNTS} FROM study").fetchone())
    groups = []
    group_years = {}
    for cohort_id, label in COHORTS.items():
        group = connection.execute(f"SELECT {COUNTS} FROM cohort_study WHERE cohort_id = ?", (cohort_id,)).fetchone()
        groups.append({"id": cohort_id, "label": label, **metrics(group)})
        group_years[cohort_id] = [
            {"id": str(year), "label": str(year), "year": year, **metrics(connection.execute(
                f"SELECT {COUNTS} FROM cohort_study WHERE cohort_id = ? AND completion_year = ?",
                (cohort_id, year),
            ).fetchone())}
            for year in range(FIRST_YEAR, LAST_YEAR + 1)
        ]
    years = [
        {"id": str(year), "label": str(year), "year": year, **metrics(connection.execute(
            f"SELECT {COUNTS} FROM study WHERE completion_year = ?", (year,),
        ).fetchone())}
        for year in range(FIRST_YEAR, LAST_YEAR + 1)
    ]
    sponsors = [
        {"id": row["sponsor_class"].lower(), "label": row["sponsor_class"], **metrics(row)}
        for row in connection.execute(f"SELECT sponsor_class, {COUNTS} FROM study GROUP BY sponsor_class ORDER BY count DESC, sponsor_class")
    ]
    statuses = [
        dict(row) for row in connection.execute(
            "SELECT overall_status AS status, COUNT(*) AS count FROM study GROUP BY status ORDER BY count DESC, status"
        )
    ]
    quality = {
        "input_unique": len(snapshot["studies"]),
        "api_matches_by_group": {key: value["api_matches"] for key, value in snapshot["cohorts"].items()},
        "excluded_unique": sum(exclusions.values()),
        "excluded_reasons": dict(sorted(exclusions.items())),
        "multi_group_unique": connection.execute(
            "SELECT COUNT(*) FROM (SELECT nct_id FROM membership GROUP BY nct_id HAVING COUNT(*) > 1)"
        ).fetchone()[0],
        "unknown_timing_reasons": {
            row["timing_detail"]: row["count"] for row in connection.execute(
                "SELECT timing_detail, COUNT(*) AS count FROM study WHERE timing = 'unknown' GROUP BY timing_detail ORDER BY timing_detail"
            )
        },
    }
    return {
        "schema_version": 1,
        "as_of": as_of.isoformat(),
        "source_version": snapshot["source_version"],
        "captured_at_utc": snapshot["captured_at_utc"],
        "snapshot_sha256": checksum,
        "cohort": "Interventional ClinicalTrials.gov search matches with actual primary completion in 2018–2023",
        "studies": overall["count"],
        "overall": overall,
        "groups": groups,
        "years": years,
        "group_years": group_years,
        "sponsors": sponsors,
        "statuses": statuses,
        "quality": quality,
    }


def build(snapshot_path, output):
    snapshot, checksum = load_snapshot(snapshot_path)
    output.mkdir(parents=True, exist_ok=True)
    db = output / "trials.sqlite"
    with tempfile.TemporaryDirectory(dir=output) as staging:
        staged_db = Path(staging) / db.name
        connection = sqlite3.connect(staged_db)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                as_of, exclusions = ingest(connection, snapshot, checksum)
                payload = summarize(connection, snapshot, checksum, as_of, exclusions)
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("SQLite integrity check failed")
                if connection.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("SQLite foreign key check failed")
        finally:
            connection.close()
        os.replace(staged_db, db)
    report = output / "trials_summary.json"
    write_bytes(report, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    payload = build(args.snapshot, args.out_dir)
    print(f"Built {payload['studies']:,} eligible-for-cohort registry studies as of {payload['as_of']}.")


if __name__ == "__main__":
    main()
