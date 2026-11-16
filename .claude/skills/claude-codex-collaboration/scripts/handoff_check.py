"""Check HANDOFF.md before passing the baton. Prints field names and counts only.

Fails if a required field is missing, if a secret- or ID-shaped string appears,
or if the current branch changed a file the other agent has claimed.
"""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

REQUIRED = ["From:", "Branch:", "Task:", "Acceptance:", "Claimed files:", "Evidence:"]
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY)")
MBI = re.compile(r"\b[1-9][AC-HJKMNP-RT-Y][AC-HJKMNP-RT-Y0-9][0-9][AC-HJKMNP-RT-Y][AC-HJKMNP-RT-Y0-9][0-9][AC-HJKMNP-RT-Y]{2}[0-9]{2}\b")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def main(path="HANDOFF.md"):
    p = Path(path)
    if not p.is_file():
        print(f"FAIL  {path} not found"); return 1
    text = p.read_text(encoding="utf-8")
    current = text.split("## History")[0]
    problems = [f"missing field {f}" for f in REQUIRED if f not in current]
    if SECRET.search(text):
        problems.append("secret-shaped string present")
    n_ids = len(MBI.findall(text)) + len(SSN.findall(text))
    if n_ids:
        problems.append(f"{n_ids} ID-shaped string(s) present")
    m = re.search(r"From:\s*(\w+)", current)
    me = (m.group(1).lower() if m else "")
    other_claims = re.findall(r"Claimed by (\w+):\s*(.+)", current)
    try:
        changed = set(subprocess.run(["git", "diff", "--name-only", "main...HEAD"], capture_output=True,
                                     text=True, check=True).stdout.split())
    except (subprocess.CalledProcessError, FileNotFoundError):
        changed = set()
    for who, files in other_claims:
        if who.lower() != me:
            clash = changed & {f.strip(" `") for f in files.split(",")}
            if clash:
                problems.append(f"changed files claimed by {who}: {sorted(clash)}")
    for line in problems:
        print("FAIL ", line)
    if not problems:
        print(f"PASS  {path}: all {len(REQUIRED)} fields present, no secrets or ID-shaped strings, no claim clashes")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
