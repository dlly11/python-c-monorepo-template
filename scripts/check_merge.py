"""Record tested PR contents and verify squash merges without repeating the test suite."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from check_commits import check_message, git
from check_github_settings import load_policy
from github_api import api, gh, items, repository_name

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


def verify_commit(repository: str, commit: str, required: set[str], workflow_id: int) -> None:
    """Bind one merged tree to a successful PR run and all required CI jobs."""
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
    pr = api(f"repos/{repository}/pulls/{candidates[0]['number']}")
    query = urlencode({"head_sha": pr["head"]["sha"], "per_page": 100})
    runs = items(
        f"repos/{repository}/actions/workflows/{workflow_id}/runs?{query}", "workflow_runs"
    )
    runs = [
        run
        for run in runs
        if run["event"] in {"pull_request", "workflow_dispatch"}
        and run["head_branch"] == pr["head"]["ref"]
    ]
    if not runs:
        raise ValueError(f"PR #{pr['number']}: no PR CI run found")
    run = api(f"repos/{repository}/actions/runs/{max(runs, key=lambda run: run['id'])['id']}")
    check_ci_run(run, repository, pr, workflow_id)
    jobs = items(
        f"repos/{repository}/actions/runs/{run['id']}/jobs?filter=latest&per_page=100", "jobs"
    )
    for name in sorted(required):
        matches = [job for job in jobs if job["name"] == name]
        if (
            len(matches) != 1
            or matches[0]["status"] != "completed"
            or matches[0]["conclusion"] != "success"
        ):
            raise ValueError(f"PR #{pr['number']}: required CI job {name!r} did not pass")
    evidence = validation_record(repository, run["id"])
    expected = {
        "schema": 1,
        "repository": repository,
        "run_id": run["id"],
        "head_sha": pr["head"]["sha"],
        "tree_sha": git("rev-parse", f"{commit}^{{tree}}").strip(),
    }
    for key, value in expected.items():
        if type(evidence.get(key)) is not type(value) or evidence.get(key) != value:
            raise ValueError(
                f"PR #{pr['number']}: validation {key} does not match the merged commit/run"
            )
    # A re-run may have started while the evidence was downloaded.
    check_ci_run(api(f"repos/{repository}/actions/runs/{run['id']}"), repository, pr, workflow_id)
    print(f"Verified {commit[:12]} matches PR #{pr['number']}'s tested tree, CI run {run['id']}.")


def main() -> int:
    """Record PR validation or check every new main commit against its tested PR."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--record", type=Path, help="write the PR validation record after quality checks"
    )
    mode.add_argument("--base", help="main commit before the push")
    parser.add_argument("--head", default="HEAD", help="main commit after the push")
    args = parser.parse_args()
    try:
        if args.record:
            record(args.record)
            return 0
        repository = repository_name(os.environ.get("GITHUB_REPOSITORY"))
        base = git("rev-parse", "--verify", "--end-of-options", f"{args.base}^{{commit}}").strip()
        head = git("rev-parse", "--verify", "--end-of-options", f"{args.head}^{{commit}}").strip()
        git("merge-base", "--is-ancestor", base, head)
        commits = git(
            "rev-list", "--reverse", "--first-parent", f"{base}..{head}", "--"
        ).splitlines()
        if not commits:
            raise ValueError("push verification requires at least one new main commit")
        policy = load_policy()
        required = {
            check["context"] for check in policy["protection"]["required_status_checks"]["checks"]
        }
        required.remove("Conventional PR title")  # Actual squash subjects are checked above.
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
            "For missing/expired evidence, rerun the original PR CI, then retry push CI.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
