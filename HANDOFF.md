# Handoff

Replace CURRENT each time; move the old block to one history line. No keys, tokens or personal data.

## CURRENT

- From: Claude (Cowork cloud session) To: MaCoi, then Codex for review
- Branch: `ai-dev-system` (pushed to origin, not merged; main untouched)
- Task: add shared agent files, repo skills and the portfolio audit. No page, CSS or project code changed.
- Acceptance: `git diff main --stat` touches only agent files, `.agents/`, `.claude/`, `.gitignore`; `check.py` OK; audit 0 FAIL.
- Claimed files: none (setup finished)
- Evidence: `python3 check.py` 36 tests OK; `audit.py --browser` 0 FAIL
- Review request for Codex: `git diff main...ai-dev-system -- .agents/skills/portfolio-audit .agents/VENDORED.md` Check the audit does not report false PASSes (link and anchor logic, overflow test) and that vendored skills match their recorded upstream commits apart from the listed patches.

## History

- 2026-11-16 Claude: setup of AI dev system on branch `ai-dev-system`.
