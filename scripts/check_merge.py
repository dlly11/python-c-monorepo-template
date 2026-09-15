"""Record tested PR contents and verify squash or merge commits without repeating tests."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from github_api import api, repository_name
from github_checks import record, required_ci_jobs, verify_commit
from repository_metadata import git


def main(argv: list[str] | None = None) -> int:
    """Record PR validation or check each new first-parent main commit against its PR."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--record", type=Path, help="write the PR validation record after quality checks"
    )
    mode.add_argument("--base", help="main commit before the push")
    parser.add_argument("--head", default="HEAD", help="main commit after the push")
    args = parser.parse_args(argv)
    try:
        if args.record:
            record(args.record)
            return 0
        if args.base in {"0" * 40, "0" * 64}:
            raise ValueError(
                "initial branch creation has no merged PR to verify; run bootstrap quality "
                "checks and submit setup changes through a protected PR before releasing"
            )
        repository = repository_name(os.environ.get("GITHUB_REPOSITORY"))
        base = git("rev-parse", "--verify", "--end-of-options", f"{args.base}^{{commit}}").strip()
        head = git("rev-parse", "--verify", "--end-of-options", f"{args.head}^{{commit}}").strip()
        git("merge-base", "--is-ancestor", base, head)
        commits = git(
            "rev-list", "--reverse", "--first-parent", f"{base}..{head}", "--"
        ).splitlines()
        if not commits:
            raise ValueError("push verification requires at least one new main commit")
        required = required_ci_jobs()
        workflow_id = api(f"repos/{repository}/actions/workflows/ci.yml")["id"]
        for commit in commits:
            verify_commit(repository, commit, required, workflow_id)
    except (
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"merge verification failed: {error}", file=sys.stderr)
        print(
            "For missing evidence, retry PR CI within 30 days of its initial run. Otherwise, "
            "run fresh CI on main and use Release recovery-run-id; see docs/testing.md.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
