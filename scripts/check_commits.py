"""Validate a commit-message file or every commit introduced by a Git revision range."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from conventional_commits import valid_subject


def git(*arguments: str) -> str:
    """Read Git metadata without shell interpretation or signature output."""
    return subprocess.run(
        ["git", "-c", "log.showSignature=false", *arguments],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout


def commits_between(base: str, head: str) -> list[str]:
    """Resolve refs first; an all-zero push base denotes a newly created branch."""
    head_sha = git("rev-parse", "--verify", "--end-of-options", f"{head}^{{commit}}").strip()
    if base in {"0" * 40, "0" * 64}:
        revision_range = head_sha
    else:
        base_sha = git("rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}").strip()
        revision_range = f"{base_sha}..{head_sha}"
    return git("rev-list", "--reverse", revision_range, "--").splitlines()


def check_message(message: str, label: str) -> bool:
    """Check only the subject; bodies and release footers remain free-form."""
    subject = message.split("\n", 1)[0]
    if valid_subject(subject):
        return True
    print(f"invalid Conventional Commit subject ({label}): {subject!r}", file=sys.stderr)
    print("example: feat(package-a): add JSON output", file=sys.stderr)
    return False


def main() -> int:
    """Support the commit-msg hook and CI without additional dependencies."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message-file", type=Path, help="message file supplied by commit-msg")
    source.add_argument("--base", help="exclude commits reachable from this ref or SHA")
    parser.add_argument("--head", default="HEAD", help="last commit to check (default: HEAD)")
    args = parser.parse_args()
    try:
        if args.message_file is not None:
            return int(
                not check_message(
                    args.message_file.read_text(encoding="utf-8"), str(args.message_file)
                )
            )
        commits = commits_between(args.base, args.head)
        failures = 0
        for commit in commits:
            message = git("show", "--no-patch", "--format=%B", commit, "--")
            failures += not check_message(message, commit[:12])
        print(f"Checked {len(commits)} commit(s); {failures} invalid subject(s).")
        return int(failures != 0)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        print(f"cannot validate commits: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
