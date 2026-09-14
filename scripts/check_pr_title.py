"""Validate a pull request title as a Conventional Commit subject."""

from __future__ import annotations

import re
import sys

TITLE_PATTERN = re.compile(
    r"(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?!?: .+"
)


def main() -> int:
    """Validate the title passed on the command line."""
    if len(sys.argv) != 2 or TITLE_PATTERN.fullmatch(sys.argv[1]) is None:
        title = sys.argv[1] if len(sys.argv) == 2 else ""
        print(f"invalid Conventional Commit pull request title: {title!r}", file=sys.stderr)
        print("example: feat(package-a): add JSON output", file=sys.stderr)
        return 1
    print(f"valid Conventional Commit pull request title: {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
