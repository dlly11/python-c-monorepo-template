"""Configuration, rendering, and safe output behavior."""

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from template_creator import cli, generate
from template_creator import snapshot as snapshots
from template_creator.config import LICENSES, Config, load, save, serialize, validate
from template_creator.render import license_text, render, without_creator
from template_creator.snapshot import Snapshot, pack, safe_name
from template_creator.wizard import wizard


def test_config_round_trip(tmp_path: Path, config: Config, snapshot: Snapshot) -> None:
    path = tmp_path / "recipe.toml"
    save(config, path)
    assert load(path, snapshot) == config
    with pytest.raises(FileExistsError):
        save(config, path)
    assert config.cmake_package == "AcmeLab"
    assert config.distribution_prefix == "acme-lab"


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("project", "prefix", "../evil"),
        ("project", "prefix", "class"),
        ("project", "prefix", "con"),
        ("project", "prefix", "example"),
        ("project", "slug", "acme-lab-core"),
        ("project", "version", "01.0.0"),
        ("project", "name", "first\nsecond"),
        ("github", "owner", "../owner"),
        ("github", "repository", "different"),
        ("github", "docs_url", "http://unsafe.invalid"),
        ("github", "docs_url", "https://user:secret@host.invalid/"),
        ("author", "email", "not-an-email"),
        ("security", "contact", "ftp://invalid"),
        ("ownership", "default", []),
        ("ownership", "default", ["organization"]),
        ("ownership", "rules", [{"pattern": "!ignored", "owners": ["@ada"]}]),
        ("ownership", "rules", "wrong"),
        ("license", "year", True),
        ("license", "choice", "unknown"),
        ("license", "text", "unexpected"),
        ("template", "digest", "wrong"),
    ],
)
def test_invalid_config(
    recipe: dict[str, Any], snapshot: Snapshot, section: str, key: str, value: Any
) -> None:
    recipe[section][key] = value
    with pytest.raises(ValueError):
        validate(recipe, snapshot)


@pytest.mark.parametrize("change", ["top", "nested", "schema", "missing"])
def test_unknown_fields(recipe: dict[str, Any], snapshot: Snapshot, change: str) -> None:
    if change == "top":
        recipe["typo"] = "value"
    elif change == "nested":
        recipe["author"]["typo"] = "value"
    elif change == "schema":
        recipe["schema_version"] = 2
    else:
        del recipe["author"]
    with pytest.raises(ValueError):
        validate(recipe, snapshot)


@pytest.mark.parametrize("choice", LICENSES)
def test_licenses(recipe: dict[str, Any], snapshot: Snapshot, choice: str) -> None:
    recipe["license"]["choice"] = choice
    recipe["license"]["text"] = "Custom terms: {{ untouched }}" if choice == "Custom" else ""
    config = validate(recipe, snapshot)
    text = license_text(config)
    assert "[year]" not in text and "[fullname]" not in text and "[yyyy]" not in text
    files = render(snapshot, config)
    assert files["LICENSE"].decode() == text
    for path, content in files.items():
        if path.endswith("pyproject.toml"):
            metadata = tomllib.loads(content.decode())["project"]
            assert metadata["license-files"] == ["LICENSE"]
            assert metadata["authors"] == [recipe["author"]]


def test_render_consistency(config: Config, snapshot: Snapshot) -> None:
    files = render(snapshot, config)
    assert files["uv.lock"] == snapshot.files["uv.lock"]
    assert files["version.txt"] == b"0.2.0\n"
    assert b"0.2.0" in files["CMakeLists.txt"]
    assert "python/packages/core/src/acme_lab_core/__init__.py" in files
    assert "cmake/AcmeLabConfig.cmake.in" in files
    assert "native/packages/core/include/acme_lab/core.h" in files
    assert b"acme-lab-package-a-cli" in files["python/apps/package_a_cli/pyproject.toml"]
    assert b"@acme/native" in files[".github/CODEOWNERS"]
    assert b"https://acme.invalid/security" in files["docs/SECURITY.md"]
    assert b"david.lynch" not in files["docs/SECURITY.md"]
    compile(files["tools/sphinx/conf.py"], "conf.py", "exec")
    for name, content in files.items():
        if name.endswith(".py"):
            compile(content, name, "exec")
        if name.endswith(".json"):
            json.loads(content)
        if name.endswith(".toml"):
            tomllib.loads(content.decode())
        if name not in {"template-config.toml", "README.md", "uv.lock"}:
            assert b"python-c-monorepo-template" not in content, name
        if name != "uv.lock":
            assert b"monorepo-template-creator" not in content, name
            assert b"python/apps/template_creator" not in content, name
    root = tomllib.loads(files["pyproject.toml"].decode())
    assert root["tool"]["coverage"]["run"]["source"] == [
        "acme_lab_core",
        "acme_lab_package_a",
        "acme_lab_package_b",
        "acme_lab_package_a_cli",
    ]
    assert files["tools/repo_tools/pyproject.toml"].find(b'version = "0.1.0"') >= 0
    assert render(snapshot, config) == files
    assert pack(snapshot) == pack(snapshot)


def test_anchors_reject_unbalanced() -> None:
    with pytest.raises(ValueError, match="anchors"):
        without_creator("# BEGIN TEMPLATE CREATOR ONLY\n")


@pytest.mark.parametrize(
    "name", ["/absolute", "../parent", "a/../b", "C:/absolute", "a\\b", "a//b"]
)
def test_archive_paths(name: str) -> None:
    assert not safe_name(name)


def test_snapshot_does_not_use_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot
) -> None:
    monkeypatch.chdir(tmp_path)
    assert snapshots.load().digest == snapshot.digest


def test_preflight_preserves_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot, config: Config
) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep"
    marker.write_text("original")
    probe = Mock(side_effect=AssertionError("must not probe"))
    monkeypatch.setattr(generate, "require_uv", probe)
    with pytest.raises(ValueError, match="already exists"):
        generate.generate(snapshot, config, output)
    assert marker.read_text() == "original"
    assert not probe.called


@pytest.mark.parametrize("error", [ValueError("offline"), KeyboardInterrupt()])
def test_failure_preserves_recipe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: Snapshot,
    config: Config,
    error: BaseException,
) -> None:
    recipe = tmp_path / "config.toml"
    save(config, recipe)
    monkeypatch.setattr(generate, "require_uv", lambda: "uv")
    monkeypatch.setattr(generate, "run", Mock(side_effect=error))
    with pytest.raises(type(error)):
        generate.generate(snapshot, config, tmp_path / "destination")
    assert list(tmp_path.iterdir()) == [recipe]
    assert recipe.read_text() == serialize(config)


def test_creation_race_preserves_other_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot, config: Config
) -> None:
    output = tmp_path / "destination"
    monkeypatch.setattr(generate, "require_uv", lambda: "uv")

    def race(*args: Any, **kwargs: Any) -> None:
        output.mkdir(exist_ok=True)
        (output / "keep").write_text("other process")

    monkeypatch.setattr(generate, "run", race)
    with pytest.raises(FileExistsError):
        generate.generate(snapshot, config, output)
    assert (output / "keep").read_text() == "other process"
    assert not list(tmp_path.glob(".template-create-*"))


def test_preview_does_not_probe_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: Config
) -> None:
    path = tmp_path / "config.toml"
    save(config, path)
    monkeypatch.setattr(generate, "require_uv", Mock(side_effect=AssertionError))
    assert (
        cli.main(
            ["generate", "--config", str(path), "--output", str(tmp_path / "out"), "--dry-run"]
        )
        == 0
    )
    assert list(tmp_path.iterdir()) == [path]
    assert cli.main(["validate", "--config", str(path)]) == 0
    assert cli.main(["--version"]) == 0


def test_wizard_saves_and_edits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot
) -> None:
    answers = iter(
        [
            "Acme",
            "acme",
            "Description",
            "acme",
            "0.1.0",
            "ada",
            "",
            "Ada",
            "ada@acme.invalid",
            "",
            "@ada",
            "no",
            "MIT",
            "2026",
            "Ada",
            "edit",
            "1",
            "Updated Acme",
            "",
            "",
            "",
            "",
            "save",
            "no",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    path = tmp_path / "recipe.toml"
    wizard(snapshot, path)
    assert load(path, snapshot).data["project"]["name"] == "Updated Acme"
    assert list(tmp_path.iterdir()) == [path]


def test_wizard_cancel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot) -> None:
    monkeypatch.setattr("builtins.input", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        wizard(snapshot, tmp_path / "recipe.toml")
    assert not list(tmp_path.iterdir())


def test_missing_uv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generate.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="uv is required"):
        generate.require_uv()


@pytest.mark.parametrize("version", ["uv 0.9.0", "invalid", "uv 0.12.13"])
def test_uv_version(monkeypatch: pytest.MonkeyPatch, version: str) -> None:
    monkeypatch.setattr(generate.shutil, "which", lambda _: "uv")
    monkeypatch.setattr(
        generate.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, version),
    )
    if version == "uv 0.12.13":
        assert generate.require_uv() == "uv"
    else:
        with pytest.raises(ValueError, match=r">=0\.10\.9"):
            generate.require_uv()


def test_packaged_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot
) -> None:
    monkeypatch.setattr(snapshots, "PACKAGE", tmp_path)
    (tmp_path / "_template.zip").write_bytes(pack(snapshot))
    assert snapshots.load() == snapshot
    assert snapshots.checkout_root() is None


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "directory/"])
def test_reject_unsafe_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    from zipfile import ZipFile

    monkeypatch.setattr(snapshots, "PACKAGE", tmp_path)
    with ZipFile(tmp_path / "_template.zip", "w") as archive:
        archive.writestr(name, "bad")
    with pytest.raises(ValueError, match="archive"):
        snapshots.load()


def test_collect_rejects_unsafe_inventory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snapshots, "PACKAGE", tmp_path)
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"include": ["../secret"]}))
    with pytest.raises(ValueError, match="unsafe template"):
        snapshots.collect(tmp_path)
    inventory.write_text(json.dumps({"include": ["link"]}))
    (tmp_path / "link").symlink_to(inventory)
    with pytest.raises(ValueError, match="regular file"):
        snapshots.collect(tmp_path)


def test_template_anchors_and_collisions(snapshot: Snapshot, config: Config) -> None:
    with pytest.raises(ValueError, match="collision"):
        render(Snapshot({"example_core/file": b"", "acme_lab_core/file": b""}), config)
    for path, text, message in (
        ("CMakeLists.txt", b"project(no_version)", "VERSION anchor"),
        ("tools/sphinx/conf.py", b"# missing declarations", "Sphinx project anchor"),
        ("tools/doxygen/Doxyfile", b"# missing declarations", "Doxygen PROJECT_NAME anchor"),
    ):
        with pytest.raises(ValueError, match=message):
            render(Snapshot({**snapshot.files, path: text}), config)


def test_run_sanitizes_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/bundled")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/host")
    monkeypatch.setenv("PYTHONPATH", "/unrelated")
    for name in ("UV_PROJECT", "UV_WORKING_DIR", "UV_PROJECT_ENVIRONMENT"):
        monkeypatch.setenv(name, "/unrelated")
    preserved = {"UV_CACHE_DIR": "/cache", "UV_OFFLINE": "1", "HTTPS_PROXY": "http://proxy:8080"}
    for name, value in preserved.items():
        monkeypatch.setenv(name, value)
    completed = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(generate.subprocess, "run", completed)
    generate.run(["uv", "lock"], tmp_path)
    env = completed.call_args.kwargs["env"]
    assert env["LD_LIBRARY_PATH"] == "/host"
    assert "PYTHONPATH" not in env
    assert not {"UV_PROJECT", "UV_WORKING_DIR", "UV_PROJECT_ENVIRONMENT"} & env.keys()
    assert all(env[name] == value for name, value in preserved.items())
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG")
    generate.run(["uv", "lock"], tmp_path)
    assert "LD_LIBRARY_PATH" not in completed.call_args.kwargs["env"]
    completed.return_value = subprocess.CompletedProcess([], 1, "resolver output", "reason")
    with pytest.raises(ValueError, match="resolver outputreason"):
        generate.run(["uv", "lock"], tmp_path)


@pytest.mark.parametrize("override", ["UV_PROJECT", "UV_WORKING_DIR"])
def test_uv_lock_cannot_be_redirected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, override: str
) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "the repository's test environment requires uv"
    stage, unrelated = tmp_path / "stage", tmp_path / "unrelated"
    for path in (stage, unrelated):
        path.mkdir()
        (path / "pyproject.toml").write_text(
            f'[project]\nname = "{path.name}"\nversion = "0.1.0"\n'
            'requires-python = ">=3.12"\ndependencies = []\n',
            encoding="utf-8",
        )
    original = (unrelated / "pyproject.toml").read_bytes()
    monkeypatch.setenv(override, str(unrelated))
    generate.run([uv, "lock", "--offline", "--python", sys.executable], stage)
    assert (stage / "uv.lock").is_file()
    assert not (unrelated / "uv.lock").exists()
    assert (unrelated / "pyproject.toml").read_bytes() == original


def test_successful_transfer_and_failed_transfer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot, config: Config
) -> None:
    monkeypatch.setattr(generate, "require_uv", lambda: "uv")
    monkeypatch.setattr(generate, "run", lambda *args, **kwargs: None)
    output = tmp_path / "success"
    generate.generate(snapshot, config, output)
    assert (output / "template-config.toml").read_text() == serialize(config)
    assert not list(tmp_path.glob(".template-create-*"))
    monkeypatch.setattr(generate.shutil, "move", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        generate.generate(snapshot, config, tmp_path / "failure")
    assert not (tmp_path / "failure").exists()
    with pytest.raises(ValueError, match="parent"):
        generate.generate(snapshot, config, tmp_path / "missing" / "failure")


def test_cli_errors_and_wizard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit) as error:
        cli.main([])
    assert error.value.code == 2
    assert cli.main(["validate", "--config", str(tmp_path / "missing")]) == 1
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "wizard", Mock(side_effect=KeyboardInterrupt))
    assert cli.main([]) == 130
    monkeypatch.setattr(cli, "wizard", lambda *args: None)
    assert cli.main(["wizard", "--config", str(tmp_path / "config")]) == 0


def test_module_help(monkeypatch: pytest.MonkeyPatch) -> None:
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["template-create", "--help"])
    with pytest.raises(SystemExit) as error:
        runpy.run_module("template_creator", run_name="__main__")
    assert error.value.code == 0


def test_wizard_custom_license_and_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot
) -> None:
    from template_creator import wizard as guide

    license = tmp_path / "custom.txt"
    license.write_text("Custom license, with café and {{ placeholders }}.\n")
    answers = iter(
        [
            "",
            "Acme",
            "acme",
            "Description",
            "acme",
            "0.1.0",
            "ada",
            "",
            "Ada",
            "ada@acme.invalid",
            "",
            "@ada",
            "yes",
            "/native/",
            "@acme/native",
            "no",
            "unknown",
            "Custom",
            "invalid year",
            "2026",
            str(tmp_path / "missing"),
            str(license),
            "Ada",
            "5",
            "",
            "remove",
            "no",
            "save",
            "yes",
            str(tmp_path / "output"),
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    generated = Mock()
    monkeypatch.setattr(guide, "generate", generated)
    path = tmp_path / "config.toml"
    wizard(snapshot, path)
    config = load(path, snapshot)
    assert config.data["license"]["text"] == license.read_text()
    assert config.data["ownership"]["rules"] == []
    assert generated.call_args.args[1] == config
    with pytest.raises(ValueError, match="already exists"):
        wizard(snapshot, path)


def test_wizard_validation_correction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot
) -> None:
    answers = iter(
        [
            "Acme",
            "acme",
            "Description",
            "class",
            "0.1.0",
            "ada",
            "",
            "Ada",
            "ada@acme.invalid",
            "",
            "@ada",
            "no",
            "MIT",
            "2026",
            "Ada",
            "1",
            "",
            "",
            "",
            "acme",
            "",
            "save",
            "no",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    wizard(snapshot, tmp_path / "config.toml")
    assert load(tmp_path / "config.toml", snapshot).prefix == "acme"


def test_wizard_corrects_invalid_owners_at_prompt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from template_creator.wizard import section

    answers = iter(["invalid", "@ada", "yes", "/native/", "also-invalid", "@acme/native", "no"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    data: dict[str, Any] = {}
    section(5, data)
    assert data["ownership"] == {
        "default": ["@ada"],
        "rules": [{"pattern": "/native/", "owners": ["@acme/native"]}],
    }
    output = capsys.readouterr().out
    assert "invalid owner 'invalid'" in output
    assert "invalid owner 'also-invalid'" in output


def test_wizard_removes_and_edits_individual_ownership_rules(
    monkeypatch: pytest.MonkeyPatch, snapshot: Snapshot, config: Config
) -> None:
    from template_creator.wizard import section

    config.data["ownership"] = {
        "default": ["@ada", "invalid"],
        "rules": [
            {"pattern": "/docs/", "owners": ["@acme/docs"]},
            {"pattern": "/native/", "owners": ["invalid"]},
            {"pattern": "/python/", "owners": ["@ada", "invalid"]},
        ],
    }
    answers = iter(["@ada", "", "typo", "remove", "edit", "", "@ada", "no"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    section(5, config.data)
    corrected = validate(config.data, snapshot)
    assert corrected.data["ownership"] == {
        "default": ["@ada"],
        "rules": [
            {"pattern": "/docs/", "owners": ["@acme/docs"]},
            {"pattern": "/python/", "owners": ["@ada"]},
        ],
    }
    assert render(snapshot, corrected)[".github/CODEOWNERS"].decode().splitlines() == [
        "# Later matching rules take precedence.",
        "* @ada",
        "/docs/ @acme/docs",
        "/python/ @ada",
    ]


@pytest.mark.parametrize(
    ("answer", "default", "expected"),
    [
        ("y", False, True),
        ("YES", False, True),
        ("n", True, False),
        ("No", True, False),
        ("", True, True),
        ("", False, False),
    ],
)
def test_yes_no_retries_invalid_answers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    answer: str,
    default: bool,
    expected: bool,
) -> None:
    from template_creator.wizard import ask_yes_no

    answers = iter(["typo", answer])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert ask_yes_no("Continue?", default=default) is expected
    assert "Please answer yes/y or no/n." in capsys.readouterr().out


@pytest.mark.parametrize("replace", [False, True])
def test_edit_custom_license_preserves_or_replaces_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: Config, replace: bool
) -> None:
    from template_creator.wizard import section

    original = "Original custom terms.\n"
    config.data["license"].update(choice="Custom", text=original)
    replacement = tmp_path / "license.txt"
    replacement.write_text("Replacement terms.\n", encoding="utf-8")
    answers = iter(
        ["", "2027", "y", str(replacement), "New holder"]
        if replace
        else ["", "2027", "", "New holder"]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    section(6, config.data)
    assert config.data["license"] == {
        "choice": "Custom",
        "year": 2027,
        "holder": "New holder",
        "text": replacement.read_text(encoding="utf-8") if replace else original,
    }


def test_creator_helpers_are_type_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    from repo_tools.commands import check_python

    root = snapshots.checkout_root()
    assert root is not None
    run = Mock()
    monkeypatch.setattr(check_python.subprocess, "run", run)
    check_python.check_projects(root)
    assert str(root / "tools/creator") in run.call_args.args[0]


def test_windows_external_dll_search(monkeypatch: pytest.MonkeyPatch) -> None:
    import ctypes
    import sys

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "bundle", raising=False)
    kernel = Mock()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel, raising=False)
    with pytest.raises(ValueError, match="child failed"), generate.host_libraries():
        raise ValueError("child failed")
    assert kernel.SetDllDirectoryW.call_args_list[0].args == (None,)
    assert kernel.SetDllDirectoryW.call_args_list[-1].args == ("bundle",)
    kernel.SetDllDirectoryW.return_value = 0
    with pytest.raises(OSError, match="DLL search"), generate.host_libraries():
        pass
