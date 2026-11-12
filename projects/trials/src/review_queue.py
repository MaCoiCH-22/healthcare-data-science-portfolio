"""Export traceable record IDs for registry timing review."""

import argparse
import csv
from pathlib import Path
import sqlite3
import sys

from analyze import ROOT
from registry import COHORTS

FIELDS = (
    "nct_id", "completion_year", "primary_completion_date", "results_first_post_date",
    "has_results", "timing", "timing_detail", "sponsor_class", "registry_url",
)


def write_queue(db, stream, cohort=None, timing="unknown", limit=100):
    if timing not in {"unknown", "after_365", "not_posted"}:
        raise ValueError("Unsupported review timing")
    if cohort is not None and cohort not in COHORTS:
        raise ValueError("Unsupported cohort")
    if limit < 1:
        raise ValueError("Limit must be positive")
    sql = """
        SELECT s.nct_id, s.completion_year, s.primary_completion_date, s.results_first_post_date,
               s.has_results, s.timing, s.timing_detail, s.sponsor_class
        FROM study AS s
        WHERE s.timing = ?
          AND (? IS NULL OR EXISTS (
              SELECT 1 FROM membership AS m WHERE m.nct_id = s.nct_id AND m.cohort_id = ?
          ))
        ORDER BY s.completion_year DESC, s.nct_id
        LIMIT ?
    """
    uri = db.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        for row in connection.execute(sql, (timing, cohort, cohort, limit)):
            writer.writerow((*row, f"https://clinicaltrials.gov/study/{row[0]}"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "output/trials.sqlite")
    parser.add_argument("--cohort", choices=COHORTS)
    parser.add_argument("--timing", choices=["unknown", "after_365", "not_posted"], default="unknown")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    write_queue(args.db, sys.stdout, args.cohort, args.timing, args.limit)


if __name__ == "__main__":
    main()
