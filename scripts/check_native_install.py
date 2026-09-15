"""Verify version headers and exercise the CLI in a native CMake installation."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = {
    Path("include/example/core_version.h"): "EXAMPLE_CORE",
    Path("include/example/package_a_version.h"): "EXAMPLE_PACKAGE_A",
    Path("include/example/package_b_version.h"): "EXAMPLE_PACKAGE_B",
    Path("include/example/package_a_cli_version.h"): "EXAMPLE_PACKAGE_A_CLI",
}


def expected_definitions(prefix: str, version: str) -> tuple[str, ...]:
    """Return the version definitions required for one component."""
    major, minor, patch = version.split(".")
    return (
        f'#define {prefix}_VERSION "{version}"',
        f"#define {prefix}_VERSION_MAJOR {major}",
        f"#define {prefix}_VERSION_MINOR {minor}",
        f"#define {prefix}_VERSION_PATCH {patch}",
    )


def install_errors(prefix: Path, version: str) -> list[str]:
    """Describe missing, stale, or unwanted installed files."""
    errors: list[str] = []

    for relative_path, macro_prefix in COMPONENTS.items():
        header = prefix / relative_path
        if not header.is_file():
            errors.append(f"missing generated version header: {relative_path}")
            continue

        contents = header.read_text(encoding="utf-8")
        for definition in expected_definitions(macro_prefix, version):
            if re.search(rf"^{re.escape(definition)}$", contents, re.MULTILINE) is None:
                errors.append(f"{relative_path}: missing {definition}")

    cpputest_files = [path for path in prefix.rglob("*") if "cpputest" in path.name.lower()]
    if cpputest_files:
        installed = ", ".join(str(path.relative_to(prefix)) for path in cpputest_files)
        errors.append(f"test-only CppUTest content was installed: {installed}")

    return errors


def cli_errors(prefix: Path, version: str) -> list[str]:
    """Exercise the installed executable, without searching PATH for another copy."""
    executable = (
        prefix.resolve() / "bin" / ("package-a-cli.exe" if os.name == "nt" else "package-a-cli")
    )
    if not executable.is_file():
        return [f"missing installed executable: {executable}"]
    errors = []
    for argument, expected in (
        ("--version", f"package-a-cli {version}\n"),
        ("Ada", "Hello, Ada!\n"),
    ):
        try:
            result = subprocess.run(
                [str(executable), argument],
                cwd=prefix,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
                check=False,
            )
        except (OSError, UnicodeError, subprocess.TimeoutExpired) as error:
            errors.append(f"installed CLI {argument}: {error}")
            continue
        if result.returncode != 0 or result.stdout != expected or result.stderr:
            errors.append(
                f"installed CLI {argument}: expected exit 0, stdout {expected!r}, empty stderr; "
                f"found exit {result.returncode}, stdout {result.stdout!r}, "
                f"stderr {result.stderr!r}"
            )
    return errors


def main() -> int:
    """Check one native installation prefix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path, help="native CMake installation prefix")
    args = parser.parse_args()

    version = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    prefix = args.prefix.resolve()
    errors = install_errors(prefix, version) + cli_errors(prefix, version)
    if errors:
        for error in errors:
            print(f"native install check failed: {error}", file=sys.stderr)
        return 1

    print(f"native install contains version {version}; installed CLI smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
