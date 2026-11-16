---
name: portfolio-audit
description: Audit the healthcare data science portfolio for technical credibility and release readiness, covering links, accessibility, mobile layout, evidence behind every number, documentation, reproducibility, recruiter readability and GitHub quality. Use before any deploy, after page or CSS changes, or when asked to review the portfolio.
---

# Portfolio audit

Looking good is not the same as being credible. Run the machine checks first, then the human-judgment pass. Report findings; do not fix during the audit unless asked.

## 1. Machine checks (paste the real output)

```
python3 check.py
python3 .agents/skills/portfolio-audit/scripts/audit.py --browser
```

`audit.py` checks internal links and anchors, alt text, one h1 and no skipped heading levels, lang/title/description/viewport, README and tests per project, then at 375, 768 and 1280 px: horizontal overflow, console errors, failed requests, and full-page screenshots into `output/portfolio-audit/` (git-ignored). FAIL lines block release.

CLAIM lines list numbers on a page that no evidence file rounds to. For each, find the source (often a ratio of two counts that are in evidence, or labeled demo data) or flag it. Never "fix" a CLAIM by editing the evidence.

## 2. Look at the screenshots

Open the 375 px shots of every page. Check text wraps, tables scroll inside their region, tap targets are not crowded, and the hero image does not cover text.

## 3. Judgment pass (write one short paragraph each)

1. Evidence: does every result claim match the project README and outputs, and does the wording match CONTRIBUTIONS.md exactly on who did what?
2. Reproducibility: can a stranger run each project from its README with no hidden files?
3. Positioning: within 30 seconds, does a healthcare analytics recruiter see the domain (Medicare reimbursement, clinical trials, FHIR, pharmacovigilance), the tools (Python, SQL, testing) and the role fit?
4. Readability: plain prose, no hype, no AI-sounding phrasing, no walls of bullets.
5. Repo quality: README at root and per project, CI passing, no stray `__pycache__`, data provenance stated, licenses for bundled fonts present.
6. Deployment readiness: all of the above, external links checked on a networked machine, MaCoi's approval to push.

Rank findings by severity (blocks release, should fix, nice to have) with file and line.
