"""Reuse PR checks only when the merged Git tree and complete CI evidence agree."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPOSITORY = "owner/project"


@pytest.fixture
def merge_context(
    scripts: dict[str, ModuleType], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ModuleType, dict[str, Any]]:
    module = scripts["check_merge"]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)

    def git(*arguments: str) -> str:
        return subprocess.check_output(
            ["git", *arguments], stderr=subprocess.DEVNULL, text=True
        ).strip()

    git("init", "--initial-branch=main")
    git("config", "user.name", "Merge tests")
    git("config", "user.email", "merge@example.invalid")
    source = tmp_path / "source.txt"
    source.write_text("before\n", encoding="utf-8")
    git("add", "source.txt")
    git("commit", "-m", "chore: initialize")
    base = git("rev-parse", "HEAD")
    source.write_text("after\n", encoding="utf-8")
    git("commit", "-am", "fix: change contents")
    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    merge = git("commit-tree", tree, "-p", base, "-m", "fix: change contents (#1)")
    git("update-ref", "refs/heads/main", merge)
    required = {
        check["context"]
        for check in module.load_policy()["protection"]["required_status_checks"]["checks"]
    } - {"Conventional PR title"}
    pr = {
        "number": 1,
        "merged_at": "2026-09-15T00:00:00Z",
        "merge_commit_sha": merge,
        "head": {"sha": head, "ref": "topic", "repo": {"full_name": REPOSITORY}},
        "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
    }
    run = {
        "id": 100,
        "workflow_id": 42,
        "path": ".github/workflows/ci.yml",
        "status": "completed",
        "conclusion": "success",
        "event": "pull_request",
        "head_sha": head,
        "head_branch": "topic",
        "repository": {"full_name": REPOSITORY},
        "pull_requests": [],
    }
    state: dict[str, Any] = {
        "base": base,
        "head": head,
        "merge": merge,
        "tree": tree,
        "pr": pr,
        "runs": [run],
        "candidates": [pr],
        "required": required,
        "git": git,
        "jobs": [
            {"name": name, "status": "completed", "conclusion": "success"} for name in required
        ],
        "evidence": {
            "schema": 1,
            "repository": REPOSITORY,
            "run_id": 100,
            "head_sha": head,
            "checkout_sha": head,
            "tree_sha": tree,
        },
    }

    def api(endpoint: str) -> dict[str, Any]:
        if endpoint.endswith("/pulls/1"):
            return state["pr"]
        if endpoint.endswith("/workflows/ci.yml"):
            return {"id": 42}
        return next(run for run in state["runs"] if endpoint.endswith(f"/runs/{run['id']}"))

    def items(endpoint: str, key: str | None = None) -> list[dict[str, Any]]:
        if "/commits/" in endpoint:
            return state["candidates"]
        return state["jobs"] if key == "jobs" else state["runs"]

    monkeypatch.setattr(module, "api", api)
    monkeypatch.setattr(module, "items", items)
    monkeypatch.setattr(module, "validation_record", lambda *args: state["evidence"])
    monkeypatch.setattr(sys, "argv", ["check_merge.py", "--base", base, "--head", merge])
    return module, state


def test_squash_sha_changes_but_tested_tree_matches(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = merge_context
    assert state["head"] != state["merge"]
    assert module.main() == 0


def test_manual_release_branch_ci_and_fork_pr_ci(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = merge_context
    state["runs"][0]["event"] = "workflow_dispatch"
    assert module.main() == 0
    state["pr"]["head"]["repo"]["full_name"] = "fork/project"
    assert module.main() == 1
    state["runs"][0]["event"] = "pull_request"
    assert module.main() == 0


@pytest.mark.parametrize("key", ["tree_sha", "head_sha", "run_id", "repository", "schema"])
def test_mismatched_validation_record_is_rejected(
    merge_context: tuple[ModuleType, dict[str, Any]], key: str
) -> None:
    module, state = merge_context
    state["evidence"][key] = "wrong"
    assert module.main() == 1


@pytest.mark.parametrize("change", ["missing", "skipped", "failed", "duplicate"])
def test_every_required_ci_job_must_actually_pass(
    merge_context: tuple[ModuleType, dict[str, Any]], change: str
) -> None:
    module, state = merge_context
    if change == "missing":
        state["jobs"].pop()
    elif change == "duplicate":
        state["jobs"].append(deepcopy(state["jobs"][0]))
    else:
        state["jobs"][0]["conclusion"] = change
    assert module.main() == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workflow_id", 99),
        ("path", "other.yml"),
        ("head_sha", "wrong"),
        ("status", "in_progress"),
        ("conclusion", "failure"),
        ("event", "push"),
        ("head_branch", "other"),
        ("repository", {"full_name": "other/project"}),
    ],
)
def test_wrong_or_unsuccessful_ci_run_is_rejected(
    merge_context: tuple[ModuleType, dict[str, Any]], field: str, value: object
) -> None:
    module, state = merge_context
    state["runs"][0][field] = value
    assert module.main() == 1


def test_new_failed_run_cannot_reuse_old_success(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = merge_context
    newer = deepcopy(state["runs"][0])
    newer.update(id=101, conclusion="failure")
    state["runs"].append(newer)
    assert module.main() == 1


def test_missing_or_ambiguous_pr_is_rejected(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = merge_context
    state["candidates"] = []
    assert module.main() == 1
    state["candidates"] = [state["pr"], state["pr"]]
    assert module.main() == 1


def test_missing_artifact_and_api_errors_fail_closed(
    merge_context: tuple[ModuleType, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, _ = merge_context

    def fail(*args: object) -> None:
        raise RuntimeError("artifact expired or unavailable")

    monkeypatch.setattr(module, "validation_record", fail)
    assert module.main() == 1


def test_rerun_started_during_download_is_rejected(
    merge_context: tuple[ModuleType, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, state = merge_context

    def download(*args: object) -> dict[str, Any]:
        state["runs"][0]["status"] = "in_progress"
        return state["evidence"]

    monkeypatch.setattr(module, "validation_record", download)
    assert module.main() == 1


def test_default_merge_message_and_non_squash_commit_are_rejected(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = merge_context
    git = state["git"]
    invalid = git("commit-tree", state["tree"], "-p", state["base"], "-m", "Update things")
    with pytest.raises(ValueError, match="subject"):
        module.verify_commit(REPOSITORY, invalid, state["required"], 42)
    merge = git(
        "commit-tree", state["tree"], "-p", state["base"], "-p", state["head"], "-m", "fix: merge"
    )
    with pytest.raises(ValueError, match="one parent"):
        module.verify_commit(REPOSITORY, merge, state["required"], 42)


def test_record_uses_actual_synthetic_merge_tree(
    merge_context: tuple[ModuleType, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, state = merge_context
    git = state["git"]
    synthetic = git(
        "commit-tree",
        state["tree"],
        "-p",
        state["base"],
        "-p",
        state["head"],
        "-m",
        "Synthetic PR merge",
    )
    git("checkout", "--detach", synthetic)
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"head": {"sha": state["head"]}}}), encoding="utf-8"
    )
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_RUN_ID", "100")
    monkeypatch.setenv("GITHUB_SHA", synthetic)
    output = tmp_path / "validation.json"
    module.record(output)
    record = json.loads(output.read_text())
    assert record["tree_sha"] == state["tree"]
    assert record["checkout_sha"] == synthetic
    assert record["head_sha"] == state["head"]
    monkeypatch.setenv("GITHUB_SHA", state["head"])
    with pytest.raises(ValueError, match="checkout"):
        module.record(output)


def test_metadata_download_selects_exact_run_and_reads_json(
    scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    module = scripts["check_merge"]

    def gh(*args: str) -> str:
        assert args[:6] == ("run", "download", "123", "--repo", REPOSITORY, "--name")
        (Path(args[-1]) / "validation.json").write_text('{"schema": 1}', encoding="utf-8")
        return ""

    monkeypatch.setattr(module, "gh", gh)
    assert module.validation_record(REPOSITORY, 123) == {"schema": 1}


def test_collection_reads_every_page(
    scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    module = scripts["github_api"]
    monkeypatch.setattr(module, "gh", lambda *args: '[[{"id":1}],[{"id":2}]]')
    assert module.items("endpoint") == [{"id": 1}, {"id": 2}]
    monkeypatch.setattr(module, "gh", lambda *args: '[{"jobs":[{"id":1}]},{"jobs":[{"id":2}]}]')
    assert module.items("endpoint", "jobs") == [{"id": 1}, {"id": 2}]


@pytest.mark.parametrize("base", ["0" * 40, "0" * 64])
def test_initialization_has_actionable_diagnostic(
    merge_context: tuple[ModuleType, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    base: str,
) -> None:
    module, state = merge_context
    monkeypatch.setattr(sys, "argv", ["check_merge.py", "--base", base, "--head", state["merge"]])
    assert module.main() == 1
    assert "initial branch creation has no merged PR" in capsys.readouterr().err


def test_recovery_record_requires_exact_checkout(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = merge_context
    state["evidence"]["head_sha"] = state["merge"]
    with pytest.raises(ValueError, match="checkout_sha"):
        module.check_evidence(REPOSITORY, 100, state["merge"], state["merge"], exact_checkout=True)
    state["evidence"]["checkout_sha"] = state["merge"]
    module.check_evidence(REPOSITORY, 100, state["merge"], state["merge"], exact_checkout=True)


@pytest.fixture
def recovery_context(
    merge_context: tuple[ModuleType, dict[str, Any]],
    scripts: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ModuleType, dict[str, Any]]:
    merge, state = merge_context
    release = scripts["check_release_readiness"]
    state["runs"][0].update(
        event="workflow_dispatch",
        head_branch="main",
        head_sha=state["merge"],
        head_repository={"full_name": REPOSITORY},
    )
    state["evidence"].update(head_sha=state["merge"], checkout_sha=state["merge"])
    state["current"] = state["merge"]
    state["event"] = {"inputs": {"recovery-run-id": "100"}}
    original = merge.api

    def api(endpoint: str) -> dict[str, Any]:
        if endpoint.endswith("/branches/main"):
            return {"commit": {"sha": state["current"]}}
        if "/runs?" in endpoint:
            assert "event=workflow_dispatch" in endpoint
            assert f"head_sha={state['merge']}" in endpoint
            return {"workflow_runs": state["runs"]}
        return original(endpoint)

    monkeypatch.setattr(release, "api", api)
    return release, state


def recover(module: ModuleType, state: dict[str, Any]) -> bool:
    return module.ready(
        "workflow_dispatch", state["event"], REPOSITORY, "refs/heads/main", state["merge"]
    )


def test_fresh_main_ci_recovers_without_original_pr_artifact(
    recovery_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = recovery_context
    assert recover(module, state)


@pytest.mark.parametrize("defect", ["missing", "skipped", "failure", "duplicate"])
def test_recovery_requires_all_quality_jobs(
    recovery_context: tuple[ModuleType, dict[str, Any]],
    defect: str,
) -> None:
    module, state = recovery_context
    if defect == "missing":
        state["jobs"].pop()
    elif defect == "duplicate":
        state["jobs"].append(deepcopy(state["jobs"][0]))
    else:
        state["jobs"][0]["conclusion"] = defect
    with pytest.raises(ValueError, match="required CI job"):
        recover(module, state)


@pytest.mark.parametrize(
    "field,value",
    [
        ("workflow_id", 99),
        ("event", "pull_request"),
        ("head_branch", "topic"),
        ("head_sha", "wrong"),
        ("status", "in_progress"),
        ("conclusion", "failure"),
        ("repository", {"full_name": "other/repo"}),
        ("head_repository", {"full_name": "fork/repo"}),
    ],
)
def test_recovery_rejects_wrong_or_unfinished_run(
    recovery_context: tuple[ModuleType, dict[str, Any]],
    field: str,
    value: object,
) -> None:
    module, state = recovery_context
    state["runs"][0][field] = value
    with pytest.raises(ValueError, match=field):
        recover(module, state)


@pytest.mark.parametrize("field", ["repository", "run_id", "head_sha", "checkout_sha", "tree_sha"])
def test_recovery_requires_matching_record(
    recovery_context: tuple[ModuleType, dict[str, Any]],
    field: str,
) -> None:
    module, state = recovery_context
    state["evidence"][field] = "wrong"
    with pytest.raises(ValueError, match=field):
        recover(module, state)


def test_recovery_rejects_expired_evidence(
    recovery_context: tuple[ModuleType, dict[str, Any]],
    scripts: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, state = recovery_context

    def expired(*args: object) -> None:
        raise RuntimeError("artifact expired")

    monkeypatch.setattr(scripts["check_merge"], "validation_record", expired)
    with pytest.raises(RuntimeError, match="expired"):
        recover(module, state)


@pytest.mark.parametrize("race", ["newer", "rerun", "main"])
def test_recovery_cannot_authorize_stale_evidence(
    recovery_context: tuple[ModuleType, dict[str, Any]],
    scripts: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    race: str,
) -> None:
    module, state = recovery_context

    def record(*args: object) -> dict[str, Any]:
        if race == "main":
            state["current"] = "b" * 40
        elif race == "rerun":
            state["runs"][0].update(status="in_progress", conclusion=None)
        else:
            newer = deepcopy(state["runs"][0])
            newer.update(id=101, conclusion="failure")
            state["runs"].append(newer)
        return state["evidence"]

    monkeypatch.setattr(scripts["check_merge"], "validation_record", record)
    with pytest.raises(ValueError):
        recover(module, state)


def test_recovery_rejects_older_run_and_non_pr_commits(
    recovery_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = recovery_context
    state["event"]["inputs"]["recovery-run-id"] = "99"
    with pytest.raises(ValueError, match="latest manual"):
        recover(module, state)
    state["event"]["inputs"]["recovery-run-id"] = "100"
    state["candidates"] = []
    with pytest.raises(ValueError, match="merged PR"):
        recover(module, state)


@pytest.mark.parametrize("value", ["-1", "0", "one", "1.0", True, False, 0, None])
def test_recovery_input_validation(
    recovery_context: tuple[ModuleType, dict[str, Any]],
    value: object,
) -> None:
    module, state = recovery_context
    state["event"]["inputs"]["recovery-run-id"] = value
    with pytest.raises(ValueError, match="positive run ID"):
        recover(module, state)


def test_bootstrap_root_cannot_use_recovery(
    recovery_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = recovery_context
    state["merge"] = state["base"]
    state["current"] = state["base"]
    state["runs"][0]["head_sha"] = state["base"]
    with pytest.raises(ValueError, match="squash commit with one parent"):
        recover(module, state)


def test_recovery_requires_manual_release_on_main(
    recovery_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = recovery_context
    with pytest.raises(ValueError, match="main branch"):
        module.ready(
            "workflow_dispatch", state["event"], REPOSITORY, "refs/heads/topic", state["merge"]
        )
    with pytest.raises(ValueError, match="manual Release"):
        module.ready("workflow_run", state["event"], REPOSITORY, "refs/heads/main", state["merge"])
