# Data and metric definitions

## Source

ClinicalTrials.gov API v2 `GET /api/v2/studies` and `GET /api/v2/version`. The historical data timestamp is `2026-11-10T10:00:05` from the API. The UTC collection time was `2026-11-12T06:56:28+00:00`. The capture verifies a stable version before and after pagination and compares unique retrieved counts against the API-reported total for each search. The snapshot is a project-specific selection of API fields with cohort membership metadata, gzip compression and an adjacent SHA-256 checksum.

The three independent `query.cond` terms are Asthma, Breast Cancer, and Type 2 Diabetes. Each request applies `AREA[StudyType]INTERVENTIONAL AND AREA[PrimaryCompletionDate]RANGE[01/01/2018,12/31/2023]`. Local eligibility requires interventional type and an actual, valid primary completion date entirely in the date window. Search semantics are controlled by the registry and can include synonyms or secondary conditions. The portfolio uses search group names as labels without asserting diagnostic adjudication.

## SQLite fields

| Table or view | Field | Meaning |
| --- | --- | --- |
| `study` | `nct_id` | Unique ClinicalTrials.gov study identifier |
| `study` | `overall_status` | Registry overall status in the capture |
| `study` | `sponsor_class` | Lead-sponsor class supplied by the registry |
| `study` | `phases` | Comma-separated phase codes, sorted |
| `study` | `primary_completion_date` | Exact or partial registry date, restricted to `ACTUAL` |
| `study` | `completion_year` | Year of reported actual primary completion |
| `study` | `has_results` | Registry presence flag as of the snapshot |
| `study` | `results_first_post_date` | API `resultsFirstPostDateStruct.date` value when present |
| `study` | `timing` | `within_365`, `after_365`, `not_posted`, `unknown` or `not_eligible` |
| `study` | `timing_detail` | Deterministic reason for the assigned bucket |
| `cohort` | `cohort_id`, `label`, `api_matches` | Search identifier, human-readable term and pre-local-filter count |
| `membership` | `cohort_id`, `nct_id` | Many-to-many join with enforced foreign keys |
| `metadata` | `key`, `value` | JSON-serialized source, version, capture, filter, fields and SHA-256 values |
| `cohort_study` | `cohort_id` and study fields | Joined query view for cohort grouping |

## Posting measures

- **Results available** counts `hasResults=true` among included studies whose overall status is `COMPLETED`.
- **Within 365 days** measures elapsed calendar days from actual primary completion to results first post after registry quality-control review. Exact dates count if the elapsed time is between 0 and 365 days inclusive. `Results First Posted with QC Comments` and first submission are distinct registry fields outside this measure.
- **Date intervals** use the first and last day when only a month or year is supplied. Minimum elapsed time is earliest posting minus latest primary completion. Maximum elapsed time is latest posting minus earliest primary completion. A timing bucket requires that all valid dates in the interval fit the bucket. Inconsistent dates and ambiguous intervals stay visible in the indeterminate category.
- **Sensitivity range** keeps the completed denominator fixed. The lower endpoint includes only known within-window postings. The upper endpoint also counts every indeterminate record as hypothetically within-window. The endpoints reflect alternate handling of uncertain records. They do not quantify sampling error.
- **Follow-up** must extend at least 365 days beyond even the latest possible completion date. The 2018–2023 cohort satisfies this criterion in the November 2026 snapshot.
- **Outside posting denominator** includes all statuses other than `COMPLETED`, even where they contribute to the status breakdown. Status and date fields may be updated by record owners.

The analysis neither determines applicability of reporting obligations nor measures submissions or publications elsewhere. Jurisdiction, results reporting policy, sponsor process, and changes in registry quality-control posting can affect comparisons.

[API documentation](https://clinicaltrials.gov/data-api/about-api) · [Glossary](https://clinicaltrials.gov/study-basics/glossary) · [Reporting requirements](https://clinicaltrials.gov/policy/reporting-requirements) · [Terms](https://clinicaltrials.gov/about-site/terms-conditions)
