"""Check that every release-bearing component uses the repository version."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo_tools.context import resolve_root
from repo_tools.repository_metadata import repository_version, version_errors


def build_parser() -> argparse.ArgumentParser:
    """Describe command arguments without performing any work."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="also require this release tag to equal v<version>")
    return parser


def execute(args: argparse.Namespace, *, root: Path | None = None) -> int:
    """Run the version consistency check."""

    try:
        root = resolve_root(root)
        expected = repository_version(root)
        errors = version_errors(root, expected, args.tag)
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(f"version check failed: {error}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"version check failed: {error}", file=sys.stderr)
        return 1

    print(f"all repository components use version {expected}")
    return 0


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    """Parse arguments and run the command."""
    return execute(build_parser().parse_args(argv), root=root)
