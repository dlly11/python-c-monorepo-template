"""Run ty once per Python workspace member to preserve package boundaries."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = (
    ROOT / "python/packages/core",
    ROOT / "python/packages/package_a",
    ROOT / "python/packages/package_b",
    ROOT / "python/apps/package_a_cli",
)


def main() -> None:
    """Type-check every independently deliverable Python project."""
    for project in PROJECTS:
        relative_project = project.relative_to(ROOT)
        print(f"==> ty check {relative_project}", flush=True)
        subprocess.run(
            ["ty", "check", "--project", str(project)],
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    main()
