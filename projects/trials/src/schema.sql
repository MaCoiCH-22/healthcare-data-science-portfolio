PRAGMA foreign_keys = ON;
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE cohort (
    cohort_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    api_matches INTEGER NOT NULL CHECK (api_matches >= 0)
);
CREATE TABLE study (
    nct_id TEXT PRIMARY KEY,
    overall_status TEXT NOT NULL,
    sponsor_class TEXT NOT NULL,
    phases TEXT NOT NULL,
    primary_completion_date TEXT NOT NULL,
    completion_year INTEGER NOT NULL,
    has_results INTEGER NOT NULL CHECK (has_results IN (0, 1)),
    results_first_post_date TEXT,
    timing TEXT NOT NULL CHECK (
        timing IN ('within_365', 'after_365', 'not_posted', 'unknown', 'not_eligible')
    ),
    timing_detail TEXT NOT NULL
);
CREATE TABLE membership (
    cohort_id TEXT NOT NULL REFERENCES cohort(cohort_id),
    nct_id TEXT NOT NULL REFERENCES study(nct_id),
    PRIMARY KEY (cohort_id, nct_id)
);
CREATE INDEX membership_study ON membership(nct_id);
CREATE INDEX study_completion_year ON study(completion_year);
CREATE VIEW cohort_study AS
SELECT membership.cohort_id, study.* FROM membership JOIN study USING (nct_id);
