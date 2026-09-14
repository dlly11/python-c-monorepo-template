"""Set the lockstep repository version and refresh uv.lock."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from check_versions import PROJECT_FILES, ROOT, VERSION_PATTERN, version_errors


def replace_once(path: Path, pattern: re.Pattern[str], replacement: str) -> None:
    """Replace one version declaration, failing if the file shape is unexpected."""
    absolute_path = ROOT / path
    contents = absolute_path.read_text(encoding="utf-8")
    updated, replacements = pattern.subn(replacement, contents, count=1)
    if replacements != 1:
        raise ValueError(f"could not find a version declaration in {path}")
    absolute_path.write_text(updated, encoding="utf-8")


def set_project_version(path: Path, version: str) -> None:
    """Update project.version in a pyproject.toml file."""
    pattern = re.compile(
        r'(^\[project\]\s*$.*?^version\s*=\s*")[^"]+("\s*$)',
        flags=re.MULTILINE | re.DOTALL,
    )
    replace_once(path, pattern, rf"\g<1>{version}\g<2>")


def set_cmake_version(version: str) -> None:
    """Update the root CMake project version."""
    pattern = re.compile(r"(\bVERSION\s+)\d+\.\d+\.\d+\b")
    replace_once(Path("CMakeLists.txt"), pattern, rf"\g<1>{version}")


def main() -> int:
    """Update all committed version metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="new version in X.Y.Z form")
    args = parser.parse_args()

    if VERSION_PATTERN.fullmatch(args.version) is None:
        parser.error("version must use the numeric X.Y.Z form")
    if shutil.which("uv") is None:
        parser.error("uv must be installed so uv.lock can be refreshed atomically")

    managed_paths = [
        Path("version.txt"),
        *PROJECT_FILES,
        Path("CMakeLists.txt"),
        Path("uv.lock"),
    ]
    originals = {path: (ROOT / path).read_text(encoding="utf-8") for path in managed_paths}

    try:
        (ROOT / "version.txt").write_text(f"{args.version}\n", encoding="utf-8")
        for path in PROJECT_FILES:
            set_project_version(path, args.version)
        set_cmake_version(args.version)
        subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
        errors = version_errors(args.version)
        if errors:
            raise ValueError("; ".join(errors))
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        for path, contents in originals.items():
            (ROOT / path).write_text(contents, encoding="utf-8")
        print(f"failed to set version: {error}", file=sys.stderr)
        return 1

    print(f"set all repository components to version {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
