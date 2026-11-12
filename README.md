# MaCoi Hollins | Healthcare Analytics & Data Science Portfolio

Portfolio projects spanning clinical research analytics, health data quality, and pharmacovigilance methods.

| Case study | Source and reproduction |
| --- | --- |
| Clinical Trial Registry Intelligence | [Public registry cohort and code](projects/trials/README.md) |
| Clinical Data Quality Engine | [Synthetic FHIR validation pipeline](projects/fhir/README.md) |
| Drug Safety Reporting | [openFDA reporting odds methods](projects/drug-safety/README.md) |

[Download the public résumé](assets/MaCoi_Hollins_Resume.pdf)

## Preview locally

Run `python3 -m http.server --bind 127.0.0.1 8080` from this directory, then open http://127.0.0.1:8080. The case studies render and expand without JavaScript. Project READMEs describe data provenance, scope, and verification.

## Run the offline checks

From the repository root, run `python3 check.py` with Python 3.11 or newer. The trials suite uses synthetic records to exercise the pipeline from capture through SQLite and the review queue. The historical study snapshot is separate from the public checkout.
