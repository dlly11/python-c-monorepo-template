"""Version validation and transactional update regressions."""

import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


def snapshot(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_consistent_versions(repository: Path, scripts: dict[str, ModuleType]) -> None:
    checker = scripts["check_versions"]
    assert checker.repository_version(repository) == "1.2.3"
    assert checker.version_errors(repository, "1.2.3", "v1.2.3") == []


@pytest.mark.parametrize(
    "version", ["1.2", "01.2.3", "1.2.3-rc1", "garbage", "", "\u0661.\u0662.\u0663"]
)
def test_invalid_canonical_version(
    version: str, repository: Path, scripts: dict[str, ModuleType]
) -> None:
    (repository / "version.txt").write_text(version, encoding="utf-8")
    with pytest.raises(ValueError, match=r"must contain X\.Y\.Z"):
        scripts["check_versions"].repository_version(repository)


@pytest.mark.parametrize("relative_path", ["pyproject.toml", "CMakeLists.txt", "uv.lock"])
def test_stale_metadata(
    relative_path: str, repository: Path, scripts: dict[str, ModuleType]
) -> None:
    path = repository / relative_path
    path.write_text(path.read_text(encoding="utf-8").replace("1.2.3", "1.2.2"), encoding="utf-8")
    assert any(
        relative_path in error
        for error in scripts["check_versions"].version_errors(repository, "1.2.3")
    )


def test_missing_locked_projects(repository: Path, scripts: dict[str, ModuleType]) -> None:
    (repository / "uv.lock").write_text("package = []\n", encoding="utf-8")
    errors = scripts["check_versions"].version_errors(repository, "1.2.3")
    assert len(errors) == len(scripts["repository_metadata"].python_projects(repository))
    assert all("missing workspace project" in error for error in errors)


def test_wrong_tag(repository: Path, scripts: dict[str, ModuleType]) -> None:
    assert scripts["check_versions"].version_errors(repository, "1.2.3", "v1.2.2") == [
        "release tag: expected v1.2.3, found v1.2.2"
    ]


def test_malformed_metadata_is_reported(
    repository: Path,
    scripts: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (repository / "pyproject.toml").write_text("[broken", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_versions.py"])
    assert scripts["check_versions"].main() == 1
    assert "version check failed:" in capsys.readouterr().err


def test_set_version_success(
    repository: Path, scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    setter = scripts["set_version"]
    monkeypatch.setattr(sys, "argv", ["set_version.py", "2.0.0"])
    monkeypatch.setattr(setter.shutil, "which", lambda _: "/approved/bin/uv")

    def refresh_lock(*args: object, **kwargs: object) -> None:
        lock = repository / "uv.lock"
        lock.write_text(
            lock.read_text(encoding="utf-8").replace("1.2.3", "2.0.0"), encoding="utf-8"
        )

    run = Mock(side_effect=refresh_lock)
    monkeypatch.setattr(setter.subprocess, "run", run)
    assert setter.main() == 0
    run.assert_called_once_with(["uv", "lock"], cwd=repository, check=True)
    assert scripts["check_versions"].repository_version(repository) == "2.0.0"
    assert scripts["check_versions"].version_errors(repository, "2.0.0") == []


@pytest.mark.parametrize("failure", ["lock", "validation", "declaration", "interrupt"])
def test_failed_update_restores_every_managed_file(
    failure: str,
    repository: Path,
    scripts: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setter = scripts["set_version"]
    if failure == "declaration":
        (repository / "CMakeLists.txt").write_text("project(example)\n", encoding="utf-8")
    before = snapshot(repository)
    monkeypatch.setattr(sys, "argv", ["set_version.py", "2.0.0"])
    monkeypatch.setattr(setter.shutil, "which", lambda _: "/approved/bin/uv")

    def fail_lock(*args: object, **kwargs: object) -> None:
        (repository / "uv.lock").write_text("partial write\n", encoding="utf-8")
        if failure == "interrupt":
            raise KeyboardInterrupt
        raise subprocess.CalledProcessError(1, ["uv", "lock"])

    # Returning without refreshing the lock causes the real post-update checker to fail.
    run = Mock(side_effect=fail_lock if failure in {"lock", "interrupt"} else None)
    monkeypatch.setattr(setter.subprocess, "run", run)
    assert setter.main() == (130 if failure == "interrupt" else 1)
    assert snapshot(repository) == before
    if failure == "declaration":
        run.assert_not_called()


@pytest.mark.parametrize("missing_uv", [False, True])
def test_rejected_update_does_not_write(
    missing_uv: bool,
    repository: Path,
    scripts: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = snapshot(repository)
    monkeypatch.setattr(sys, "argv", ["set_version.py", "2.0.0" if missing_uv else "invalid"])
    monkeypatch.setattr(scripts["set_version"].shutil, "which", lambda _: None)
    with pytest.raises(SystemExit) as error:
        scripts["set_version"].main()
    assert error.value.code == 2
    assert snapshot(repository) == before


def test_new_member_is_discovered_by_version_setter_and_type_checks(
    repository: Path, scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    member = repository / "python/packages/added"
    namespace = member / "src/added"
    namespace.mkdir(parents=True)
    (namespace / "__init__.py").touch()
    metadata = member / "pyproject.toml"
    metadata.write_text('[project]\nname = "added"\nversion = "1.2.3"\n', encoding="utf-8")
    with (repository / "uv.lock").open("a") as lock:
        lock.write('[[package]]\nname = "added"\nversion = "1.2.3"\n')
    commands = []

    def run(command: list[str], **kwargs: object) -> None:
        commands.append(command)
        if command == ["uv", "lock"]:
            lock = repository / "uv.lock"
            lock.write_text(lock.read_text().replace("1.2.3", "2.0.0"), encoding="utf-8")

    monkeypatch.setattr(subprocess, "run", run)
    scripts["check_python"].check_projects(repository)
    assert ["ty", "check", "--project", str(member)] in commands
    scripts["set_version"].update_version(repository, "2.0.0")
    assert 'version = "2.0.0"' in metadata.read_text()
    assert scripts["repository_metadata"].version_errors(repository, "2.0.0") == []
