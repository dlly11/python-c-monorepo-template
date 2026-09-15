"""Isolated fixtures for repository orchestration scripts."""

from importlib import import_module
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def scripts(monkeypatch: pytest.MonkeyPatch) -> dict[str, ModuleType]:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    return {
        name: import_module(name)
        for name in (
            "check_versions",
            "set_version",
            "check_native_install",
            "check_pr_title",
            "check_commits",
            "check_release_readiness",
            "check_github_settings",
            "github_api",
            "check_python_install",
            "doctor",
            "check_workspace",
        )
    }


@pytest.fixture
def repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scripts: dict[str, ModuleType]
) -> Path:
    for name in ("check_versions", "set_version", "check_native_install"):
        monkeypatch.setattr(scripts[name], "ROOT", tmp_path)

    (tmp_path / "version.txt").write_text("1.2.3\n", encoding="utf-8")
    (tmp_path / "CMakeLists.txt").write_text(
        "project(example VERSION 1.2.3 LANGUAGES C)\n", encoding="utf-8"
    )
    packages = []
    for path, name in scripts["check_versions"].PROJECT_FILES.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'[project]\nname = "{name}"\nversion = "1.2.3"\n', encoding="utf-8")
        packages.append(f'[[package]]\nname = "{name}"\nversion = "1.2.3"\n')
    (tmp_path / "uv.lock").write_text("\n".join(packages), encoding="utf-8")
    return tmp_path
