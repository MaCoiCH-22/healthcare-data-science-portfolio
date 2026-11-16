---
name: code-exploration
description: Find the code relevant to a task with the fewest reads, using ARCHITECTURE.md, filename and symbol search, and narrow line-range reads instead of opening whole files or directories. Use before reading any file over about 300 lines, when locating where something happens, or when starting work in an unfamiliar area.
---

# Efficient code exploration

Measured on the scrubber (2026-11-16, one task, "where are hidden sheets detected"): 4 targeted commands returned 2,504 bytes; reading `compact_inspector.py` and `bdl_engine.py` whole returned 737,473 bytes. Both found the same two functions. One task is not a general percentage; re-measure before quoting savings.

## Order of moves (stop as soon as you can answer)

1. `ARCHITECTURE.md` and `PROJECT_STATE.md`: which file owns this?
2. Filename search: `git ls-files | grep -i <word>`.
3. Symbol search: `grep -nE "^(def|class) <name>" <file>` or `grep -n "<CONSTANT> *=" *.py`. For callers: `grep -n "<name>(" *.py | head -20`.
4. Read only the found range: `sed -n '<start>,<end>p' <file>` (about 40 to 80 lines). Widen only if the function continues.
5. Dependencies: `grep -nE "^(from|import) " <file>` before guessing what a module uses.

## Rules

- Never `cat` a file over 300 lines or list a directory recursively without a filter. Cap output with `head`.
- Do not re-read a range you already have in context; note line numbers once.
- Do not read data files to understand code. In the scrubber, never open real workbooks at all.
- When you learn something durable about the layout, add one line to ARCHITECTURE.md so nobody pays for it twice.
