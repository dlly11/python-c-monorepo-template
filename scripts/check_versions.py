"""Check that every release-bearing component uses the repository version."""

from __future__ import annotations

import argparse
import sys

from repository_metadata import ROOT, repository_version, version_errors


def main(argv: list[str] | None = None) -> int:
    """Run the version consistency check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="also require this release tag to equal v<version>")
    args = parser.parse_args(argv)

    try:
        expected = repository_version(ROOT)
        errors = version_errors(ROOT, expected, args.tag)
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(f"version check failed: {error}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"version check failed: {error}", file=sys.stderr)
        return 1

    print(f"all repository components use version {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
