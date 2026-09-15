"""Validate a pull request title as a Conventional Commit subject."""

from __future__ import annotations

import sys

from conventional_commits import valid_subject


def main() -> int:
    """Validate the title passed on the command line."""
    if len(sys.argv) != 2 or not valid_subject(sys.argv[1]):
        title = sys.argv[1] if len(sys.argv) == 2 else ""
        print(f"invalid Conventional Commit pull request title: {title!r}", file=sys.stderr)
        print("example: feat(package-a): add JSON output", file=sys.stderr)
        return 1
    print(f"valid Conventional Commit pull request title: {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
