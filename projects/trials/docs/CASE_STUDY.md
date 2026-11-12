# When did results become available on ClinicalTrials.gov?

A clinical research operations analyst has three related questions. How many studies are marked completed or terminated? Among completed studies, how often are summary results visible in the registry? Which records have conflicting dates worth checking individually?

This workbench answers those questions for three historical registry search groups. It provides comparable denominators, traces the underlying record identifiers, and supports repeatable analysis from a pinned public capture.

## Decision and measurement

The primary cohort is interventional search matches with reported actual primary completion between 2018 and 2023. The year range leaves at least 365 days of observation by the snapshot date. The project reports the status of all included records and restricts posting coverage to records marked completed. For example, termination remains visible as a status but does not enter the 365-day posting denominator.

The project selected a descriptive analysis because the question concerns visible registry records and the underlying source has broad reporting eligibility and potentially unobserved revisions. An outcome prediction model would introduce a separate target, sampling frame, feature availability date, and validation problem.

## Findings from the pinned snapshot

- Of 5,524 distinct included studies, 4,466 were completed, 648 terminated and 108 withdrawn. Another 302 had other statuses. A separate source status query returned 139 studies with status `UNKNOWN`.
- The registry indicated results available for 1,264 of the completed records as of November 10, 2026. Of the completed denominator, 141 were known to have posted within 365 days and nine had indeterminate timing. The project’s sensitivity range for 365-day results posting is 3.16%–3.36%.
- Of the nine indeterminate records, five had date intervals crossing 365 days, one had overlapping primary completion and posting intervals, and three had reported posting dates earlier than reported actual primary completion.
- In the Asthma search, 37 of 568 completed records (6.5%) were known to have posted within 365 days. The analogous counts were 59 of 2,059 for Breast Cancer (2.9%) and 45 of 1,848 for Type 2 Diabetes (2.4%). These are unadjusted comparisons across overlapping registry search groups.

## How a stakeholder can use the outputs

Use the aggregate dashboard to select a cohort and year. Export the indeterminate-timing queue, review the registry history for those NCT identifiers, and document a resolution or escalation. Then examine records marked without registry results only after checking applicable reporting context, submissions, extensions and alternative dissemination channels.

For routine use, schedule new immutable snapshots, diff records by NCT identifier, reconcile changing statuses or dates, and verify policy-specific data before drawing compliance conclusions. Use first submission dates and policy applicability for a separate project on deadline adherence. If the goal becomes inference about cross-group reporting behavior, define the target population and prespecified design, and account for meaningful differences across studies.

[ClinicalTrials.gov source](https://clinicaltrials.gov/) · [Record date definitions](https://clinicaltrials.gov/study-basics/glossary)
