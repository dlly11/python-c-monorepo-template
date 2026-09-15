"""Set the lockstep repository version and refresh uv.lock, restoring files on failure."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from repo_tools.context import resolve_root
from repo_tools.repository_metadata import (
    VERSION_PATTERN,
    cmake_project_version,
    python_projects,
    version_errors,
)


def replace_once(contents: str, pattern: re.Pattern[str], replacement: str, path: Path) -> str:
    """Prepare one version replacement without changing the file."""
    updated, replacements = pattern.subn(replacement, contents, count=1)
    if replacements != 1:
        raise ValueError(f"could not find a version declaration in {path}")
    return updated


def update_version(root: Path, version: str) -> None:
    """Validate declarations first, then restore original bytes on any unsuccessful update."""
    projects = python_projects(root)
    paths = [Path("version.txt"), *projects, Path("CMakeLists.txt"), Path("uv.lock")]
    originals = {path: (root / path).read_bytes() for path in paths}
    pattern = re.compile(
        r'(^\[project\]\s*$.*?^version\s*=\s*")[^"]+("\s*$)',
        flags=re.MULTILINE | re.DOTALL,
    )
    updates = {Path("version.txt"): f"{version}\n"}
    for path in projects:
        updates[path] = replace_once(
            originals[path].decode("utf-8"), pattern, rf"\g<1>{version}\g<2>", path
        )
    cmake = Path("CMakeLists.txt")
    contents = originals[cmake].decode("utf-8")
    _, start, end = cmake_project_version(contents)
    updates[cmake] = contents[:start] + version + contents[end:]
    try:
        for path, contents in updates.items():
            (root / path).write_bytes(contents.encode("utf-8"))
        subprocess.run(["uv", "lock"], cwd=root, check=True)
        errors = version_errors(root, version)
        if errors:
            raise ValueError("; ".join(errors))
    except BaseException:
        for path, contents in originals.items():
            try:
                (root / path).write_bytes(contents)
            except OSError as error:
                print(f"could not restore {path}: {error}", file=sys.stderr)
        raise


def build_parser() -> argparse.ArgumentParser:
    """Describe command arguments without performing any work."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="new version in X.Y.Z form")
    return parser


def execute(args: argparse.Namespace, *, root: Path | None = None) -> int:
    """Update all committed version metadata."""
    if VERSION_PATTERN.fullmatch(args.version) is None:
        build_parser().error("version must use the numeric X.Y.Z form")
    if shutil.which("uv") is None:
        build_parser().error("uv must be installed so uv.lock can be refreshed")
    try:
        update_version(resolve_root(root), args.version)
    except KeyboardInterrupt:
        print("version update interrupted", file=sys.stderr)
        return 130
    except (OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"failed to set version: {error}", file=sys.stderr)
        return 1
    print(f"set all repository components to version {args.version}")
    return 0


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    """Parse arguments and run the command."""
    return execute(build_parser().parse_args(argv), root=root)
