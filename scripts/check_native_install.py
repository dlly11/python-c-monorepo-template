"""Verify generated version headers in a native CMake installation."""

from __future__ import annotations

import argparse
import re
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


def main() -> int:
    """Check one native installation prefix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path, help="native CMake installation prefix")
    args = parser.parse_args()

    version = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    errors = install_errors(args.prefix.resolve(), version)
    if errors:
        for error in errors:
            print(f"native install check failed: {error}", file=sys.stderr)
        return 1

    print(f"native install contains version {version} for all components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
