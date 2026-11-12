"""Exercise source pagination, date logic, integrity, and independent reconciliation."""

from collections import Counter
import csv
from datetime import date
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import analyze
import registry
import review_queue


class CaptureTests(unittest.TestCase):
    @staticmethod
    def study(nct_id):
        return {"protocolSection": {"identificationModule": {"nctId": nct_id}}}

    def test_all_pages_are_read_and_counted(self):
        one = self.study("NCT00000001")
        two = self.study("NCT00000002")
        pages = [{"totalCount": 2, "studies": [one], "nextPageToken": "x"}, {"studies": [two]}]
        with patch("registry.get_json", side_effect=pages):
            key, group, records = registry.fetch_cohort(("asthma", "Asthma"))
        self.assertEqual((key, group["api_matches"]), ("asthma", 2))
        self.assertEqual(group["ids"], list(records))

    def test_duplicate_page_records_fail(self):
        study = self.study("NCT00000001")
        pages = [{"totalCount": 2, "studies": [study], "nextPageToken": "x"}, {"studies": [study]}]
        with patch("registry.get_json", side_effect=pages), self.assertRaisesRegex(ValueError, "Repeated record"):
            registry.fetch_cohort(("asthma", "Asthma"))

    def test_repeated_pagination_token_fails(self):
        pages = [
            {"totalCount": 2, "studies": [], "nextPageToken": "x"},
            {"studies": [], "nextPageToken": "x"},
        ]
        with patch("registry.get_json", side_effect=pages), self.assertRaisesRegex(ValueError, "Repeated page token"):
            registry.fetch_cohort(("asthma", "Asthma"))

    def test_incomplete_capture_fails(self):
        with patch("registry.get_json", return_value={"totalCount": 1, "studies": []}):
            with self.assertRaisesRegex(ValueError, "received 0 of 1"):
                registry.fetch_cohort(("asthma", "Asthma"))


class TimingTests(unittest.TestCase):
    def result(self, primary, posted=None, present=True, post_type="ACTUAL"):
        details = {"date": posted, "type": post_type}
        return analyze.posting_timing(analyze.date_interval(primary), details, present, date(2026, 11, 10))

    def test_exact_cutoff_and_next_day(self):
        self.assertEqual(self.result("2018-03-09", "2019-03-09")[0], "within_365")
        self.assertEqual(self.result("2018-03-09", "2019-03-10")[0], "after_365")

    def test_partial_precision_leap_date(self):
        self.assertEqual(analyze.date_interval("2020-02").latest, date(2020, 2, 29))
        self.assertEqual(analyze.date_interval("2021").earliest, date(2021, 1, 1))
        for malformed in ("2018-02-29", "2018-00", "018", "2018-2"):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                analyze.date_interval(malformed)

    def test_known_and_ambiguous_partial_posting_dates(self):
        self.assertEqual(self.result("2018-03-09", "2019-02")[0], "within_365")
        self.assertEqual(self.result("2018-03-09", "2019-04")[0], "after_365")
        self.assertEqual(self.result("2018-03-09", "2019-03"), ("unknown", "date_precision_crosses_window"))

    def test_inconsistent_missing_and_future_dates(self):
        self.assertEqual(self.result("2018-03-09", "2018-02"), ("unknown", "posting_date_before_primary_completion"))
        self.assertEqual(self.result("2018-03-09", "2026-12"), ("unknown", "posting_date_after_snapshot"))
        self.assertEqual(self.result("2018-03-09", present=False)[0], "not_posted")
        self.assertEqual(self.result("2018-03-09", "2018-07", present=False)[0], "unknown")
        self.assertEqual(self.result("2018-03-09", "2018-07", post_type="ESTIMATED")[0], "unknown")
        self.assertEqual(self.result("2018-03-09", posted=None)[0], "unknown")

    def test_incomplete_follow_up_is_rejected(self):
        record = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001"},
                "designModule": {"studyType": "INTERVENTIONAL"},
                "statusModule": {"primaryCompletionDateStruct": {"date": "2023", "type": "ACTUAL"}},
            },
            "hasResults": False,
        }
        with self.assertRaisesRegex(ValueError, "less than 365 days"):
            analyze.normalized_study("NCT00000001", record, date(2024, 1, 1))


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.path = Path(cls.work.name)
        cls.payload = analyze.build(registry.DEFAULT_SNAPSHOT, cls.path)
        cls.snapshot, _ = analyze.load_snapshot(registry.DEFAULT_SNAPSHOT)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def test_offline_summary_reproduces_the_delivered_json(self):
        expected = json.loads((ROOT / "output/trials_summary.json").read_text())
        self.assertEqual(self.payload, expected)

    def test_capture_checksum_rejects_tampering(self):
        bad = self.path / "altered.gz"
        bad.write_bytes(registry.DEFAULT_SNAPSHOT.read_bytes() + b"x")
        bad.with_suffix(".gz.sha256").write_text(self.payload["snapshot_sha256"])
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            analyze.load_snapshot(bad)

    def test_independent_registry_reconciliation(self):
        # Independently reconcile source-level status/availability counts and the exact-date lower bound.
        status_counter = Counter()
        known_exact_timely = 0
        posted = 0
        for record in self.snapshot["studies"].values():
            status = record["protocolSection"]["statusModule"]
            primary = status["primaryCompletionDateStruct"]
            if primary["type"] != "ACTUAL" or not 2018 <= int(primary["date"][:4]) <= 2023:
                continue
            status_counter[status["overallStatus"]] += 1
            if status["overallStatus"] != "COMPLETED" or not record["hasResults"]:
                continue
            posted += 1
            publication = status.get("resultsFirstPostDateStruct", {})
            date_text = publication.get("date", "")
            if publication.get("type") == "ACTUAL" and len(date_text) == len(primary["date"]) == 10:
                lag = (date.fromisoformat(date_text) - date.fromisoformat(primary["date"])).days
                known_exact_timely += 0 <= lag <= 365
        actual_status_counts = {item["status"]: item["count"] for item in self.payload["statuses"]}
        self.assertEqual(dict(status_counter), actual_status_counts)
        self.assertEqual(posted, self.payload["overall"]["posted"])
        self.assertLessEqual(known_exact_timely, self.payload["overall"]["posted_365"])

    def test_unique_overall_and_overlapping_memberships(self):
        groups = self.payload["groups"]
        with sqlite3.connect(self.path / "trials.sqlite") as connection:
            memberships = connection.execute("SELECT COUNT(*) FROM membership").fetchone()[0]
            unique = connection.execute("SELECT COUNT(DISTINCT nct_id) FROM membership").fetchone()[0]
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(sum(group["count"] for group in groups), memberships)
        self.assertEqual(self.payload["studies"], unique)
        self.assertGreater(memberships, unique)

    def test_review_queue_matches_unknown_timing_and_cohort(self):
        stream = io.StringIO()
        review_queue.write_queue(self.path / "trials.sqlite", stream, "asthma")
        rows = list(csv.DictReader(io.StringIO(stream.getvalue())))
        group = next(group for group in self.payload["groups"] if group["id"] == "asthma")
        self.assertEqual(len(rows), group["unknown_timing"])
        for row in rows:
            self.assertEqual(row["timing"], "unknown")
            self.assertEqual(row["registry_url"], f"https://clinicaltrials.gov/study/{row['nct_id']}")
        with self.assertRaises(ValueError):
            review_queue.write_queue(self.path / "trials.sqlite", stream, limit=0)

    def test_yearly_and_group_year_metrics_roll_up(self):
        self.assertEqual(sum(row["eligible"] for row in self.payload["years"]), self.payload["overall"]["eligible"])
        for group in self.payload["groups"]:
            for field in ("count", "posted", "posted_365", "not_posted", "unknown_timing"):
                self.assertEqual(sum(row[field] for row in self.payload["group_years"][group["id"]]), group[field])


if __name__ == "__main__":
    unittest.main()
