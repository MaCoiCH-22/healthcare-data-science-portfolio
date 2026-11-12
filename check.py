"""Run each project's offline tests in its own process."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
failed = False
for project in ("trials", "fhir", "drug-safety"):
    print(f"\n{project}", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=root / "projects" / project,
        check=False,
    )
    failed |= result.returncode != 0
sys.exit(int(failed))
