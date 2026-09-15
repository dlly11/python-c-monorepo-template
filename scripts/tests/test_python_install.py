"""Regression checks for isolated wheel installation and artifact validation."""

import base64
import hashlib
import os
import shutil
import sys
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

import pytest


def write_wheel(
    directory: Path, name: str, *, version: str = "1.2.3", requires: str = "", code: str = ""
) -> Path:
    """Create a small installable wheel without a build backend or network access."""
    namespace = name.replace("-", "_")
    info = f"{namespace}-{version}.dist-info"
    files = {
        f"{namespace}/__init__.py": code,
        f"{namespace}/py.typed": "",
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n{requires}",
        f"{info}/WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    records = []
    for path, content in files.items():
        data = content.encode()
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        records.append(f"{path},sha256={digest},{len(data)}\n")
    files[f"{info}/RECORD"] = "".join(records) + f"{info}/RECORD,,\n"
    wheel = directory / f"{namespace}-{version}-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return wheel


@pytest.mark.parametrize("problem", ["missing", "version", "duplicate", "unexpected"])
def test_bad_artifacts_fail(tmp_path: Path, scripts: dict[str, ModuleType], problem: str) -> None:
    module = scripts["check_python_install"]
    if problem == "version":
        write_wheel(tmp_path, "example-core", version="0.0.1")
    elif problem == "unexpected":
        write_wheel(tmp_path, "another-package")
    elif problem == "duplicate":
        wheel = write_wheel(tmp_path, "example-core")
        shutil.copyfile(wheel, tmp_path / "duplicate.whl")
    with pytest.raises(ValueError):
        module.collect_wheels(tmp_path, {"example-core": "1.2.3"})


@pytest.mark.parametrize("declared", [False, True])
def test_install_uses_only_declared_dependencies(
    tmp_path: Path, scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch, declared: bool
) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is needed for the offline installation regression")
    module = scripts["check_python_install"]
    core = write_wheel(tmp_path, "example-core", code='message = "Hello"\n')
    package = write_wheel(
        tmp_path,
        "example-package-a",
        requires="Requires-Dist: example-core>=1.0\n" if declared else "",
        code="from example_core import message\n",
    )
    constraints = tmp_path / "constraints.txt"
    constraints.write_text(f"example-core @ {core.as_uri()}\n", encoding="utf-8")
    monkeypatch.setitem(
        module.SMOKE_CHECKS,
        "example-package-a",
        ("example_package_a", 'from example_package_a import message\nassert message == "Hello"'),
    )
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv("UV_NO_CONFIG", "1")
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "cache"))
    # A source tree on PYTHONPATH must not rescue the missing wheel dependency.
    (tmp_path / "example_core").mkdir()
    (tmp_path / "example_core/__init__.py").write_text('message = "Hello"\n', encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    if declared:
        module.check_wheel(uv, "example-package-a", "1.2.3", package, constraints, tmp_path)
    else:
        with pytest.raises(RuntimeError, match="ModuleNotFoundError"):
            module.check_wheel(uv, "example-package-a", "1.2.3", package, constraints, tmp_path)


@pytest.mark.parametrize(
    ("code", "options"),
    [("raise SystemExit(7)", {}), ('print("wrong")', {"stdout": "expected\n"})],
)
def test_failed_smoke_command_is_reported(
    tmp_path: Path, scripts: dict[str, ModuleType], code: str, options: dict[str, str]
) -> None:
    with pytest.raises(RuntimeError, match=r"command.*python"):
        scripts["check_python_install"].run(
            [sys.executable, "-I", "-c", code], cwd=tmp_path, env=dict(os.environ), **options
        )


def test_failure_returns_nonzero_and_removes_temporary_files(
    tmp_path: Path,
    scripts: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = scripts["check_python_install"]
    monkeypatch.setattr(module.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(module.shutil, "which", lambda _: "uv")

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("build failed deliberately")

    monkeypatch.setattr(module, "run", fail)
    assert module.main([]) == 1
    assert "build failed deliberately" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_release_mode_checks_supplied_wheels_without_rebuilding(
    tmp_path: Path, scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    module = scripts["check_python_install"]
    wheel = write_wheel(tmp_path, "example-core")
    monkeypatch.setattr(
        module, "python_projects", lambda root: {Path("core/pyproject.toml"): "example-core"}
    )
    monkeypatch.setattr(module, "project_metadata", lambda root, path: ("example-core", "1.2.3"))
    monkeypatch.setattr(module, "SMOKE_CHECKS", {"example-core": ("example_core", "")})
    monkeypatch.setattr(module.shutil, "which", lambda _: "uv")

    def no_build(*args: object, **kwargs: object) -> None:
        pytest.fail("release mode must not rebuild distributions")

    checked = []

    def check(
        uv: str,
        name: str,
        version: str,
        artifact: Path,
        constraints: Path,
        temporary: Path,
        project_root: Path,
    ) -> None:
        checked.append(artifact)
        assert artifact == wheel
        assert wheel.as_uri() in constraints.read_text()

    monkeypatch.setattr(module, "run", no_build)
    monkeypatch.setattr(module, "check_wheel", check)
    assert module.main(["--dist", str(tmp_path)]) == 0
    assert checked == [wheel]
    assert wheel.exists()


def test_install_discovers_selected_project_configuration(
    tmp_path: Path, scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is needed for the offline installation regression")
    module = scripts["check_python_install"]
    project = tmp_path / "project"
    artifacts = tmp_path / "private-wheels"
    temporary = tmp_path / "isolated"
    for path in (project, artifacts, temporary):
        path.mkdir()
    write_wheel(artifacts, "private-dependency", code='message = "Private"\n')
    wheel = write_wheel(
        artifacts,
        "example-core",
        requires="Requires-Dist: private-dependency==1.2.3\n",
        code="from private_dependency import message\n",
    )
    # Only this checkout's config knows where to find the private dependency.
    (project / "pyproject.toml").write_text(
        f'[tool.uv]\nno-index = true\nfind-links = ["{artifacts.as_uri()}"]\n', encoding="utf-8"
    )
    constraints = temporary / "constraints.txt"
    constraints.touch()
    monkeypatch.setitem(
        module.SMOKE_CHECKS,
        "example-core",
        ("example_core", 'from example_core import message\nassert message == "Private"'),
    )
    for variable in ("UV_NO_CONFIG", "UV_FIND_LINKS", "UV_CONFIG_FILE"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "cache"))
    module.check_wheel(uv, "example-core", "1.2.3", wheel, constraints, temporary, project)


def test_hanging_smoke_command_times_out_with_output(
    tmp_path: Path, scripts: dict[str, ModuleType]
) -> None:
    with pytest.raises(RuntimeError, match=r"timed out.*started"):
        scripts["check_python_install"].run(
            [
                sys.executable,
                "-I",
                "-c",
                'import time; print("started", flush=True); time.sleep(30)',
            ],
            cwd=tmp_path,
            env=dict(os.environ),
            timeout=1,
        )
