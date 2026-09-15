"""Authorize Release Please only after push CI passes for the current main commit."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from github_api import api, repository_name


def check_run(run: dict[str, Any], repository: str, sha: str, workflow_id: int) -> None:
    """Reject runs that do not establish successful push CI for this commit."""
    expected = {
        "workflow_id": workflow_id,
        "path": ".github/workflows/ci.yml",
        "event": "push",
        "head_branch": "main",
        "head_sha": sha,
        "status": "completed",
        "conclusion": "success",
    }
    for field, value in expected.items():
        if run.get(field) != value:
            raise ValueError(f"CI {field}: expected {value!r}, found {run.get(field)!r}")
    for field in ("repository", "head_repository"):
        actual = (run.get(field) or {}).get("full_name")
        if actual != repository:
            raise ValueError(f"CI {field}: expected {repository!r}, found {actual!r}")


def ready(event_name: str, event: dict[str, Any], repository: str, ref: str, sha: str) -> bool:
    """Return false for obsolete automatic runs; reject all other ineligible runs."""
    automatic = event_name == "workflow_run"
    if event_name not in {"workflow_run", "workflow_dispatch"}:
        raise ValueError(f"unsupported release event: {event_name!r}")
    if not automatic and ref != "refs/heads/main":
        raise ValueError("manual releases must select the main branch")
    workflow = api(f"repos/{repository}/actions/workflows/ci.yml")
    workflow_id = workflow["id"]
    if automatic:
        run = event["workflow_run"]
        sha = run["head_sha"]
        check_run(run, repository, sha, workflow_id)

    branch_endpoint = f"repos/{repository}/branches/main"
    current_sha = api(branch_endpoint)["commit"]["sha"]
    if sha != current_sha:
        if automatic:
            print(f"Skipping stale release run for {sha}; main is now {current_sha}.")
            return False
        raise ValueError(
            f"manual run selected {sha}, but main is now {current_sha}; start a new run"
        )

    query = urlencode({"branch": "main", "event": "push", "head_sha": sha, "per_page": 100})
    runs = api(f"repos/{repository}/actions/workflows/{workflow_id}/runs?{query}")["workflow_runs"]
    if not runs:
        raise ValueError(f"no push CI run exists for main commit {sha}")
    # Do not filter by success: a newer failed or in-progress run invalidates an older success.
    latest = max(runs, key=lambda candidate: candidate["id"])
    latest = api(f"repos/{repository}/actions/runs/{latest['id']}")
    check_run(latest, repository, sha, workflow_id)
    if api(branch_endpoint)["commit"]["sha"] != sha:
        if automatic:
            print("Skipping release because main advanced during the readiness check.")
            return False
        raise ValueError("main advanced during the readiness check; start a new run")
    print(f"Release ready: push CI run {latest['id']} passed for main commit {sha}.")
    return True


def main() -> int:
    """Read GitHub's event context and emit a step output only after all checks pass."""
    try:
        repository = repository_name(os.environ["GITHUB_REPOSITORY"])
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        allowed = ready(
            os.environ["GITHUB_EVENT_NAME"],
            event,
            repository,
            os.environ["GITHUB_REF"],
            os.environ["GITHUB_SHA"],
        )
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"ready={str(allowed).lower()}\n")
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"release readiness failed: {error}", file=sys.stderr)
        print("Wait for successful push CI on current main, then retry Release.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
