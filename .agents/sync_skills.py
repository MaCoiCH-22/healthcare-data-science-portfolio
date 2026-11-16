"""Mirror .agents/skills (Codex) to .claude/skills (Claude Code). Real copies, no symlinks,
because Windows checkouts turn git symlinks into text files.

  python .agents/sync_skills.py          copy, then verify
  python .agents/sync_skills.py --check  verify only; exit 1 if the mirror differs
"""
import filecmp, shutil, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src, dst = root / ".agents" / "skills", root / ".claude" / "skills"


def differences():
    if not dst.is_dir():
        return ["(mirror missing)"]
    out = []
    def walk(c, rel=""):
        out.extend(f"{rel}{n}" for n in c.left_only + c.right_only + c.diff_files + c.funny_files)
        for name, sub in c.subdirs.items():
            if name != "__pycache__":
                walk(sub, f"{rel}{name}/")
    walk(filecmp.dircmp(src, dst, ignore=["__pycache__"]))
    return [d for d in out if "__pycache__" not in d]


if "--check" not in sys.argv:
    for skill in src.iterdir():
        if skill.is_dir():
            target = dst / skill.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(skill, target, ignore=shutil.ignore_patterns("__pycache__"))
    for stale in (dst.iterdir() if dst.is_dir() else []):
        if stale.is_dir() and not (src / stale.name).is_dir():
            shutil.rmtree(stale)

diff = differences()
names = sorted(p.parent.name for p in src.glob("*/SKILL.md"))
print(("MIRROR OK: " if not diff else "MIRROR DIFFERS: " + ", ".join(diff) + " | skills: ") + ", ".join(names))
sys.exit(1 if diff else 0)
