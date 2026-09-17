"""Independent ownership, version updates, scopes, and release output contracts."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from repo_tools import cli
from repo_tools.commands import release_assets, set_version
from repo_tools.components import CONFIG, MANIFEST, component_errors, load_components
from repo_tools.conventional_commits import check_message, scope_policy, subject_errors
from repo_tools.release_changes import release_changes


def add_native(root: Path) -> None:
    directory = root / "native/packages/core"
    directory.mkdir(parents=True)
    (directory / "CMakeLists.txt").write_text("# native build\n")
    (directory / "version.txt").write_text("1.2.3\n")
    (directory / "CHANGELOG.md").write_text("# Changelog\n\n## 1.2.3\n\nInitial.\n")
    config = json.loads((root / CONFIG).read_text())
    config["packages"]["native/packages/core"] = {
        "component": "native-core",
        "release-type": "simple",
    }
    config["packages"]["."]["exclude-paths"].append("native/packages/core")
    (root / CONFIG).write_text(json.dumps(config))
    manifest = json.loads((root / MANIFEST).read_text())
    manifest["native/packages/core"] = "1.2.3"
    (root / MANIFEST).write_text(json.dumps(manifest))


def bump(root: Path, identifier: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def refresh(*args, **kwargs):
        lock = root / "uv.lock"
        name = "sample-template" if identifier == "template" else "sample-core"
        lock.write_text(
            lock.read_text().replace(
                f'name = "{name}"\nversion = "1.2.3"', f'name = "{name}"\nversion = "1.3.0"'
            )
        )

    with monkeypatch.context() as patched:
        patched.setattr(set_version.subprocess, "run", refresh)
        set_version.update_version(root, "1.3.0", identifier)
    component = next(c for c in load_components(root) if c.id == identifier)
    changelog = root / component.changelog
    changelog.write_text(
        changelog.read_text().replace(
            "# Changelog\n\n", "# Changelog\n\n## [1.3.0](url) (2026-09-18)\n\nChanges.\n\n"
        )
    )


@pytest.mark.parametrize(
    "identifiers",
    [
        ["python-core"],
        ["native-core"],
        ["template"],
        ["python-core", "native-core"],
        ["template", "python-core", "native-core"],
    ],
)
def test_independent_release_subset(independent_repository, monkeypatch, git, identifiers):
    root = independent_repository
    add_native(root)
    monkeypatch.chdir(root)
    git("init", "--initial-branch=main")
    git("add", ".")
    git("commit", "-m", "chore: initial")
    base = git("rev-parse", "HEAD")
    for identifier in identifiers:
        bump(root, identifier, monkeypatch)
    git("commit", "-am", "chore: release main")
    assert component_errors(root) == []
    assert release_changes(root, base, git("rev-parse", "HEAD"))[0]
    for component in load_components(root):
        assert component.version(root) == ("1.3.0" if component.id in identifiers else "1.2.3")


@pytest.mark.parametrize(
    "tamper", ["source", "dependency", "scope", "old-notes", "unchanged-notes", "manifest", "mode"]
)
def test_component_release_rejects_extra_changes(independent_repository, monkeypatch, git, tamper):
    root = independent_repository
    monkeypatch.chdir(root)
    git("init", "--initial-branch=main")
    git("add", ".")
    git("commit", "-m", "chore: initial")
    base = git("rev-parse", "HEAD")
    bump(root, "python-core", monkeypatch)
    files = {
        "source": "python/packages/core/src/sample_core/__init__.py",
        "dependency": "uv.lock",
        "scope": "pyproject.toml",
        "old-notes": "python/packages/core/CHANGELOG.md",
        "unchanged-notes": "CHANGELOG.md",
        "manifest": MANIFEST,
    }
    if tamper == "mode":
        git("add", ".")
        git("update-index", "--chmod=+x", "uv.lock")
    else:
        path = root / files[tamper]
        if tamper == "manifest":
            data = json.loads(path.read_text())
            data["."] = "9.0.0"
            path.write_text(json.dumps(data))
        else:
            path.write_text(path.read_text() + "\n# extra change\n")
            # Lock whitespace/comments are harmless; alter a semantic field instead.
            if tamper == "dependency":
                path.write_text(path.read_text() + 'dependencies = [{name = "external"}]\n')
        git("add", ".")
    git("commit", "-m", "chore: release main")
    assert not release_changes(root, base, git("rev-parse", "HEAD"))[0]


def test_empty_or_decreasing_release_rejected(independent_repository, monkeypatch, git):
    root = independent_repository
    monkeypatch.chdir(root)
    git("init", "--initial-branch=main")
    git("add", ".")
    git("commit", "-m", "chore: initial")
    base = git("rev-parse", "HEAD")
    assert not release_changes(root, base, base)[0]
    bump(root, "python-core", monkeypatch)
    git("commit", "-am", "chore: release main")
    assert not release_changes(root, git("rev-parse", "HEAD"), base)[0]


def test_scope_policy_and_mistakes(independent_repository, capsys):
    scopes = scope_policy(independent_repository)
    assert scopes and scopes["python-core"] == "python/packages/core"
    assert not subject_errors("fix: cross component change", scopes)
    assert not subject_errors("fix(python-core): change", scopes)
    assert "perhaps python-core" in subject_errors("fix(python-coree): change", scopes)[0]
    assert cli.main(["list-scopes"], default_root=independent_repository) == 0
    assert "python/packages/core" in capsys.readouterr().out


def test_scope_policy_from_member_directory(independent_repository, monkeypatch):
    monkeypatch.chdir(independent_repository / "python/packages/core")
    assert not check_message("fix(typo): change", "local")
    assert cli.main(["check-pr-title", "fix(typo): change"]) == 1


def test_historical_and_renamed_scopes(independent_repository, monkeypatch, git):
    root = independent_repository
    monkeypatch.chdir(root)
    git("init", "--initial-branch=main")
    git("add", ".")
    git("commit", "-m", "fix(python-core): change")
    old = git("rev-parse", "HEAD")
    config = root / CONFIG
    config.write_text(config.read_text().replace("python-core", "python-renamed"))
    git("commit", "-am", "refactor(python-core): rename component")
    renamed = git("rev-parse", "HEAD")
    assert check_message("fix(python-core): change", "old", root=root, revision=old)
    assert check_message(
        "refactor(python-core): rename component", "rename", root=root, revision=renamed
    )
    assert not check_message("fix(python-core): new change", "new", root=root)


@pytest.mark.parametrize("change", ["duplicate", "collision", "missing"])
def test_invalid_scope_registration(independent_repository, change):
    project = independent_repository / "pyproject.toml"
    text = project.read_text()
    if change == "missing":
        text = text.split("[tool.repo-tools.conventional-commits]")[0]
    else:
        text = text.replace(
            '"ci", "docs"', '"ci", "ci"' if change == "duplicate" else '"ci", "python-core"'
        )
    project.write_text(text)
    with pytest.raises(ValueError):
        scope_policy(independent_repository)


def test_release_plan(independent_repository):
    output = {
        "paths_released": '["python/packages/core"]',
        "python/packages/core--version": "1.3.0",
        "python/packages/core--tag_name": "python-core-v1.3.0",
        "python/packages/core--sha": "a" * 40,
        "python/packages/core--release_created": "true",
    }
    assert release_assets.release_plan(independent_repository, output) == [
        {
            "path": "python/packages/core",
            "component": "python-core",
            "kind": "python",
            "version": "1.3.0",
            "tag": "python-core-v1.3.0",
            "sha": "a" * 40,
        }
    ]
    assert release_assets.release_plan(independent_repository, {}) == []
    for key, value in [
        ("paths_released", '["unknown"]'),
        ("paths_released", '[".", "."]'),
        ("python/packages/core--version", "01.3.0"),
        ("python/packages/core--sha", "a" * 41),
        ("python/packages/core--tag_name", "other-v1.3.0"),
        ("python/packages/core--release_created", "false"),
    ]:
        with pytest.raises(ValueError):
            release_assets.release_plan(independent_repository, {**output, key: value})


def test_native_setter_does_not_need_uv(independent_repository, monkeypatch):
    add_native(independent_repository)
    monkeypatch.setattr(set_version.shutil, "which", lambda _: None)
    run = Mock()
    monkeypatch.setattr(set_version.subprocess, "run", run)
    assert (
        cli.main(["set-version", "native-core", "1.3.0"], default_root=independent_repository) == 0
    )
    run.assert_not_called()
    assert component_errors(independent_repository) == []


def test_publish_routes_only_released_python_product(independent_repository, monkeypatch):
    import shutil

    root = independent_repository
    uploads = []
    builds = []

    def run(cwd, *command):
        if command[:3] == ("git", "worktree", "add"):
            checkout = Path(command[4])
            shutil.copytree(root, checkout)
        elif command[:2] == ("uv", "build"):
            builds.append(cwd)
            dist = cwd / "dist"
            dist.mkdir()
            for name in ("sample_core", "unreleased_sibling"):
                (dist / f"{name}-1.2.3-py3-none-any.whl").touch()
                (dist / f"{name}-1.2.3.tar.gz").touch()
        elif command[:3] == ("gh", "release", "upload"):
            uploads.append(command)

    monkeypatch.setattr(release_assets, "run", run)
    monkeypatch.setattr(release_assets, "git", lambda *args, **kwargs: "a" * 40)
    release = {
        "path": "python/packages/core",
        "component": "python-core",
        "kind": "python",
        "tag": "python-core-v1.2.3",
        "version": "1.2.3",
        "sha": "a" * 40,
    }
    release_assets.publish(root, [release], "python")
    assert len(builds) == len(uploads) == 1
    assert uploads[0][3] == release["tag"]
    assert {Path(name).name for name in uploads[0][4:-1]} == {
        "sample_core-1.2.3-py3-none-any.whl",
        "sample_core-1.2.3.tar.gz",
    }
    monkeypatch.setattr(release_assets, "git", lambda *args, **kwargs: "b" * 40)
    with pytest.raises(ValueError, match="tag moved"):
        release_assets.publish(root, [release], "python")
    assert len(builds) == 1


@pytest.mark.parametrize("name", ["", "template"])
def test_root_retains_local_scope_and_tag(independent_repository: Path, name: str) -> None:
    config_path = independent_repository / CONFIG
    config = json.loads(config_path.read_text())
    config["packages"]["."].update({"component": name, "package-name": ""})
    config_path.write_text(json.dumps(config))
    root = next(c for c in load_components(independent_repository) if c.path == ".")
    assert root.id == "template"
    assert root.tag("1.2.3") == "v1.2.3"
    policy = scope_policy(independent_repository)
    assert policy is not None and policy["template"] == "."
    assert component_errors(independent_repository) == []
