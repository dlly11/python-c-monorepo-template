"""Audit GitHub policy drift without allowing remote writes."""

import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def settings_context(
    scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> tuple[ModuleType, dict[str, Any]]:
    module = scripts["check_github_settings"]
    policy = module.load_policy()
    state: dict[str, Any] = {
        "repository": deepcopy(policy["repository"]),
        "protection": deepcopy(policy["protection"]),
        "protected": True,
    }

    def api(endpoint: str) -> dict[str, Any]:
        assert endpoint.startswith("repos/owner/project")
        if endpoint.endswith("/protection"):
            return state["protection"]
        if endpoint.endswith("/branches/main"):
            return {"protected": state["protected"]}
        return state["repository"]

    monkeypatch.setattr(module, "api", api)
    monkeypatch.setattr(sys, "argv", ["check_github_settings.py", "--repo", "owner/project"])
    return module, state


def test_match_ignores_unmanaged_fields_and_check_order(
    settings_context: tuple[ModuleType, dict[str, Any]],
) -> None:
    module, state = settings_context
    state["repository"]["description"] = "Unmanaged description"
    state["protection"]["required_status_checks"]["checks"].reverse()
    assert module.main() == 0


@pytest.mark.parametrize(
    "change",
    ["merge", "merge_title", "linear", "protection", "missing", "additional", "source", "reviews"],
)
def test_reports_policy_drift(
    settings_context: tuple[ModuleType, dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
    change: str,
) -> None:
    module, state = settings_context
    checks = state["protection"]["required_status_checks"]["checks"]
    if change == "merge":
        state["repository"]["allow_merge_commit"] = False
    elif change == "merge_title":
        state["repository"]["merge_commit_title"] = "MERGE_MESSAGE"
    elif change == "linear":
        state["protection"]["required_linear_history"]["enabled"] = True
    elif change == "protection":
        state["protected"] = False
    elif change == "missing":
        checks.pop()
    elif change == "additional":
        checks.append({"context": "Unexpected check", "app_id": 15368})
    elif change == "source":
        checks[0]["app_id"] = -1
    else:
        state["protection"]["required_pull_request_reviews"] = None
    assert module.main() == 1
    assert "expected" in capsys.readouterr().err


def test_all_differences_are_reported(
    settings_context: tuple[ModuleType, dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    module, state = settings_context
    state["repository"].update(allow_merge_commit=False, allow_rebase_merge=False)
    assert module.main() == 1
    output = capsys.readouterr().err
    assert "allow_merge_commit" in output and "allow_rebase_merge" in output


def test_api_error_is_not_reported_as_drift(
    settings_context: tuple[ModuleType, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, _ = settings_context

    def fail(endpoint: str) -> None:
        raise RuntimeError("HTTP 403: missing Administration read permission")

    monkeypatch.setattr(module, "api", fail)
    assert module.main() == 2


@pytest.mark.parametrize("contents", ["{", "{}", '{"repository": {}, "protection": {}}'])
def test_invalid_policy_is_configuration_error(
    settings_context: tuple[ModuleType, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    contents: str,
    scripts: dict[str, ModuleType],
) -> None:
    module, _ = settings_context
    path = tmp_path / "policy.json"
    path.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(scripts["github_checks"], "POLICY", path)
    assert module.main() == 2


def test_duplicate_policy_checks_are_rejected(
    settings_context: tuple[ModuleType, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scripts: dict[str, ModuleType],
) -> None:
    module, _ = settings_context
    policy = module.load_policy()
    checks = policy["protection"]["required_status_checks"]["checks"]
    checks.append(checks[0])
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setattr(scripts["github_checks"], "POLICY", path)
    assert module.main() == 2
