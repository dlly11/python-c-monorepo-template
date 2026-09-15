"""Check Python component registrations against the actual uv workspace."""

from __future__ import annotations

import json
import sys
import tomllib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from check_python import PROJECTS
from check_python_install import SMOKE_CHECKS, normalized_name
from check_versions import PROJECT_FILES

ROOT = Path(__file__).resolve().parents[1]
RELEASE_CONFIG = Path("tools/release-please/config.json")


@dataclass(frozen=True)
class Member:
    """A discovered member, with paths relative to the repository root."""

    path: Path
    name: str
    namespaces: frozenset[str]


def read_project(path: Path) -> dict[str, Any]:
    """Read TOML with the source path included in parse and I/O errors."""
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"{path}: {error}") from error


def discover_members(config: dict[str, Any]) -> tuple[list[Member], list[str]]:
    """Expand member/exclude globs and discover the template's src-layout packages."""
    workspace = config["tool"]["uv"]["workspace"]
    excluded = {
        path.resolve() for pattern in workspace.get("exclude", []) for path in ROOT.glob(pattern)
    }
    paths = {
        path.resolve() for pattern in workspace["members"] for path in ROOT.glob(pattern)
    } - excluded
    members: list[Member] = []
    errors: list[str] = []
    for path in sorted(paths):
        if path == ROOT or not path.is_relative_to(ROOT):
            errors.append(f"workspace members: expected a component below the root, found {path}")
            continue
        relative = path.relative_to(ROOT)
        try:
            name = read_project(path / "pyproject.toml")["project"]["name"]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("project.name must be a non-empty string")
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"{relative}/pyproject.toml: {error}")
            continue
        namespaces = frozenset(
            package.parent.name for package in (path / "src").glob("*/__init__.py")
        )
        if not namespaces:
            errors.append(f"{relative}: no import package found at src/<namespace>/__init__.py")
        members.append(Member(relative, normalized_name(name), namespaces))
    return members, errors


def registration_errors(label: str, expected: Iterable[str], actual: Iterable[str]) -> list[str]:
    """Describe missing, stale, and duplicate entries in a registration list."""
    expected_set = set(expected)
    counts = Counter(actual)
    errors = [f"{label}: missing {value}" for value in sorted(expected_set - counts.keys())]
    errors.extend(f"{label}: stale {value}" for value in sorted(counts.keys() - expected_set))
    errors.extend(
        f"{label}: duplicate {value}" for value, count in sorted(counts.items()) if count > 1
    )
    return errors


def workspace_errors() -> list[str]:
    """Validate existing registries without adding a new component manifest."""
    config = read_project(ROOT / "pyproject.toml")
    members, errors = discover_members(config)
    names = [member.name for member in members]
    root_name = normalized_name(config["project"]["name"])
    all_names = [root_name, *names]
    namespaces = [namespace for member in members for namespace in sorted(member.namespaces)]
    errors.extend(registration_errors("workspace distribution names", all_names, all_names))
    errors.extend(registration_errors("workspace import namespaces", namespaces, namespaces))

    expected_projects = {
        Path("pyproject.toml"): root_name,
        **{member.path / "pyproject.toml": member.name for member in members},
    }
    errors.extend(
        registration_errors(
            "check_versions.PROJECT_FILES",
            (path.as_posix() for path in expected_projects),
            (path.as_posix() for path in PROJECT_FILES),
        )
    )
    for path in sorted(expected_projects.keys() & PROJECT_FILES.keys()):
        if normalized_name(PROJECT_FILES[path]) != expected_projects[path]:
            errors.append(
                f"check_versions.PROJECT_FILES: {path} should name {expected_projects[path]}, "
                f"found {PROJECT_FILES[path]}"
            )
    errors.extend(
        registration_errors(
            "check_python.PROJECTS",
            (str(ROOT / member.path) for member in members),
            (str(path) for path in PROJECTS),
        )
    )
    smoke_names = [normalized_name(name) for name in SMOKE_CHECKS]
    errors.extend(registration_errors("check_python_install.SMOKE_CHECKS", names, smoke_names))
    member_namespaces = {member.name: member.namespaces for member in members}
    for name, (namespace, _) in SMOKE_CHECKS.items():
        if (
            normalized_name(name) in member_namespaces
            and namespace not in member_namespaces[normalized_name(name)]
        ):
            errors.append(
                f"SMOKE_CHECKS[{name!r}]: namespace {namespace!r} "
                "is missing from that member's src directory"
            )

    errors.extend(
        registration_errors(
            "pyproject.toml: tool.coverage.run.source",
            namespaces,
            config["tool"]["coverage"]["run"]["source"],
        )
    )
    errors.extend(
        registration_errors(
            "pyproject.toml: tool.ruff.lint.isort.known-first-party",
            namespaces,
            config["tool"]["ruff"]["lint"]["isort"]["known-first-party"],
        )
    )

    try:
        release = json.loads((ROOT / RELEASE_CONFIG).read_text(encoding="utf-8"))
        extra_files = release["packages"]["."]["extra-files"]
        # Other entries, including the native CMake version, retain their own checks.
        entries = [
            entry if isinstance(entry, dict) else {"path": entry}
            for entry in extra_files
            if (isinstance(entry, dict) and str(entry.get("path", "")).endswith("pyproject.toml"))
            or (isinstance(entry, str) and entry.endswith("pyproject.toml"))
        ]
        errors.extend(
            registration_errors(
                f"{RELEASE_CONFIG}: Python extra-files",
                (path.as_posix() for path in expected_projects),
                (entry["path"] for entry in entries),
            )
        )
        for entry in entries:
            if entry.get("type") != "toml" or entry.get("jsonpath") != "$.project.version":
                errors.append(
                    f"{RELEASE_CONFIG}: {entry['path']} requires type='toml' "
                    "and jsonpath='$.project.version'"
                )
    except (OSError, KeyError, TypeError, ValueError) as error:
        errors.append(f"{RELEASE_CONFIG}: {error}")
    return errors


def main() -> int:
    """Report all registration discrepancies and return a failing status if needed."""
    try:
        errors = workspace_errors()
    except (OSError, KeyError, TypeError, ValueError) as error:
        errors = [f"invalid workspace configuration: {error}"]
    for error in errors:
        print(f"workspace check failed: {error}", file=sys.stderr)
    if errors:
        return 1
    print("all Python workspace components have consistent registrations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
