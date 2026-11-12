import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from analysis import analyze, reporting_odds


class ReportingOddsTests(unittest.TestCase):
    def test_cells_and_ratio(self):
        result = reporting_odds(total=100, drug=30, event=20, both=10)
        self.assertEqual(result["cells"], [10, 20, 10, 60])
        self.assertEqual(result["ror"], 3.0)
        self.assertLess(result["interval"][0], result["ror"])
        self.assertGreater(result["interval"][1], result["ror"])

    def test_no_silent_continuity_correction(self):
        self.assertIsNone(reporting_odds(100, 10, 20, 0)["ror"])

    def test_impossible_counts(self):
        with self.assertRaises(ValueError):
            reporting_odds(100, 30, 20, 35)
        with self.assertRaises(ValueError):
            reporting_odds(100, 90, 90, 20)

    def test_fixed_snapshot_reconciles_and_matches_output(self):
        snapshot = json.loads((ROOT / "data/openfda_counts.json").read_text())
        result = analyze(snapshot)
        expected = json.loads((ROOT / "outputs/drug_summary.json").read_text())
        self.assertEqual(result, expected)
        self.assertEqual(len(result["results"]), 4)
        for row in result["results"]:
            self.assertEqual(sum(row["cells"]), row["total"])
            a, b, c, d = row["cells"]
            self.assertAlmostEqual(row["ror"], (a / b) / (c / d))

    def test_duplicate_query_rejected(self):
        snapshot = json.loads((ROOT / "data/openfda_counts.json").read_text())
        snapshot["counts"].append(snapshot["counts"][0])
        with self.assertRaises(ValueError):
            analyze(snapshot)


if __name__ == "__main__":
    unittest.main()
