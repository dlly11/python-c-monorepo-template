"""Reuse PR checks only when the merged Git tree and complete CI evidence agree."""

import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPOSITORY = "owner/project"


def test_squash_sha_changes_but_tested_tree_matches(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    _module, state = merge_context
    assert state["head"] != state["merge"]
    assert state["cli"].main() == 0


def test_manual_release_branch_ci_and_fork_pr_ci(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    _module, state = merge_context
    state["runs"][0]["event"] = "workflow_dispatch"
    assert state["cli"].main() == 0
    state["pr"]["head"]["repo"]["full_name"] = "fork/project"
    assert state["cli"].main() == 1
    state["runs"][0]["event"] = "pull_request"
    assert state["cli"].main() == 0


@pytest.mark.parametrize("key", ["tree_sha", "head_sha", "run_id", "repository", "schema"])
def test_mismatched_validation_record_is_rejected(
    merge_context: tuple[ModuleType, dict[str, Any]], key: str
) -> None:
    _module, state = merge_context
    state["evidence"][key] = "wrong"
    assert state["cli"].main() == 1


@pytest.mark.parametrize("change", ["missing", "skipped", "failed", "duplicate"])
def test_every_required_ci_job_must_actually_pass(
    merge_context: tuple[ModuleType, dict[str, Any]], change: str
) -> None:
    _module, state = merge_context
    if change == "missing":
        state["jobs"].pop()
    elif change == "duplicate":
        state["jobs"].append(deepcopy(state["jobs"][0]))
    else:
        state["jobs"][0]["conclusion"] = change
    assert state["cli"].main() == 1


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
    _module, state = merge_context
    state["runs"][0][field] = value
    assert state["cli"].main() == 1


def test_new_failed_run_cannot_reuse_old_success(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    _module, state = merge_context
    newer = deepcopy(state["runs"][0])
    newer.update(id=101, conclusion="failure")
    state["runs"].append(newer)
    assert state["cli"].main() == 1


def test_missing_or_ambiguous_pr_is_rejected(
    merge_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    _module, state = merge_context
    state["candidates"] = []
    assert state["cli"].main() == 1
    state["candidates"] = [state["pr"], state["pr"]]
    assert state["cli"].main() == 1


def test_missing_artifact_and_api_errors_fail_closed(
    merge_context: tuple[ModuleType, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, state = merge_context

    def fail(*args: object) -> None:
        raise RuntimeError("artifact expired or unavailable")

    monkeypatch.setattr(module, "validation_record", fail)
    assert state["cli"].main() == 1


def test_rerun_started_during_download_is_rejected(
    merge_context: tuple[ModuleType, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, state = merge_context

    def download(*args: object) -> dict[str, Any]:
        state["runs"][0]["status"] = "in_progress"
        return state["evidence"]

    monkeypatch.setattr(module, "validation_record", download)
    assert state["cli"].main() == 1


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
    module = scripts["github_checks"]

    def gh(*args: str) -> str:
        assert args[:6] == ("run", "download", "123", "--repo", REPOSITORY, "--name")
        (Path(args[-1]) / "validation.json").write_text('{"schema": 1}', encoding="utf-8")
        return ""

    monkeypatch.setattr(module, "gh", gh)
    assert module.validation_record(REPOSITORY, 123) == {"schema": 1}


@pytest.mark.parametrize("base", ["0" * 40, "0" * 64])
def test_initialization_has_actionable_diagnostic(
    merge_context: tuple[ModuleType, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    base: str,
) -> None:
    _module, state = merge_context
    monkeypatch.setattr(sys, "argv", ["check_merge.py", "--base", base, "--head", state["merge"]])
    assert state["cli"].main() == 1
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


@pytest.mark.parametrize("conclusion", ["success", "failure", None])
def test_new_run_during_download_invalidates_selected_evidence(
    merge_context: tuple[ModuleType, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    conclusion: str | None,
) -> None:
    module, state = merge_context

    def download(*args: object) -> dict[str, Any]:
        newer = deepcopy(state["runs"][0])
        newer.update(id=101, conclusion=conclusion)
        state["runs"].append(newer)
        return state["evidence"]

    monkeypatch.setattr(module, "validation_record", download)
    with pytest.raises(ValueError, match="newer PR CI run"):
        module.verify_commit(REPOSITORY, state["merge"], state["required"], 42)
