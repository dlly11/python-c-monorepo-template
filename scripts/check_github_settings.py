"""Audit managed GitHub settings against the checked-in policy without changing them."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from github_api import api, repository_name

POLICY = Path(__file__).resolve().parents[1] / "tools/github/repository-policy.json"


def check_set(checks: list[dict[str, Any]]) -> set[str]:
    """Compare check identities independently of their API ordering."""
    return {f"{check['context']} (app_id={check.get('app_id')})" for check in checks}


def differences(expected: dict[str, Any], actual: dict[str, Any], prefix: str) -> list[str]:
    """Compare only managed keys and report all discrepancies together."""
    errors = []
    for key, wanted in expected.items():
        path = f"{prefix}.{key}"
        found = actual.get(key)
        if isinstance(wanted, dict) and isinstance(found, dict):
            errors.extend(differences(wanted, found, path))
        elif key == "checks" and isinstance(wanted, list) and isinstance(found, list):
            wanted_checks, found_checks = check_set(wanted), check_set(found)
            if wanted_checks != found_checks:
                errors.append(
                    f"{path}: expected {sorted(wanted_checks)!r}, found {sorted(found_checks)!r}"
                )
        elif type(wanted) is not type(found) or wanted != found:
            errors.append(f"{path}: expected {wanted!r}, found {found!r}")
    return errors


def load_policy() -> dict[str, Any]:
    """Reject incomplete policy files before attempting any GitHub reads."""
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or set(policy) != {"repository", "protection"}:
        raise ValueError("policy must contain repository and protection objects")
    if not all(isinstance(value, dict) and value for value in policy.values()):
        raise ValueError("policy sections must be nonempty objects")
    branch = policy["repository"].get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise ValueError("policy must specify a default_branch")
    checks = policy["protection"]["required_status_checks"]["checks"]
    if not isinstance(checks, list) or not checks:
        raise ValueError("policy must specify a nonempty required check list")
    for check in checks:
        if (
            not isinstance(check, dict)
            or set(check) != {"context", "app_id"}
            or not isinstance(check["context"], str)
            or not check["context"]
            or type(check["app_id"]) is not int
            or check["app_id"] <= 0
        ):
            raise ValueError("each required check must have a context and positive integer app_id")
    if len(check_set(checks)) != len(checks):
        raise ValueError("policy contains duplicate required checks")
    return policy


def main() -> int:
    """Return 0 for matching settings, 1 for drift, and 2 for an unavailable audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="OWNER/REPO (default: current checkout's GitHub repository)")
    args = parser.parse_args()
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
