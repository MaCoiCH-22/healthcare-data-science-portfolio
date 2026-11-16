---
name: project-handoff
description: Resume or close a work session using the short shared state files (PROJECT_STATE.md, HANDOFF.md, DECISIONS.md). Use at the start of a session to pick up where work stopped, at the end of a session, when switching between Claude and Codex, or when asked "where did we leave off".
---

# Project memory and handoff

Goal: the next agent starts in under a minute without re-reading the repo or asking Macoi to repeat herself.

## Starting a session

1. Read `HANDOFF.md` CURRENT block, then `PROJECT_STATE.md`. Stop there unless the task needs more.
2. Open `DECISIONS.md` only if you are about to change direction or something looks wrong. Never reopen a logged decision without the owner.
3. Open the detailed tracker (for the scrubber, `docs/OPEN_ISSUES.md`) only for the item you are working on, by searching for its number.

## Ending a session (or handing to the other agent)

Rewrite the HANDOFF.md CURRENT block, at most 12 lines: from/to, branch, task, acceptance criteria, files claimed, evidence (command plus result line, or evidence file name), review request if any, open questions. Move the old block to one history line.

Update `PROJECT_STATE.md` only if the state changed (keep it under 40 lines; delete stale lines rather than adding). Add a line to `DECISIONS.md` only for a real decision with who made it.

## Rules

- Facts only. Mark guesses as "(inferred)". Never write "should work"; write what ran.
- No patient data, account numbers, keys, tokens or passwords in any of these files.
- If two files would say the same thing, keep it in one and point to it.
