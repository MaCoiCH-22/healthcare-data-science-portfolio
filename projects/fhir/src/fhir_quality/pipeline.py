"""Build a reproducible SQLite audit ledger and a public aggregate JSON report."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from .fixture import FEEDS
from .validate import RULES, SUPPORTED_TYPES, audit, string_in

BATCH_NAME = re.compile(r"([1-3])-(\d{2})\.json\Z")
DB_NAME = "audit.sqlite3"
REPORT_NAME = "report.json"
RULESET_VERSION = "1.0.0"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE batch (
    batch_id TEXT PRIMARY KEY,
    feed TEXT NOT NULL,
    source_file TEXT NOT NULL,
    sha256 TEXT NOT NULL
) WITHOUT ROWID;
CREATE TABLE resource (
    batch_id TEXT REFERENCES batch,
    entry_index INTEGER,
    resource_type TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK(disposition IN ('accepted', 'direct', 'dependent')),
    PRIMARY KEY(batch_id, entry_index)
) WITHOUT ROWID;
CREATE TABLE rule (
    rule_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('error', 'warning')),
    category TEXT NOT NULL
) WITHOUT ROWID;
CREATE TABLE finding (
    batch_id TEXT,
    entry_index INTEGER,
    rule_id TEXT REFERENCES rule,
    source_path TEXT,
    PRIMARY KEY(batch_id, entry_index, rule_id, source_path),
    FOREIGN KEY(batch_id, entry_index) REFERENCES resource
) WITHOUT ROWID;
CREATE TABLE reference (
    batch_id TEXT,
    entry_index INTEGER,
    field TEXT,
    target_index INTEGER NOT NULL,
    PRIMARY KEY(batch_id, entry_index, field),
    FOREIGN KEY(batch_id, entry_index) REFERENCES resource,
    FOREIGN KEY(batch_id, target_index) REFERENCES resource(batch_id, entry_index)
) WITHOUT ROWID;
CREATE TABLE accepted_measurement (
    batch_id TEXT,
    entry_index INTEGER,
    loinc_code TEXT NOT NULL,
    normalized_value REAL NOT NULL,
    ucum_code TEXT NOT NULL,
    PRIMARY KEY(batch_id, entry_index),
    FOREIGN KEY(batch_id, entry_index) REFERENCES resource
) WITHOUT ROWID;
CREATE INDEX idx_finding_rule ON finding(rule_id, batch_id);
CREATE INDEX idx_batch_feed ON batch(feed, batch_id);
"""

RESOURCE_COUNTS = """
SELECT COUNT(*) AS resources,
       COUNT(*) FILTER (WHERE disposition = 'accepted') AS accepted,
       COUNT(*) FILTER (WHERE disposition <> 'accepted') AS quarantined,
       COUNT(*) FILTER (WHERE disposition = 'direct') AS direct_quarantine,
       COUNT(*) FILTER (WHERE disposition = 'dependent') AS dependent_quarantine
FROM resource
"""

FINDING_COUNTS = """
SELECT COUNT(*) AS findings,
       COUNT(*) FILTER (WHERE severity = 'error') AS errors,
       COUNT(*) FILTER (WHERE severity = 'warning') AS warnings
FROM finding JOIN rule USING (rule_id)
"""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"non-finite JSON number {value}")


def finite_float(value):
    result = float(value)
    return result if math.isfinite(result) else reject_constant(value)


def ingest(path: Path, connection: sqlite3.Connection) -> None:
    match = BATCH_NAME.fullmatch(path.name)
    if match is None:
        raise ValueError(f"{path.name}: expected a synthetic feed batch named 1-01.json")
    feed_number, batch_number = match.groups()
    batch_id = f"feed-{feed_number}-{batch_number}"
    payload = path.read_bytes()
    try:
        bundle = json.loads(
            payload.decode("utf-8"), object_pairs_hook=unique_object,
            parse_constant=reject_constant, parse_float=finite_float,
        )
    except (ValueError, RecursionError) as error:
        raise ValueError(f"{path.name}: invalid input JSON ({error})") from error
    if not (
        isinstance(bundle, dict) and bundle.get("resourceType") == "Bundle"
        and bundle.get("type") == "collection" and bundle.get("id") == batch_id
        and isinstance(bundle.get("entry"), list) and bundle["entry"]
    ):
        raise ValueError(f"{path.name}: expected matching collection Bundle with entries")
    records = audit(bundle["entry"])
    connection.execute(
        "INSERT INTO batch VALUES (?, ?, ?, ?)",
        (batch_id, FEEDS[int(feed_number) - 1], path.name, hashlib.sha256(payload).hexdigest()),
    )
    connection.executemany(
        "INSERT INTO resource VALUES (?, ?, ?, ?, ?)",
        (
            (
                batch_id, record.entry_index,
                record.resource_type if string_in(record.resource_type, SUPPORTED_TYPES) else "Unsupported",
                record.content_hash, disposition(record),
            )
            for record in records
        ),
    )
    connection.executemany(
        "INSERT INTO finding VALUES (?, ?, ?, ?)",
        (
            (batch_id, record.entry_index, finding.rule, finding.path)
            for record in records for finding in record.findings
        ),
    )
    connection.executemany(
        "INSERT INTO reference VALUES (?, ?, ?, ?)",
        (
            (batch_id, record.entry_index, field, target)
            for record in records for field, target in record.targets.items()
        ),
    )
    connection.executemany(
        "INSERT INTO accepted_measurement VALUES (?, ?, ?, ?, ?)",
        (
            (batch_id, record.entry_index, *record.normalized)
            for record in records if not record.quarantined and record.normalized is not None
        ),
    )


def disposition(record) -> str:
    if record.direct_error:
        return "direct"
    if record.quarantined:
        return "dependent"
    return "accepted"


def query(connection, statement, values=()):
    return [dict(row) for row in connection.execute(statement, values)]


def make_report(connection) -> dict:
    summary = query(connection, RESOURCE_COUNTS)[0]
    summary.update(query(connection, FINDING_COUNTS)[0])
    summary.update(query(
        connection,
        """
        SELECT (SELECT COUNT(*) FROM batch) AS batches,
               (SELECT COUNT(*) FROM accepted_measurement) AS accepted_measurements
        """,
    )[0])
    feeds = []
    for feed in query(connection, "SELECT feed, COUNT(*) AS batches FROM batch GROUP BY feed ORDER BY feed"):
        name = feed["feed"]
        feed.update(query(connection, RESOURCE_COUNTS + "JOIN batch USING (batch_id) WHERE feed = ?", (name,))[0])
        feed.update(query(connection, FINDING_COUNTS + "JOIN batch USING (batch_id) WHERE feed = ?", (name,))[0])
        feeds.append(feed)
    rules = query(connection, """
        SELECT rule_id AS id, label, severity, category, COUNT(finding.rule_id) AS count
        FROM rule LEFT JOIN finding USING (rule_id)
        GROUP BY rule_id
        ORDER BY count DESC, rule_id
    """)
    feed_rules = query(connection, """
        SELECT feed, rule_id, COUNT(*) AS count
        FROM finding JOIN batch USING (batch_id)
        GROUP BY feed, rule_id
        ORDER BY feed, rule_id
    """)
    measures = query(connection, """
        SELECT loinc_code AS code, ucum_code AS unit, COUNT(*) AS count,
               ROUND(AVG(normalized_value), 2) AS mean
        FROM accepted_measurement GROUP BY loinc_code, ucum_code ORDER BY loinc_code
    """)
    return {
        "schema_version": 1, "ruleset_version": RULESET_VERSION,
        "dataset": "Deterministic synthetic FHIR R4 fixture", "summary": summary,
        "feeds": feeds, "rules": rules, "feed_rules": feed_rules, "measures": measures,
    }


def validate_directory(source: Path, output: Path) -> dict:
    if source.resolve() == output.resolve():
        raise ValueError("Input and output directories must differ")
    batches = sorted(source.glob("*.json"))
    if not batches:
        raise ValueError(f"No synthetic JSON batches found in {source}")
    output.mkdir(parents=True, exist_ok=True)
    # Build privately before replacing either deliverable. Bad input leaves any
    # last successful outputs untouched. Each final rename is atomic individually.
    with TemporaryDirectory(dir=output, prefix=".audit-") as temporary:
        stage = Path(temporary)
        with closing(sqlite3.connect(stage / DB_NAME)) as connection:
            connection.row_factory = sqlite3.Row
            connection.executescript(SCHEMA)
            with connection:
                connection.executemany(
                    "INSERT INTO rule VALUES (?, ?, ?, ?)",
                    ((rule_id, *details) for rule_id, details in RULES.items()),
                )
                for path in batches:
                    ingest(path, connection)
                report = make_report(connection)
        (stage / REPORT_NAME).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        for name in (DB_NAME, REPORT_NAME):
            (stage / name).replace(output / name)
    return report
