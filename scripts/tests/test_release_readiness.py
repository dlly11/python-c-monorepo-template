"""Release gating must use successful push CI for the current main commit."""

import json
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPOSITORY = "owner/project"
SHA = "a" * 40


@pytest.fixture
def release_context(
    scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> tuple[ModuleType, dict[str, Any]]:
    module = scripts["check_release_readiness"]
    run = {
        "id": 100,
        "workflow_id": 42,
        "path": ".github/workflows/ci.yml",
        "event": "push",
        "head_branch": "main",
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
    }
    state: dict[str, Any] = {
        "event": {"workflow_run": deepcopy(run)},
        "runs": [run],
        "head": SHA,
        "reads": [],
        "jobs": [
            {"name": "Merged PR verification", "status": "completed", "conclusion": "success"}
        ],
    }

    def api(endpoint: str) -> dict[str, Any]:
        state["reads"].append(endpoint)
        assert endpoint.startswith(f"repos/{REPOSITORY}/")
        if endpoint.endswith("/branches/main"):
            return {"commit": {"sha": state["head"]}}
        if endpoint.endswith("/workflows/ci.yml"):
            return {"id": 42}
        if "/runs?" in endpoint:
            assert f"head_sha={SHA}" in endpoint
            assert "event=push" in endpoint
            return {"workflow_runs": state["runs"]}
        return next(run for run in state["runs"] if endpoint.endswith(f"/runs/{run['id']}"))

    monkeypatch.setattr(module, "api", api)
    monkeypatch.setattr(module, "items", lambda *args: state["jobs"])
    return module, state


@pytest.mark.parametrize("event_name", ["workflow_run", "workflow_dispatch"])
def test_successful_current_push_authorizes_release(
    release_context: tuple[ModuleType, dict[str, Any]], event_name: str
) -> None:
    module, state = release_context
    assert module.ready(event_name, state["event"], REPOSITORY, "refs/heads/main", SHA)
    assert state["reads"].count(f"repos/{REPOSITORY}/branches/main") == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workflow_id", 99),
        ("path", ".github/workflows/other.yml"),
        ("event", "pull_request"),
        ("event", "workflow_dispatch"),
        ("head_branch", "topic"),
        ("head_sha", "b" * 40),
        ("status", "in_progress"),
        ("conclusion", "failure"),
        ("conclusion", "cancelled"),
        ("conclusion", "skipped"),
        ("repository", {"full_name": "other/project"}),
        ("head_repository", {"full_name": "fork/project"}),
    ],
)
def test_latest_run_must_match_all_release_requirements(
    release_context: tuple[ModuleType, dict[str, Any]], field: str, value: object
) -> None:
    module, state = release_context
    state["runs"][0][field] = value
    with pytest.raises(ValueError, match=field):
        module.ready("workflow_dispatch", {}, REPOSITORY, "refs/heads/main", SHA)


@pytest.mark.parametrize("field", ["event", "head_repository", "workflow_id"])
def test_automatic_event_is_checked_independently_of_latest_run(
    release_context: tuple[ModuleType, dict[str, Any]], field: str
) -> None:
    module, state = release_context
    state["event"]["workflow_run"][field] = None
    with pytest.raises(ValueError, match=field):
        module.ready("workflow_run", state["event"], REPOSITORY, "refs/heads/main", SHA)


def test_stale_automatic_run_skips_but_manual_run_fails(
    release_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = release_context
    state["head"] = "b" * 40
    assert not module.ready("workflow_run", state["event"], REPOSITORY, "refs/heads/main", SHA)
    with pytest.raises(ValueError, match="main is now"):
        module.ready("workflow_dispatch", {}, REPOSITORY, "refs/heads/main", SHA)


def test_old_success_cannot_override_new_failure_or_rerun(
    release_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = release_context
    newer = deepcopy(state["runs"][0])
    newer.update(id=101, status="in_progress", conclusion=None)
    state["runs"].insert(0, newer)
    with pytest.raises(ValueError, match="status"):
        module.ready("workflow_run", state["event"], REPOSITORY, "refs/heads/main", SHA)
    newer.update(status="completed", conclusion="failure")
    with pytest.raises(ValueError, match="conclusion"):
        module.ready("workflow_dispatch", {}, REPOSITORY, "refs/heads/main", SHA)


def test_main_advance_during_reads_prevents_release(
    release_context: tuple[ModuleType, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, state = release_context
    original = module.api

    def advance(endpoint: str) -> dict[str, Any]:
        result = original(endpoint)
        if endpoint.endswith("/runs/100"):
            state["head"] = "b" * 40
        return result

    monkeypatch.setattr(module, "api", advance)
    assert not module.ready("workflow_run", state["event"], REPOSITORY, "refs/heads/main", SHA)


def test_missing_ci_and_manual_non_main_are_rejected(
    release_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = release_context
    state["runs"] = []
    with pytest.raises(ValueError, match="no push CI"):
        module.ready("workflow_dispatch", {}, REPOSITORY, "refs/heads/main", SHA)
    with pytest.raises(ValueError, match="main branch"):
        module.ready("workflow_dispatch", {}, REPOSITORY, "refs/heads/topic", SHA)


@pytest.mark.parametrize("conclusion", ["missing", "skipped", "failure"])
def test_release_requires_actual_merge_verification(
    release_context: tuple[ModuleType, dict[str, Any]], conclusion: str
) -> None:
    module, state = release_context
    if conclusion == "missing":
        state["jobs"] = []
    else:
        state["jobs"][0]["conclusion"] = conclusion
    with pytest.raises(ValueError, match="Merged PR verification"):
        module.ready("workflow_dispatch", {}, REPOSITORY, "refs/heads/main", SHA)


@pytest.mark.parametrize("allowed", [True, False])
def test_step_output_records_decision(
    release_context: tuple[ModuleType, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    allowed: bool,
) -> None:
    module, state = release_context
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(state["event"]), encoding="utf-8")
    output_path = tmp_path / "output"
    for name, value in {
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_EVENT_PATH": str(event_path),
        "GITHUB_EVENT_NAME": "workflow_run",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SHA,
        "GITHUB_OUTPUT": str(output_path),
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(module, "ready", lambda *args: allowed)
    assert module.main() == 0
    assert output_path.read_text() == f"ready={str(allowed).lower()}\n"

    def fail(*args: object) -> None:
        raise RuntimeError("API unavailable")

    output_path.unlink()
    monkeypatch.setattr(module, "ready", fail)
    assert module.main() == 1
    assert not output_path.exists()


def test_initialization_never_authorizes_release(
    release_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = release_context
    state["jobs"][0]["conclusion"] = "skipped"
    assert not module.ready("workflow_run", state["event"], REPOSITORY, "refs/heads/main", SHA)
    with pytest.raises(ValueError, match="Merged PR verification"):
        module.ready("workflow_dispatch", {}, REPOSITORY, "refs/heads/main", SHA)
