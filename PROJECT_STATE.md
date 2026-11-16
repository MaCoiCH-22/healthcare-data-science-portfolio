# Project state (short)

Last updated: 2026-11-16 by Claude (setup session, branch `ai-dev-system`, pushed, not merged). Keep under 40 lines.

## Where things stand

- `main` at 924c21f (merge of PR #2, scrubber-workflow), last commit 2026-11-13.
- Pages: index, bad-debt, trials, fhir, drug-safety. `check.py`: trials 14, fhir 17, drug-safety 5 tests, all OK (Linux, Python 3.13).
- Audit 2026-11-16: 0 FAIL. Internal links, anchors, alt text, headings and meta all pass; no horizontal overflow, console errors or failed requests at 375, 768, 1280 px.

## Open items for MaCoi

- Numbers to confirm (audit CLAIM lines): 36.8%, 27.7%, 26.2% on index and trials are ratios of counts that are in evidence files (for example 209 of 568 = 36.8%); the bad-debt walkthrough's dollar figures are fictional demo values. Confirm both readings.
- 11 external links were not checked from this sandbox (no general internet). Check them on a networked machine.
- Deployment: none done. Any push to `main` publishes the site.
