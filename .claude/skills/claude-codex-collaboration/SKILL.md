---
name: claude-codex-collaboration
description: Run a task through Claude and Codex with clear roles (one implements, the other independently reviews or tests), using the Codex MCP server when connected and a HANDOFF.md plus Git branch exchange otherwise. Use for security-sensitive or brain-lane scrubber changes, complex architecture, major portfolio releases, bugs that survived two attempts, or when asked for a Codex review.
---

# Claude and Codex collaboration

Default roles: Claude implements, Codex reviews and tests. Swap for a hard problem where a second approach helps; write the swap in HANDOFF.md.

## When to use two agents (otherwise do not)

Use it for: scrubber brain-lane changes, anything touching PHI handling or money math, security-sensitive code, architecture changes, a major portfolio release, a bug two attempts have not fixed. Skip it for: wording, docs, menu text, styling tweaks, one-line fixes with a passing test.

## The loop

1. Spec: write the task and acceptance criteria (observable, testable) into HANDOFF.md CURRENT.
2. Claim files in HANDOFF.md. Implementer works on its own branch (`claude/<item>` or `codex/<item>`) or a separate worktree (`git worktree add ../<repo>-codex codex/<item>`).
3. Implement, run the project's gates (TEST_PLAN.md), write a 12-line handoff with evidence.
4. Run `python .agents/skills/claude-codex-collaboration/scripts/handoff_check.py` (fields present, no secrets or ID-shaped strings, claimed files respected).
5. Reviewer works read-only from the diff only: `git diff main...<branch> -- <files>`. Reviewer re-runs the tests itself rather than trusting pasted output.
6. Reviewer writes a REVIEW block in HANDOFF.md: verdict (accept / changes needed), defects as one line each with severity, file:line and the evidence command.
7. Implementer fixes only the listed defects, reruns gates.
8. Final verification by whoever did not write the last change.
9. Update PROJECT_STATE.md and DECISIONS.md if anything changed; clear claims.

## How to reach Codex (best available first)

A. Codex MCP server (direct, synchronous). Needs Claude Code on Macoi's computer, Codex CLI installed and signed in, and `claude mcp add codex -- codex mcp-server`. Then use the installed `codex-dispatch` skill: `sandbox: "read-only"` for reviews, `"workspace-write"` only for an assigned implementation, `cwd` = the repo, prompt fully self-contained. Status 2026-11-16: NOT connected, unverified. Exact Windows steps: `references/connect-codex-windows.md`.

B. Codex CLI one-shot from a terminal: `codex exec --sandbox read-only "<self-contained review prompt>"`, output pasted into the REVIEW block. Same prerequisites as A, minus the MCP registration. Unverified.

C. Asynchronous file and Git exchange (works today, no setup). Claude commits to its branch and writes the review request in HANDOFF.md. Macoi opens Codex (app, IDE or CLI) in the repo and says "Do the review requested in HANDOFF.md." Codex reads AGENTS.md automatically, writes its REVIEW block, commits to `codex/review-<item>`. The next Claude session reads it. This is not real-time; never describe it as live.

## Privacy

Codex sends what it reads to OpenAI. In the scrubber repo, restrict prompts to the diff and tests, keep the read-only sandbox, and never let it open workbooks or `06_run_logs/`. Before the first Codex run on a private or employer repo, Macoi must approve.
