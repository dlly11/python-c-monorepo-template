"""Verify version headers and exercise the CLI in a native CMake installation."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from repo_tools.components import CONFIG, legacy_config, load_components, select_component
from repo_tools.repository_metadata import repository_version

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


def install_errors(prefix: Path, version: str | dict[Path, str]) -> list[str]:
    """Describe missing, stale, or unwanted installed files."""
    errors: list[str] = []

    for relative_path, macro_prefix in COMPONENTS.items():
        if isinstance(version, dict) and relative_path not in version:
            continue
        expected_version = version[relative_path] if isinstance(version, dict) else version
        header = prefix / relative_path
        if not header.is_file():
            errors.append(f"missing generated version header: {relative_path}")
            continue

        contents = header.read_text(encoding="utf-8")
        for definition in expected_definitions(macro_prefix, expected_version):
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


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register command arguments without performing any work."""
    parser.add_argument("prefix", type=Path, help="native CMake installation prefix")
    parser.add_argument("--component", help="check one native component installation")


def execute(args: argparse.Namespace, *, root: Path) -> int:
    """Check one native installation prefix."""

    try:
        prefix = args.prefix.resolve()
        config = root / CONFIG
        if not config.exists() or legacy_config(json.loads(config.read_text())):
            version = repository_version(root)
            errors = install_errors(prefix, version) + cli_errors(prefix, version)
        else:
            components = load_components(root)
            chosen = (
                [select_component(components, args.component)]
                if args.component
                else [c for c in components if c.kind == "native"]
            )
            if any(c.kind != "native" for c in chosen):
                raise ValueError("select a native component")
            versions = {
                Path(f"include/example/{Path(c.path).name}_version.h"): c.version(root)
                for c in chosen
            }
            errors = install_errors(prefix, versions)
            version = ", ".join(f"{c.id}={c.version(root)}" for c in chosen)
            for c in chosen:
                if c.path.startswith("native/apps/"):
                    errors += cli_errors(prefix, c.version(root))
                provenance = prefix / "share" / c.id / "component-versions.txt"
                if not provenance.is_file():
                    errors.append(f"missing build provenance: {provenance}")
                else:
                    entries = provenance.read_text().splitlines()
                    if f"{c.id}={c.version(root)}" not in entries:
                        errors.append(f"incorrect build provenance: {provenance}")
    except (OSError, ValueError) as error:
        print(f"native install check failed: {error}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"native install check failed: {error}", file=sys.stderr)
        return 1

    print(f"native install contains version {version}; installed CLI smoke checks passed")
    return 0
