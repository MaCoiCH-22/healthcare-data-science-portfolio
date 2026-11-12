# Drug Safety Reporting

A companion methods project for a pharmacovigilance reviewer. It shows how the reporting odds ratio changes across two receipt years and two reaction terms using openFDA aggregate counts.

## Data and methods

- Source: [openFDA drug adverse event API](https://open.fda.gov/apis/drug/event/). The fixed snapshot records the exact query URLs and source update date. Only aggregate counts are retained.
- Inclusion: all indexed reports received in 2023 or 2024, worldwide, with exact indexed-field matching as handled by openFDA. Drug matching uses the indexed generic name IBUPROFEN. Reaction matching uses the terms NAUSEA and HEADACHE. Drug and reaction can appear anywhere in the same report.
- Four cells: report matches both, drug only, reaction only, neither. The reporting odds ratio is a × d / (b × c). A 95% log-Wald interval uses the sum of inverse cell counts for its log-scale variance. Zero cells return unavailable without a continuity correction.
- Comparator: reports without the indexed generic-name match. They can include reports with an unavailable generic mapping. Reports may describe multiple suspect or concomitant drugs and multiple reactions.
- Receipt-year and term stratification are illustrative sensitivity comparisons. The analysis performs no significance testing, multiplicity adjustment, causal inference, or regulatory screening decision.

| Receipt year | Nausea ROR (95% interval) | Headache ROR (95% interval) |
| --- | ---: | ---: |
| 2023 | 2.15 (2.02–2.28) | 2.38 (2.23–2.54) |
| 2024 | 2.75 (2.60–2.91) | 3.36 (3.16–3.56) |

In the selected report sets, both ratios are higher in the later receipt year. A report is not a patient. The database lacks the denominator required to estimate incidence, and co-reporting does not establish causality. Deduplication, case versioning, primary suspect role, confounding, and changes in reporting or data mapping can affect results. The intervals do not account for these sources of systematic error. See [FDA AEMS](https://www.fda.gov/drugs/surveillance-post-drug-approval-activities/fda-adverse-event-monitoring-system-aems).

## Reproduce

From the portfolio root, with Python 3.10+ and no third-party dependencies:

```bash
python3 projects/drug-safety/src/analysis.py
python3 -m unittest discover -s projects/drug-safety/tests -v
```

Add `--refresh` to the analysis command to replace the frozen aggregate snapshot with live data. Source revisions can change results. The code rejects inconsistent margins and differing API update stamps.

## Provenance

AI-assisted independent portfolio demonstration, separate from employment and coursework.
