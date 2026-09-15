"""Type-check workspace members separately, then private tooling and its tests."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from repo_tools.context import resolve_root
from repo_tools.repository_metadata import python_projects


def check_projects(root: Path) -> None:
    """Type-check discovered deliverables, then the orchestration code."""
    for path in python_projects(root):
        if path == Path("pyproject.toml"):
            continue
        project = root / path.parent
        print(f"==> ty check {path.parent}", flush=True)
        subprocess.run(["ty", "check", "--project", str(project)], cwd=root, check=True)
    print("==> ty check private tooling (including tests)", flush=True)
    subprocess.run(
        ["ty", "check", "--project", str(root), str(root / "tools/repo_tools")],
        cwd=root,
        check=True,
    )


def build_parser() -> argparse.ArgumentParser:
    """Describe command arguments without performing any work."""
    parser = argparse.ArgumentParser(description=__doc__)
    return parser


def execute(args: argparse.Namespace, *, root: Path | None = None) -> int:
    """Run the workspace type checks."""
    try:
        root = resolve_root(root)
        check_projects(root)
    except (OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Python type check failed: {error}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    """Parse arguments and run the command."""
    return execute(build_parser().parse_args(argv), root=root)
