"""Recognize release identities and exact metadata-only Git changes."""

from __future__ import annotations

import io
import json
import re
import subprocess
import tarfile
import tempfile
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from repo_tools.components import component_errors, configured_components, legacy_config
from repo_tools.repository_metadata import (
    VERSION_PATTERN,
    cmake_project_version,
    git,
    python_projects,
)

CONFIG = "tools/release-please/config.json"
MANIFEST = "tools/release-please/manifest.json"


def release_branch(config: dict[str, Any], target: str = "main") -> str:
    """Recognize the combined branch, retaining historical lockstep identity checks."""
    if isinstance(config, dict) and not legacy_config(config):
        configured_components(config)
        return f"release-please--branches--{target}"
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("packages"), dict)
        or set(config["packages"]) != {"."}
        or not isinstance(config["packages"]["."], dict)
        or config.get("plugins")
    ):
        raise ValueError("release automation requires one root package without plugins")
    package = {**config, **config["packages"]["."]}
    if package.get("release-type") != "simple" or package.get("pull-request-title-pattern"):
        raise ValueError("release automation requires the simple strategy and default PR title")
    component = package.get("component") or package.get("package-name") or ""
    if not isinstance(component, str) or (
        component and not re.fullmatch(r"[A-Za-z0-9_.-]+", component)
    ):
        raise ValueError("unsupported release branch component")
    branch = f"release-please--branches--{target}"
    return branch + (f"--components--{component}" if component else "")


def branch_at(root: Path, revision: str) -> str:
    return release_branch(json.loads(git("show", f"{revision}:{CONFIG}", root=root)))


def managed_pr(pr: dict[str, Any], repository: str, branch: str) -> bool:
    return (
        pr["base"]["ref"] == "main"
        and pr["head"]["ref"] == branch
        and all(
            (pr[side]["repo"] or {}).get("full_name") == repository for side in ("base", "head")
        )
    )


@contextmanager
def snapshot(root: Path, revision: str, *paths: str) -> Iterator[Path]:
    """Materialize committed inputs in a disposable directory, never the checkout."""
    contents = subprocess.check_output(["git", "archive", revision, *paths], cwd=root)
    with tempfile.TemporaryDirectory(prefix="ci-base-") as temporary:
        directory = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(contents)) as archive:
            archive.extractall(directory, filter="data")
        yield directory


def tree(root: Path, revision: str) -> dict[str, tuple[str, str]]:
    result = {}
    for entry in git("ls-tree", "-r", "-z", revision, root=root).split("\0"):
        if entry:
            metadata, name = entry.split("\t", 1)
            mode, _, oid = metadata.split()
            result[name] = mode, oid
    return result


def project_version_change(before: str, after: str, old: str, new: str) -> bool:
    """Require both semantic equality and an exact scalar substitution, including comments."""
    original = tomllib.loads(before)
    changed = tomllib.loads(after)
    if original["project"]["version"] != old or changed["project"]["version"] != new:
        return False
    changed["project"]["version"] = old
    if original != changed:
        return False
    section = re.search(r"(?ms)^\[project\][^\n]*\n(?P<body>.*?)(?=^\[|\Z)", before)
    if section is None:
        return False
    match = re.search(r"(?m)^version\s*=\s*([\"\'])(?P<version>[^\"\']+)\1", section["body"])
    if match is None or match["version"] != old:
        return False
    start = section.start("body") + match.start("version")
    end = section.start("body") + match.end("version")
    return after == before[:start] + new + before[end:]


def lock_change(before: str, after: str, projects: dict[Path, str], old: str, new: str) -> bool:
    original, changed = tomllib.loads(before), tomllib.loads(after)
    expected = {
        (name, str(path.parent).replace("\\", "/")): "virtual"
        if path == Path("pyproject.toml")
        else "editable"
        for path, name in projects.items()
    }
    seen = set()
    for package in changed["package"]:
        for (name, path), kind in expected.items():
            if package["name"] == name:
                if (
                    name in seen
                    or package.get("source") != {kind: path}
                    or package["version"] != new
                ):
                    return False
                package["version"] = old
                seen.add(name)
    return seen == {name for name, _ in expected} and original == changed


def legacy_release_changes(root: Path, base: str, head: str) -> tuple[bool, str]:
    """Return an explanatory full-CI fallback for anything outside the release transform."""
    try:
        previous, current = tree(root, base), tree(root, head)
        if previous.keys() != current.keys() or any(
            previous[p][0] != current[p][0] for p in previous
        ):
            return False, "paths or file modes changed"
        with snapshot(root, base) as baseline:
            projects = python_projects(baseline)
            config = json.loads((baseline / CONFIG).read_text())
            release_branch(config)
            if config["packages"]["."].get("changelog-path", "CHANGELOG.md") != "CHANGELOG.md":
                return False, "custom changelog layout"
            old = (baseline / "version.txt").read_text().strip()
            new = git("show", f"{head}:version.txt", root=root).strip()
            if not VERSION_PATTERN.fullmatch(new) or tuple(map(int, new.split("."))) <= tuple(
                map(int, old.split("."))
            ):
                return False, "release version must increase"
            allowed = {
                "version.txt",
                "CMakeLists.txt",
                "uv.lock",
                "CHANGELOG.md",
                MANIFEST,
                *(p.as_posix() for p in projects),
            }
            changed_paths = {p for p in previous if previous[p] != current[p]}
            if changed_paths - allowed:
                return False, "non-release files changed: " + ", ".join(
                    sorted(changed_paths - allowed)
                )
            for name in allowed:
                if previous.get(name, (None,))[0] != "100644":
                    return False, f"unsupported release file: {name}"
                before = (baseline / name).read_text(encoding="utf-8")
                after = git("show", f"{head}:{name}", root=root)
                if name == "version.txt":
                    valid = after == new + "\n"
                elif name.endswith("pyproject.toml"):
                    valid = project_version_change(before, after, old, new)
                elif name == "CMakeLists.txt":
                    version, start, end = cmake_project_version(before)
                    valid = version == old and after == before[:start] + new + before[end:]
                elif name == MANIFEST:
                    valid = json.loads(before) == {".": old} and json.loads(after) == {".": new}
                elif name == "uv.lock":
                    valid = lock_change(before, after, projects, old, new)
                else:
                    header = "# Changelog\n\n"
                    prior = before.removeprefix(header)
                    inserted = (
                        after[len(header) : len(after) - len(prior)]
                        if prior
                        else after[len(header) :]
                    )
                    valid = (
                        before.startswith(header)
                        and after.startswith(header)
                        and after.endswith(prior)
                        and bool(inserted.strip())
                        and re.match(rf"## (?:\[)?{re.escape(new)}(?:\]|\s|$)", inserted)
                        is not None
                    )
                if not valid:
                    return False, f"unexpected changes in {name}"
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
        tarfile.TarError,
    ) as error:
        return False, f"unsupported release metadata: {error}"
    return True, "only consistent version metadata and a new changelog entry changed"


def changelog_change(before: str, after: str, version: str) -> bool:
    header = "# Changelog\n\n"
    prior = before.removeprefix(header)
    inserted = after[len(header) : len(after) - len(prior)] if prior else after[len(header) :]
    return (
        before.startswith(header)
        and after.startswith(header)
        and after.endswith(prior)
        and re.match(rf"## (?:\[)?{re.escape(version)}(?:\]|\s|$)", inserted) is not None
    )


def component_lock_change(before: str, after: str, changes: dict[str, tuple[str, str]]) -> bool:
    """Normalize only the explicitly changed workspace package versions."""
    original, changed = tomllib.loads(before), tomllib.loads(after)
    seen = set()
    for package in changed["package"]:
        name = package["name"]
        if name in changes:
            old, new = changes[name]
            if name in seen or package.get("version") != new:
                return False
            seen.add(name)
            package["version"] = old
    return seen == changes.keys() and original == changed


def release_changes(root: Path, base: str, head: str) -> tuple[bool, str]:
    """Allow exact release transforms for any nonempty subset of components."""
    try:
        config = json.loads(git("show", f"{base}:{CONFIG}", root=root))
        if legacy_config(config):
            return legacy_release_changes(root, base, head)
        components = configured_components(config)
        previous, current = tree(root, base), tree(root, head)
        if previous.keys() != current.keys() or any(
            previous[p][0] != current[p][0] for p in previous
        ):
            return False, "paths or file modes changed"
        old_manifest = json.loads(git("show", f"{base}:{MANIFEST}", root=root))
        new_manifest = json.loads(git("show", f"{head}:{MANIFEST}", root=root))
        if old_manifest.keys() != new_manifest.keys() or set(old_manifest) != {
            c.path for c in components
        }:
            return False, "release component registrations changed"
        allowed = {MANIFEST, "uv.lock"}
        if any(previous.get(name, (None,))[0] != "100644" for name in allowed):
            return False, "release manifest and lock must be regular files"
        metadata = {}
        lock_versions = {}
        with snapshot(root, base) as baseline, snapshot(root, head) as proposed:
            if errors := component_errors(baseline) + component_errors(proposed):
                return False, "; ".join(errors)
            projects = python_projects(baseline)
            for component in components:
                old, new = old_manifest[component.path], new_manifest[component.path]
                if old == new:
                    continue
                if tuple(map(int, new.split("."))) <= tuple(map(int, old.split("."))):
                    return False, f"{component.id}: release version must increase"
                for name in (*component.files, component.changelog):
                    allowed.add(name)
                    metadata[name] = old, new, name == component.changelog
                for name in component.files:
                    if Path(name) in projects:
                        lock_versions[projects[Path(name)]] = old, new
            if not metadata:
                return False, "no component version increased"
            changed_paths = {p for p in previous if previous[p] != current[p]}
            if changed_paths - allowed:
                return False, "non-release files changed: " + ", ".join(
                    sorted(changed_paths - allowed)
                )
            for name, (old, new, changelog) in metadata.items():
                if previous.get(name, (None,))[0] != "100644":
                    return False, f"unsupported release file: {name}"
                before = (baseline / name).read_text(encoding="utf-8")
                after = (proposed / name).read_text(encoding="utf-8")
                if changelog:
                    valid = changelog_change(before, after, new)
                elif name.endswith("pyproject.toml"):
                    valid = project_version_change(before, after, old, new)
                elif name == "CMakeLists.txt":
                    version, start, end = cmake_project_version(before)
                    valid = version == old and after == before[:start] + new + before[end:]
                else:
                    valid = before == old + "\n" and after == new + "\n"
                if not valid:
                    return False, f"unexpected changes in {name}"
            if not component_lock_change(
                (baseline / "uv.lock").read_text(),
                (proposed / "uv.lock").read_text(),
                lock_versions,
            ):
                return False, "unexpected changes in uv.lock"
        return True, "only independent component versions and new changelog entries changed"
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
        tarfile.TarError,
    ) as error:
        return False, f"unsupported release metadata: {error}"
