"""Capture a reproducible, field-limited ClinicalTrials.gov API v2 snapshot."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://clinicaltrials.gov/api/v2"
COHORTS = {
    "asthma": "Asthma",
    "breast-cancer": "Breast Cancer",
    "type-2-diabetes": "Type 2 Diabetes",
}
FIRST_YEAR, LAST_YEAR = 2018, 2023
FIELDS = (
    "NCTId", "StudyType", "OverallStatus", "PrimaryCompletionDate",
    "PrimaryCompletionDateType", "ResultsFirstPostDate", "ResultsFirstPostDateType",
    "LeadSponsorClass", "Phase", "HasResults",
)
FILTER = (
    "AREA[StudyType]INTERVENTIONAL AND "
    f"AREA[PrimaryCompletionDate]RANGE[01/01/{FIRST_YEAR},12/31/{LAST_YEAR}]"
)
DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[1] / "data/registry_snapshot.json.gz"


def get_json(path, query=None):
    url = f"{BASE}/{path}"
    if query:
        url += "?" + urlencode(query)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "registry-operations-portfolio/1.0"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("Request exhausted retry attempts")


def fetch_cohort(item):
    group, term = item
    params = {
        "query.cond": term,
        "filter.advanced": FILTER,
        "fields": ",".join(FIELDS),
        "countTotal": "true",
        "pageSize": 500,
    }
    all_studies = {}
    tokens = set()
    total = None
    while True:
        page = get_json("studies", params)
        if total is None:
            total = page["totalCount"]
        for study in page["studies"]:
            nct_id = study["protocolSection"]["identificationModule"]["nctId"]
            if nct_id in all_studies:
                raise ValueError(f"Repeated record {nct_id} in {group}")
            all_studies[nct_id] = study
        token = page.get("nextPageToken")
        if not token:
            break
        if token in tokens:
            raise ValueError(f"Repeated page token in {group}")
        tokens.add(token)
        params["pageToken"] = token
    if total != len(all_studies):
        raise ValueError(f"{group}: received {len(all_studies)} of {total}")
    return group, {"term": term, "api_matches": total, "ids": sorted(all_studies)}, all_studies


def write_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        try:
            handle.write(content)
            handle.flush()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def capture(path):
    before = get_json("version")
    cohorts, studies = {}, {}
    with ThreadPoolExecutor(max_workers=len(COHORTS)) as workers:
        for group, membership, cohort_studies in workers.map(fetch_cohort, COHORTS.items()):
            cohorts[group] = membership
            for nct_id, study in cohort_studies.items():
                if nct_id in studies and studies[nct_id] != study:
                    raise ValueError(f"Conflicting snapshots for {nct_id}")
                studies[nct_id] = study
    after = get_json("version")
    if before != after:
        raise ValueError("The API data version changed during capture. Rerun.")
    # API timestamps are Eastern registry timestamps. Only the reported calendar date is used in analysis.
    date.fromisoformat(before["dataTimestamp"][:10])
    payload = {
        "schema_version": 1,
        "source": BASE,
        "source_version": before,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "filter": FILTER,
        "fields": list(FIELDS),
        "cohorts": cohorts,
        "studies": studies,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as compressed:
        compressed.write(raw)
    contents = buffer.getvalue()
    write_bytes(path, contents)
    digest = hashlib.sha256(contents).hexdigest()
    write_bytes(Path(path).with_suffix(Path(path).suffix + ".sha256"), (digest + "\n").encode())
    print(f"Captured {len(studies):,} unique API records at {path}\nSHA-256 {digest}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args()
    capture(args.snapshot)


if __name__ == "__main__":
    main()
