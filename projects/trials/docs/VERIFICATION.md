# Verification

Executed November 12, 2026, using Python 3.12.14 and SQLite 3.53.1.

| Check | Observed result |
| --- | --- |
| Live source pagination | All three ClinicalTrials.gov search counts reconciled to the reported totals of 831, 3,689 and 2,643 |
| Source version | API version and data timestamp matched before and after collection |
| Snapshot integrity | SHA-256 verified during every replay |
| SQLite integrity | `PRAGMA integrity_check` returned `ok`; foreign key violations were zero |
| Automated tests | All 15 passed |
| Offline replay | Summary regenerated in a temporary directory and compared to the packaged report |
| Independent raw-data reconciliation | Full study-status counts and completed results availability matched direct counts from the frozen raw records |
| Threshold | Tests cover elapsed days 365 and 366, partial precision, invalid dates, future dates and inadequate follow-up |
| Review queue | Nine unique indeterminate records exported with a source URL and review reason for each |
| Roll-ups | Year and cohort-year aggregation reconcile to the summary denominators; overlap remains explicit |

## Review findings addressed

| Issue | Change |
| --- | --- |
| Search-group overlap inflated totals if summed | Counted distinct NCT IDs overall and maintained membership separately |
| Month-only dates risked arbitrary first-day imputation | Used date intervals and reported ambiguous timings explicitly |
| Studies lacked a complete 365-day observation window in recent years | Used a fixed date window and enforced minimum follow-up |
| Registry first-post dates could be mistaken for submission dates | Defined the measure in the data dictionary and kept regulatory applicability out of scope |
| Missing or conflicting dates were difficult to reconcile in an aggregate view | Added an export keyed to the original public registry record |

Remaining limitations include reliance on a single registry snapshot, exclusion of non-completed records from the primary posting denominator, and reliance on registry condition search matching. There is no policy adjudication or cross-registry outcome comparison. The source capture pipeline requires live access only for refreshes.

The full automated test run is included as [test-log.txt](test-log.txt).
