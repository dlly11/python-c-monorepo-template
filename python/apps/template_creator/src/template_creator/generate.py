"""Stage and validate a repository before publishing its destination."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from template_creator.config import Config
from template_creator.render import render
from template_creator.snapshot import Snapshot


@contextmanager
def host_libraries() -> Iterator[None]:
    """Avoid exposing bundled Windows DLLs to external uv/Python processes."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    if not kernel.SetDllDirectoryW(None):
        raise OSError("cannot reset DLL search path for external tools")
    try:
        yield
    finally:
        kernel.SetDllDirectoryW(getattr(sys, "_MEIPASS", None))


def run(command: list[str], root: Path, *, timeout: int = 300) -> None:
    """Use argument arrays and expose useful errors without a shell."""
    environment = dict(os.environ)
    # Project/directory overrides take precedence over cwd in uv. Never let the
    # caller redirect generation into another repository; keep cache/network settings.
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PROJECT",
        "UV_WORKING_DIR",
    ):
        environment.pop(name, None)
    # PyInstaller changes the dynamic-library search path for its embedded runtime.
    # External uv/Python processes must use the original host library search path.
    original = environment.pop("LD_LIBRARY_PATH_ORIG", None)
    if getattr(sys, "frozen", False):
        if original is None:
            environment.pop("LD_LIBRARY_PATH", None)
        else:
            environment["LD_LIBRARY_PATH"] = original
    with host_libraries():
        result = subprocess.run(
            command,
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    if result.returncode:
        raise ValueError(f"{' '.join(command)} failed:\n{result.stdout}{result.stderr}")


def require_uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError(
            "uv is required to generate the lockfile; install it using https://docs.astral.sh/uv/getting-started/installation/"
        )
    with host_libraries():
        result = subprocess.run(
            [uv, "--version"], capture_output=True, text=True, timeout=10, check=True
        )
    match = re.match(r"uv (\d+)\.(\d+)\.(\d+)", result.stdout)
    if match is None or tuple(map(int, match.groups())) < (0, 10, 9):
        raise ValueError("uv >=0.10.9 is required")
    return uv


def generate(snapshot: Snapshot, config: Config, output: Path) -> None:
    """Leave existing destinations untouched and clean up owned staging files on error."""
    output = output.absolute()
    if os.path.lexists(output):
        raise ValueError(f"destination already exists: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"destination parent does not exist: {output.parent}")
    uv = require_uv()
    files = render(snapshot, config)
    with tempfile.TemporaryDirectory(prefix=".template-create-", dir=output.parent) as temporary:
        root = Path(temporary)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        print("Resolving the workspace lockfile...", flush=True)
        run([uv, "lock"], root)
        python = (root / ".python-version").read_text().strip()
        packages = tomllib.loads((root / "uv.lock").read_text())["package"]
        ruff_version = next(package["version"] for package in packages if package["name"] == "ruff")
        ruff = [uv, "tool", "run", "--python", python, "--from", f"ruff=={ruff_version}", "ruff"]
        print("Formatting renamed Python and native sources...", flush=True)
        run([*ruff, "format", "."], root)
        run([*ruff, "check", "--fix", "."], root)
        native = [
            str(path.relative_to(root))
            for path in sorted((root / "native").rglob("*"))
            if path.is_file() and path.suffix in {".c", ".cpp", ".h"}
        ]
        run(
            [
                uv,
                "tool",
                "run",
                "--python",
                python,
                "--from",
                "clang-format==21.1.8",
                "clang-format",
                "-i",
                *native,
            ],
            root,
        )
        for check in ("check-workspace", "check-versions"):
            run(
                [
                    uv,
                    "run",
                    "--no-project",
                    "--python",
                    (root / ".python-version").read_text().strip(),
                    "python",
                    "tools/repo_tools/run.py",
                    check,
                ],
                root,
            )
        # Reserve with mkdir, which fails if another process creates the destination.
        # Publish only our own directory; remove it on interrupted/failed transfer.
        output.mkdir()
        try:
            for path in root.iterdir():
                shutil.move(str(path), output / path.name)
        except BaseException:
            shutil.rmtree(output)
            raise
    print(f"Created {output}\nNext steps: {output / 'docs/adopting.md'}", flush=True)
