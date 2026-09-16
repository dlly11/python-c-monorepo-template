"""Require every tracked file to have an explicit template inclusion decision."""

import fnmatch
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
inventory = json.loads(
    (root / "python/apps/template_creator/src/template_creator/inventory.json").read_text()
)
tracked = set(subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines())
included = set(inventory["include"])
excluded = {
    name
    for name in tracked
    if any(fnmatch.fnmatchcase(name, pattern) for pattern in inventory["exclude"])
}
errors = []
for label, paths in (
    ("unclassified", tracked - included - excluded),
    ("missing", included - tracked),
    ("both included and excluded", included & excluded),
):
    errors.extend(f"{label}: {name}" for name in sorted(paths))
if errors:
    raise SystemExit("Template inventory errors:\n" + "\n".join(errors))
print("All tracked files are classified for template packaging")
