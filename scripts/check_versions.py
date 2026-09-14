"""Check that every release-bearing component uses the repository version."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")
PROJECT_FILES = {
    Path("pyproject.toml"): "python-c-monorepo-template",
    Path("python/packages/core/pyproject.toml"): "example-core",
    Path("python/packages/package_a/pyproject.toml"): "example-package-a",
    Path("python/packages/package_b/pyproject.toml"): "example-package-b",
    Path("python/apps/package_a_cli/pyproject.toml"): "example-package-a-cli",
}


def repository_version() -> str:
    """Return the canonical repository version."""
    version = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(f"version.txt must contain X.Y.Z, found {version!r}")
    return version


def project_metadata(path: Path) -> tuple[str, str]:
    """Return a project's distribution name and version."""
    with (ROOT / path).open("rb") as file:
        project = tomllib.load(file)["project"]
    return str(project["name"]), str(project["version"])


def cmake_version() -> str:
    """Return the version declared by the root CMake project."""
    contents = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    match = re.search(r"\bVERSION\s+(\d+\.\d+\.\d+)\b", contents)
    if match is None:
        raise ValueError("CMakeLists.txt does not declare a project VERSION")
    return match.group(1)


def locked_versions() -> dict[str, str]:
    """Return versions for repository projects recorded in uv.lock."""
    with (ROOT / "uv.lock").open("rb") as file:
        packages = tomllib.load(file)["package"]
    expected_names = set(PROJECT_FILES.values())
    return {
        str(package["name"]): str(package["version"])
        for package in packages
        if package["name"] in expected_names
    }


def version_errors(expected: str, expected_tag: str | None = None) -> list[str]:
    """Describe all metadata that differs from the expected version."""
    errors: list[str] = []

    for path, expected_name in PROJECT_FILES.items():
        name, version = project_metadata(path)
        if name != expected_name:
            errors.append(f"{path}: expected project name {expected_name!r}, found {name!r}")
        if version != expected:
            errors.append(f"{path}: expected version {expected}, found {version}")

    native_version = cmake_version()
    if native_version != expected:
        errors.append(f"CMakeLists.txt: expected version {expected}, found {native_version}")

    locked = locked_versions()
    for name in PROJECT_FILES.values():
        version = locked.get(name)
        if version is None:
            errors.append(f"uv.lock: missing workspace project {name}")
        elif version != expected:
            errors.append(f"uv.lock: {name} expected version {expected}, found {version}")

    if expected_tag is not None and expected_tag != f"v{expected}":
        errors.append(f"release tag: expected v{expected}, found {expected_tag}")

    return errors


def main() -> int:
    """Run the version consistency check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="also require this release tag to equal v<version>")
    args = parser.parse_args()

    try:
        expected = repository_version()
        errors = version_errors(expected, args.tag)
    except (KeyError, OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"version check failed: {error}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"version check failed: {error}", file=sys.stderr)
        return 1

    print(f"all repository components use version {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
