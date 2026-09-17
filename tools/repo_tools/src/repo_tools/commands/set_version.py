"""Set one component version and refresh uv.lock, restoring files on failure."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from repo_tools.components import MANIFEST, component_errors, load_components, select_component
from repo_tools.repository_metadata import (
    VERSION_PATTERN,
    cmake_project_version,
)


def replace_once(contents: str, pattern: re.Pattern[str], replacement: str, path: Path) -> str:
    """Prepare one version replacement without changing the file."""
    updated, replacements = pattern.subn(replacement, contents, count=1)
    if replacements != 1:
        raise ValueError(f"could not find a version declaration in {path}")
    return updated


def update_version(root: Path, version: str, component: str) -> None:
    """Update one owner, restoring all original bytes after any unsuccessful update."""
    selected = select_component(load_components(root), component)
    errors = component_errors(root)
    if errors:
        raise ValueError("; ".join(errors))
    python = any(name.endswith("pyproject.toml") for name in selected.files)
    paths = [*selected.files, MANIFEST, *(["uv.lock"] if python else [])]
    originals = {name: (root / name).read_bytes() for name in paths}
    pattern = re.compile(
        r'(^\[project\]\s*$.*?^version\s*=\s*")[^"]+("\s*$)',
        flags=re.MULTILINE | re.DOTALL,
    )
    updates = {}
    for name in selected.files:
        contents = originals[name].decode("utf-8")
        if name.endswith("pyproject.toml"):
            contents = replace_once(contents, pattern, rf"\g<1>{version}\g<2>", Path(name))
        elif name == "CMakeLists.txt":
            _, start, end = cmake_project_version(contents)
            contents = contents[:start] + version + contents[end:]
        else:
            contents = version + "\n"
        updates[name] = contents
    manifest = json.loads(originals[MANIFEST])
    manifest[selected.path] = version
    updates[MANIFEST] = json.dumps(manifest, indent=2) + "\n"
    try:
        for name, contents in updates.items():
            (root / name).write_bytes(contents.encode("utf-8"))
        if python:
            subprocess.run(["uv", "lock"], cwd=root, check=True)
        errors = component_errors(root)
        if errors:
            raise ValueError("; ".join(errors))
    except BaseException:
        for name, contents in originals.items():
            try:
                (root / name).write_bytes(contents)
            except OSError as error:
                print(f"could not restore {name}: {error}", file=sys.stderr)
        raise


def version_argument(value: str) -> str:
    """Reject invalid versions through the active command parser."""
    if VERSION_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("version must use the numeric X.Y.Z form")
    return value


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register command arguments without performing any work."""
    parser.add_argument("component", help="component ID; use list-scopes to discover IDs")
    parser.add_argument("version", type=version_argument, help="new version in X.Y.Z form")


def execute(args: argparse.Namespace, *, root: Path) -> int:
    """Update one component's committed version metadata."""
    try:
        selected = select_component(load_components(root), args.component)
        if (
            any(name.endswith("pyproject.toml") for name in selected.files)
            and shutil.which("uv") is None
        ):
            args.parser.error("uv must be installed so uv.lock can be refreshed")
        update_version(root, args.version, args.component)
    except KeyboardInterrupt:
        print("version update interrupted", file=sys.stderr)
        return 130
    except (OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"failed to set version: {error}", file=sys.stderr)
        return 1
    print(f"set {args.component} to version {args.version}")
    return 0
