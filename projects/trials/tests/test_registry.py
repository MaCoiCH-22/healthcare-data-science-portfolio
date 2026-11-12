"""Exercise source pagination, date logic, integrity, and independent reconciliation."""

import csv
from datetime import date
import io
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
        work = tempfile.TemporaryDirectory()
        cls.addClassCleanup(work.cleanup)
        cls.path = Path(work.name)
        cls.snapshot_path = cls.path / "fixture.json.gz"
        ids = [f"NCT{number:08d}" for number in range(1, 5)]

        def study(nct, status, posted=None):
            dates = {
                "overallStatus": status,
                "primaryCompletionDateStruct": {"date": "2020-03-09", "type": "ACTUAL"},
            }
            if posted:
                dates["resultsFirstPostDateStruct"] = {"date": posted, "type": "ACTUAL"}
            return {
                "protocolSection": {
                    "identificationModule": {"nctId": nct},
                    "designModule": {"studyType": "INTERVENTIONAL"},
                    "statusModule": dates,
                },
                "hasResults": posted is not None,
            }

        first = study(ids[0], "COMPLETED", "2021-02-01")
        uncertain = study(ids[1], "COMPLETED", "2021-03")
        absent = study(ids[2], "COMPLETED")
        terminated = study(ids[3], "TERMINATED")
        matches = {
            "Asthma": [first, uncertain],
            "Breast Cancer": [first, absent],
            "Type 2 Diabetes": [terminated],
        }

        def fixture_api(endpoint, query=None):
            if endpoint == "version":
                return {"dataTimestamp": "2026-11-10T12:00:00"}
            studies = matches[query["query.cond"]]
            return {"totalCount": len(studies), "studies": studies}

        with patch("registry.get_json", side_effect=fixture_api):
            registry.capture(cls.snapshot_path)
        cls.payload = analyze.build(cls.snapshot_path, cls.path)

    def test_fixture_counts_and_timing(self):
        overall = self.payload["overall"]
        self.assertEqual(self.payload["studies"], 4)
        self.assertEqual(overall["eligible"], 3)
        self.assertEqual(overall["posted"], 2)
        self.assertEqual(overall["posted_365"], 1)
        self.assertEqual(overall["unknown_timing"], 1)
        self.assertEqual(overall["not_posted"], 1)

    def test_capture_checksum_rejects_tampering(self):
        bad = self.path / "altered.gz"
        bad.write_bytes(self.snapshot_path.read_bytes() + b"x")
        bad.with_suffix(".gz.sha256").write_text(self.payload["snapshot_sha256"])
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            analyze.load_snapshot(bad)

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
