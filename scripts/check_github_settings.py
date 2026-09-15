"""Audit managed GitHub settings against the checked-in policy without changing them."""

from __future__ import annotations

import argparse
import sys
from urllib.parse import quote

from github_api import api, repository_name
from github_checks import differences, load_policy


def main(argv: list[str] | None = None) -> int:
    """Return 0 for matching settings, 1 for drift, and 2 for an unavailable audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="OWNER/REPO (default: current checkout's GitHub repository)")
    args = parser.parse_args(argv)
    try:
        policy = load_policy()
        repository = repository_name(args.repo)
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


if __name__ == "__main__":
    raise SystemExit(main())
