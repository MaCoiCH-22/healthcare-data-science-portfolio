# MaCoi Hollins healthcare data science portfolio

Static site (GitHub Pages: `.nojekyll`, plain HTML and one `style.css`) plus three Python projects in `projects/` with offline tests. Purpose: show credible evidence for healthcare data analyst, data scientist, clinical analytics and pharmacy analytics roles.

## Rules (all agents)

- Never invent results, metrics, work history or accomplishments. Every number on a page must trace to a file in this repo (project outputs, `assets/*_summary.json`) or be labeled as fictional demo data. Authorship follows `CONTRIBUTIONS.md`; do not widen any claim there without MaCoi's word.
- Preserve the current design system (Instrument serif headings, DM Sans body, paper/ink/rose/berry palette in `style.css` `:root`) and working features. Treat them as approved until MaCoi says otherwise. Use skill `frontend-design` for new UI; match, do not restyle.
- Do not push to `main` or change anything that deploys without MaCoi's approval. Work on a branch.
- Copy reads like a person wrote it: plain prose, no hype, no AI-sounding filler.
- The Medicare Bad Debt walkthrough uses fictional data only. Nothing from the private scrubber repo or from work comes here.

## Gates before asking to deploy

`python3 check.py` passes; `python3 .agents/skills/portfolio-audit/scripts/audit.py --browser` has 0 FAIL and every CLAIM line is explained; screenshots at 375, 768 and 1280 px reviewed. Details in `TEST_PLAN.md`.

## Agents and shared files

Default: Claude implements, Codex reviews from the diff (skill `claude-codex-collaboration`), used for major releases and tricky bugs only. Status `PROJECT_STATE.md`, decisions `DECISIONS.md`, map `ARCHITECTURE.md`, baton `HANDOFF.md`. One agent per branch; claim files in HANDOFF.md before editing. Skills live in `.agents/skills/` and are mirrored to `.claude/skills/` by `python3 .agents/sync_skills.py`; edit only the `.agents` copy. Third-party skill sources are in `.agents/VENDORED.md`.
