"""Type-check workspace members separately, then repository scripts and their tests."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from repository_metadata import ROOT, python_projects


def check_projects(root: Path) -> None:
    """Type-check discovered deliverables, then the orchestration code."""
    for path in python_projects(root):
        if path == Path("pyproject.toml"):
            continue
        project = root / path.parent
        print(f"==> ty check {path.parent}", flush=True)
        subprocess.run(["ty", "check", "--project", str(project)], cwd=root, check=True)
    print("==> ty check scripts (including script tests)", flush=True)
    subprocess.run(
        ["ty", "check", "--project", str(root), str(root / "scripts")], cwd=root, check=True
    )


def main(argv: list[str] | None = None) -> int:
    """Run the workspace type checks."""
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        check_projects(ROOT)
    except (OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Python type check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
