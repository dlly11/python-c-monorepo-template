"""Build distributions and smoke-test each wheel in its own clean environment."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from email.parser import BytesParser
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from check_versions import PROJECT_FILES, ROOT, project_metadata

# Keep one observable API example per independently delivered component.
SMOKE_CHECKS = {
    "example-core": (
        "example_core",
        """
from example_core import Message, MessageKind, create_message, normalize_name
assert normalize_name(" Ada  Lovelace ") == "Ada Lovelace"
assert create_message(kind=MessageKind.GREETING, source="smoke", prefix="Hi", name="Ada") == (
    Message(kind=MessageKind.GREETING, source="smoke", text="Hi, Ada!")
)
""",
    ),
    "example-package-a": (
        "example_package_a",
        """
from example_package_a import GreetingService
message = GreetingService().greet("Ada")
assert (message.kind, message.source, message.text) == ("greeting", "package_a", "Hello, Ada!")
""",
    ),
    "example-package-b": (
        "example_package_b",
        """
from example_package_b import FarewellService
message = FarewellService().farewell("Ada")
assert (message.kind, message.source, message.text) == ("farewell", "package_b", "Goodbye, Ada!")
""",
    ),
    "example-package-a-cli": (
        "example_package_a_cli",
        """
from example_package_a_cli.cli import build_parser
assert build_parser().parse_args(["Ada"]).name == "Ada"
""",
    ),
}

INSTALL_CHECK = """
import importlib
import importlib.metadata
import pathlib
import sys

name, namespace, expected_version = sys.argv[1:]
assert importlib.metadata.version(name) == expected_version
module = importlib.import_module(namespace)
location = pathlib.Path(module.__file__).resolve()
assert location.is_relative_to(pathlib.Path(sys.prefix).resolve()), location
assert location.with_name("py.typed").is_file(), "missing py.typed"
"""


def normalized_name(name: str) -> str:
    """Normalize a distribution name for comparisons with wheel metadata."""
    return re.sub(r"[-_.]+", "-", name).lower()


def collect_wheels(directory: Path, expected: dict[str, str]) -> dict[str, Path]:
    """Require exactly one wheel for each expected distribution and version."""
    wheels: dict[str, Path] = {}
    for path in sorted(directory.glob("*.whl")):
        with ZipFile(path) as archive:
            metadata_files = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_files) != 1:
                raise ValueError(f"{path.name}: expected one wheel METADATA file")
            metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        name = normalized_name(str(metadata.get("Name", "")))
        version = str(metadata.get("Version", ""))
        if name not in expected or expected[name] != version:
            raise ValueError(f"{path.name}: unexpected distribution/version {name}=={version}")
        if name in wheels:
            raise ValueError(f"{name}: multiple wheels found")
        wheels[name] = path.resolve()
    missing = expected.keys() - wheels.keys()
    if missing:
        raise ValueError(f"missing wheels: {', '.join(sorted(missing))}")
    return wheels


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    status: int = 0,
    stdout: str | None = None,
    stderr_contains: str | None = None,
) -> None:
    """Run a command and include its output in any failure report."""
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if (
        result.returncode != status
        or (stdout is not None and result.stdout != stdout)
        or (stderr_contains is not None and stderr_contains not in result.stderr)
    ):
        raise RuntimeError(
            f"command {subprocess.list2cmdline(command)}\n"
            f"expected exit {status}, got {result.returncode}; "
            f"expected stdout {stdout!r}, stderr containing {stderr_contains!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def check_wheel(
    uv: str, name: str, version: str, wheel: Path, constraints: Path, temporary: Path
) -> None:
    """Install only this wheel and its declared dependencies, then exercise it."""
    env = dict(os.environ)
    for variable in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(variable, None)
    env.update(PYTHONNOUSERSITE="1", PYTHONSAFEPATH="1")
    environment = temporary / name
    run(
        [uv, "venv", "--python", sys.executable, str(environment)],
        cwd=temporary,
        env=env,
    )
    bin_directory = environment / ("Scripts" if os.name == "nt" else "bin")
    python = str(bin_directory / ("python.exe" if os.name == "nt" else "python"))
    run(
        [uv, "pip", "install", "--python", python, "-c", str(constraints), str(wheel)],
        cwd=temporary,
        env=env,
    )
    run([uv, "pip", "check", "--python", python], cwd=temporary, env=env)
    namespace, example = SMOKE_CHECKS[name]
    run(
        [python, "-I", "-c", INSTALL_CHECK + example, name, namespace, version],
        cwd=temporary,
        env=env,
    )
    if name == "example-package-a-cli":
        executable = str(
            bin_directory / ("package-a-cli.exe" if os.name == "nt" else "package-a-cli")
        )
        run([executable, "Ada"], cwd=temporary, env=env, stdout="Hello, Ada!\n")
        run(
            [executable, "Ada", "--prefix", "Welcome"],
            cwd=temporary,
            env=env,
            stdout="Welcome, Ada!\n",
        )
        run(
            [executable, "   "],
            cwd=temporary,
            env=env,
            status=2,
            stdout="",
            stderr_contains="name must contain at least one non-whitespace character",
        )


def main(argv: list[str] | None = None) -> int:
    """Build once and check every wheel without using the workspace environment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist", type=Path, help="verify existing release wheels without rebuilding"
    )
    args = parser.parse_args(argv)
    context = "build"
    try:
        uv = shutil.which("uv")
        if uv is None:
            raise ValueError("uv is required; see docs/workstation.md")
        expected = dict(
            project_metadata(path) for path in PROJECT_FILES if path != Path("pyproject.toml")
        )
        if expected.keys() != SMOKE_CHECKS.keys():
            raise ValueError(
                "workspace distributions and SMOKE_CHECKS must cover the same packages"
            )
        with tempfile.TemporaryDirectory(prefix="python-install-check-") as directory:
            temporary = Path(directory).resolve()
            dist = args.dist.resolve() if args.dist is not None else temporary / "dist"
            if args.dist is None:
                print("Building all wheels and source distributions", flush=True)
                run(
                    [uv, "build", "--all-packages", "--out-dir", str(dist)],
                    cwd=ROOT,
                    env=dict(os.environ),
                )
            wheels = collect_wheels(dist, expected)
            constraints = temporary / "workspace-wheels.txt"
            constraints.write_text(
                "".join(f"{name} @ {wheel.as_uri()}\n" for name, wheel in wheels.items()),
                encoding="utf-8",
            )
            for name, wheel in wheels.items():
                context = name
                print(f"Checking installed {name}=={expected[name]}", flush=True)
                check_wheel(uv, name, expected[name], wheel, constraints, temporary)
    except (OSError, ValueError, RuntimeError, BadZipFile) as error:
        print(f"Python install check failed ({context}): {error}", file=sys.stderr)
        return 1
    print("All Python wheels passed isolated installation checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
