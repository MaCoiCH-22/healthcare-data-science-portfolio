# Vendored third-party skills

Reviewed 2026-11-16 before copying. Re-review on every update; never pull a new upstream version without reading its scripts.

| Skill | Source | Commit | License | Scripts and dependencies | Local patches |
| --- | --- | --- | --- | --- | --- |
| frontend-design | github.com/anthropics/skills `skills/frontend-design` | e4bb5d9 (2026-11-16) | see LICENSE.txt in folder | Instructions only, no scripts | none (identical to the copy built into claude.ai) |
| webapp-testing | github.com/anthropics/skills `skills/webapp-testing` | e4bb5d9 (2026-11-16) | Apache-2.0 | `scripts/with_server.py` starts your own server command with `shell=True` (local only); needs Python `playwright` and Chromium | none |
| playwright | github.com/openai/skills `skills/.curated/playwright` | 49f948f (2026-06-23) | Apache-2.0 | `scripts/playwright_cli.sh` runs `npx --yes @playwright/cli` (Microsoft, Apache-2.0) | Pinned `@playwright/cli@0.1.24` (upstream runs latest unpinned); added a repo-scoped path note to SKILL.md |

Not vendored on purpose: `skill-creator` (already built into Claude; for Codex use its built-in `$skill-creator`), `playwright-interactive` (needs a persistent JS REPL; the CLI skill covers the need).
