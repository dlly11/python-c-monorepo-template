"""Shared read-only GitHub policy and CI evidence checks."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from conventional_commits import check_message
from github_api import api, gh, items, repository_name
from repository_metadata import git

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


ARTIFACT = "pr-validation"


def record(path: Path) -> None:
    """Record the actual checkout used by this CI run, including synthetic PR merges."""
    event_name = os.environ["GITHUB_EVENT_NAME"]
    if event_name not in {"pull_request", "workflow_dispatch"}:
        raise ValueError("validation records can only be produced by PR or manual CI")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    head = (
        event["pull_request"]["head"]["sha"]
        if event_name == "pull_request"
        else os.environ["GITHUB_SHA"]
    )
    checkout = git("rev-parse", "HEAD").strip()
    if checkout != os.environ["GITHUB_SHA"]:
        raise ValueError("checkout does not match the workflow commit")
    git("diff", "--exit-code", "HEAD", "--")
    data = {
        "schema": 1,
        "repository": repository_name(os.environ["GITHUB_REPOSITORY"]),
        "run_id": int(os.environ["GITHUB_RUN_ID"]),
        "head_sha": head,
        "checkout_sha": checkout,
        "tree_sha": git("rev-parse", "HEAD^{tree}").strip(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded tested tree {data['tree_sha']} for CI run {data['run_id']}.")


def validation_record(repository: str, run_id: int) -> dict[str, Any]:
    """Read only the JSON record from the selected workflow run's artifact."""
    with tempfile.TemporaryDirectory(prefix="pr-validation-") as directory:
        gh(
            "run",
            "download",
            str(run_id),
            "--repo",
            repository,
            "--name",
            ARTIFACT,
            "--dir",
            directory,
        )
        path = Path(directory) / "validation.json"
        if path.stat().st_size > 65536:
            raise ValueError("PR validation record is unexpectedly large")
        data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("PR validation record must be a JSON object")
    return data


def check_ci_run(
    run: dict[str, Any], repository: str, pr: dict[str, Any], workflow_id: int
) -> None:
    """Require a successful run of this repository's CI for the original PR head."""
    expected = {
        "workflow_id": workflow_id,
        "path": ".github/workflows/ci.yml",
        "head_sha": pr["head"]["sha"],
        "status": "completed",
        "conclusion": "success",
    }
    for key, value in expected.items():
        if run.get(key) != value:
            raise ValueError(f"PR CI {key}: expected {value!r}, found {run.get(key)!r}")
    if run["repository"]["full_name"] != repository:
        raise ValueError("PR CI ran in a different repository")
    # GitHub clears run.pull_requests after merging. Bind the immutable head and recorded tree
    # instead, while checking the original branch and the repository that ran the workflow.
    if run["head_branch"] != pr["head"]["ref"]:
        raise ValueError("PR CI ran on a different head branch")
    if run["event"] == "workflow_dispatch":
        if (pr["head"]["repo"] or {}).get("full_name") != repository:
            raise ValueError("manual CI must run on the PR head branch in this repository")
    elif run["event"] != "pull_request":
        raise ValueError(f"unsupported PR CI event: {run['event']!r}")


def merged_pr(repository: str, commit: str) -> dict[str, Any]:
    """Require a conventional squash commit associated with one merged main PR."""
    if len(git("show", "--no-patch", "--format=%P", commit, "--").split()) != 1:
        raise ValueError(f"{commit}: expected a squash commit with one parent")
    if not check_message(git("show", "--no-patch", "--format=%B", commit, "--"), commit[:12]):
        raise ValueError("merged commit subject is not conventional")
    candidates = items(f"repos/{repository}/commits/{commit}/pulls?per_page=100")
    candidates = [
        pr
        for pr in candidates
        if pr.get("merged_at")
        and pr.get("merge_commit_sha") == commit
        and pr["base"]["ref"] == "main"
        and pr["base"]["repo"]["full_name"] == repository
    ]
    if len(candidates) != 1:
        raise ValueError(f"{commit}: expected exactly one merged PR targeting main")
    return api(f"repos/{repository}/pulls/{candidates[0]['number']}")


def required_ci_jobs() -> set[str]:
    """Read the required CI job names; final subjects replace the separate title check."""
    required = {
        check["context"]
        for check in load_policy()["protection"]["required_status_checks"]["checks"]
    }
    required.remove("Conventional PR title")
    return required


def check_jobs(repository: str, run_id: int, required: set[str]) -> None:
    """Require every quality job to have actually succeeded, including partial reruns."""
    jobs = items(
        f"repos/{repository}/actions/runs/{run_id}/jobs?filter=latest&per_page=100", "jobs"
    )
    for name in sorted(required):
        matches = [job for job in jobs if job["name"] == name]
        if (
            len(matches) != 1
            or matches[0]["status"] != "completed"
            or matches[0]["conclusion"] != "success"
        ):
            raise ValueError(f"CI run {run_id}: required CI job {name!r} did not pass")


def check_evidence(
    repository: str, run_id: int, head: str, commit: str, *, exact_checkout: bool = False
) -> None:
    """Bind the recorded tested tree to a commit; recovery also binds the checkout SHA."""
    evidence = validation_record(repository, run_id)
    expected = {
        "schema": 1,
        "repository": repository,
        "run_id": run_id,
        "head_sha": head,
        "tree_sha": git("rev-parse", f"{commit}^{{tree}}").strip(),
    }
    if exact_checkout:
        expected["checkout_sha"] = commit
    for key, value in expected.items():
        if type(evidence.get(key)) is not type(value) or evidence.get(key) != value:
            raise ValueError(f"CI run {run_id}: validation {key} does not match the commit/run")


def verify_commit(repository: str, commit: str, required: set[str], workflow_id: int) -> None:
    """Bind one merged tree to a successful PR run and all required CI jobs."""
    pr = merged_pr(repository, commit)
    query = urlencode({"head_sha": pr["head"]["sha"], "per_page": 100})
    endpoint = f"repos/{repository}/actions/workflows/{workflow_id}/runs?{query}"

    def newest_run_id() -> int:
        runs = [
            run
            for run in items(endpoint, "workflow_runs")
            if run["event"] in {"pull_request", "workflow_dispatch"}
            and run["head_branch"] == pr["head"]["ref"]
        ]
        if not runs:
            raise ValueError(f"PR #{pr['number']}: no PR CI run found")
        return max(run["id"] for run in runs)

    run = api(f"repos/{repository}/actions/runs/{newest_run_id()}")
    check_ci_run(run, repository, pr, workflow_id)
    check_jobs(repository, run["id"], required)
    check_evidence(repository, run["id"], pr["head"]["sha"], commit)
    # A re-run may have started while the evidence was downloaded.
    check_ci_run(api(f"repos/{repository}/actions/runs/{run['id']}"), repository, pr, workflow_id)
    if newest_run_id() != run["id"]:
        raise ValueError("a newer PR CI run started during merge verification")
    print(f"Verified {commit[:12]} matches PR #{pr['number']}'s tested tree, CI run {run['id']}.")
