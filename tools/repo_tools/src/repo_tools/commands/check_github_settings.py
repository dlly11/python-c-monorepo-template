"""Audit managed GitHub settings against the checked-in policy without changing them."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

from repo_tools.github_api import api, repository_name
from repo_tools.github_checks import differences, load_policy


def build_parser() -> argparse.ArgumentParser:
    """Describe command arguments without performing any work."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="OWNER/REPO (default: current checkout's GitHub repository)")
    return parser


def execute(args: argparse.Namespace, *, root: Path | None = None) -> int:
    """Return 0 for matching settings, 1 for drift, and 2 for an unavailable audit."""
    try:
        policy = load_policy(root=root)
        repository = repository_name(args.repo, root=root)
        actual = api(f"repos/{repository}")
        errors = differences(policy["repository"], actual, "repository")
        branch = policy["repository"]["default_branch"]
        endpoint = f"repos/{repository}/branches/{quote(branch, safe='')}"
        branch_info = api(endpoint)
        if branch_info["protected"]:
            errors.extend(
                differences(policy["protection"], api(f"{endpoint}/protection"), "protection")
            )
        else:
            errors.append(f"protection: expected protected branch {branch!r}, found unprotected")
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"cannot audit GitHub settings: {error}", file=sys.stderr)
        return 2
    for error in errors:
        print(f"GitHub policy drift: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"Managed GitHub settings match policy for {repository}. No settings were changed.")
    return 0


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    """Parse arguments and run the command."""
    return execute(build_parser().parse_args(argv), root=root)
