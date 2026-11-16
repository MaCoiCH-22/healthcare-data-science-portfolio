# Architecture map

| Part | Files | Notes |
| --- | --- | --- |
| Site | `index.html`, `bad-debt.html`, `trials.html`, `fhir.html`, `drug-safety.html`, `style.css` | Static, no build step. GitHub Pages (`.nojekyll`). |
| Design tokens | `style.css` `:root` | Colors paper, ink, muted, dark, rose, berry; fonts Instrument (serif) and DM Sans, self-hosted in `assets/` with OFL licenses |
| Demo | `assets/scrubber-demo.js` | Interactive bad-debt walkthrough on fictional data |
| Evidence | `assets/*_summary.json`, `assets/trials_timing_review.csv`, `assets/*_source.zip` | Numbers shown on pages come from here or from project outputs |
| Trials project | `projects/trials/` (`src/registry.py`, `analyze.py`, `review_queue.py`, `schema.sql`) | Registry capture to SQLite to review queue; synthetic test records |
| FHIR project | `projects/fhir/` (`run.py`, `src/fhir_quality/`) | Synthetic FHIR validation pipeline with audit ledger |
| Drug safety | `projects/drug-safety/` (`src/analysis.py`) | Reporting odds ratios on fixed openFDA aggregate counts |
| Checks | `check.py`, `.github/workflows/check.yml` | Runs each project's unittest suite on push and PR (Python 3.12 in CI) |
| Résumé | `assets/MaCoi_Hollins_Resume.pdf` | Public résumé linked from the nav |
