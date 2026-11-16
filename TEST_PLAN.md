# Test plan

| When | Command | Pass means |
| --- | --- | --- |
| Any code change | `python3 check.py` | Every project suite OK |
| Any page or CSS change | `python3 .agents/skills/portfolio-audit/scripts/audit.py --browser` | 0 FAIL; screenshots in `output/portfolio-audit/` (git-ignored) look right at 375, 768, 1280 px |
| Any new number on a page | same audit | No new CLAIM line, or the CLAIM is explained in PROJECT_STATE.md |
| Before deploy | all of the above, plus external links checked on a networked machine and a Codex review of the diff for a major release | MaCoi approves the push |

Browser checks need Playwright for Python with Chromium (`pip install playwright` then `python -m playwright install chromium`). Local preview: `python3 -m http.server --bind 127.0.0.1 8080`.

Baseline 2026-11-16 (Linux, Python 3.13.18): check.py 36 tests OK in 0.7 s; audit 27 static plus 15 browser checks, 0 FAIL, 3 pages with numbers to verify.
