"""Read release ownership from Release Please, without maintaining another inventory."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from repo_tools.repository_metadata import (
    VERSION_PATTERN,
    cmake_version,
    locked_versions,
    project_metadata,
    python_projects,
    registration_errors,
)

CONFIG = "tools/release-please/config.json"
MANIFEST = "tools/release-please/manifest.json"
COMPONENT_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")


def relative_path(value: str) -> str:
    """Require a normalized repository-relative path."""
    if not isinstance(value, str) or not value:
        raise ValueError("release paths must be nonempty strings")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in {"", ".."} for p in value.split("/")):
        raise ValueError(f"invalid release path: {value!r}")
    if "\\" in value or ":" in value:
        raise ValueError(f"invalid release path: {value!r}")
    return value


@dataclass(frozen=True)
class Component:
    """One release owner and the metadata updated by its configured strategy."""

    path: str
    id: str
    kind: str
    files: tuple[str, ...]
    changelog: str
    tagged_component: bool = True

    def version(self, root: Path) -> str:
        primary = self.files[0]
        value = (
            project_metadata(root, Path(primary))[1]
            if primary.endswith("pyproject.toml")
            else (root / primary).read_text(encoding="utf-8").strip()
        )
        if not VERSION_PATTERN.fullmatch(value):
            raise ValueError(f"{primary}: expected numeric X.Y.Z, found {value!r}")
        return value

    def tag(self, version: str) -> str:
        return f"{self.id}-v{version}" if self.tagged_component else f"v{version}"


def legacy_config(config: dict[str, Any]) -> bool:
    """Historical lockstep trees are supported only for read-only recovery."""
    return (
        isinstance(config.get("packages"), dict)
        and set(config["packages"]) == {"."}
        and "separate-pull-requests" not in config
    )


def configured_components(config: dict[str, Any]) -> tuple[Component, ...]:
    """Interpret the deliberately small, supported Release Please configuration."""
    packages = config.get("packages")
    if not isinstance(packages, dict) or not packages:
        raise ValueError("release configuration requires packages")
    if config.get("plugins") or config.get("separate-pull-requests") is not False:
        raise ValueError("independent releases require one combined PR without plugins")
    if config.get("group-pull-request-title-pattern") != "chore: release ${branch}":
        raise ValueError("combined releases require the conventional group PR title")
    components = []
    for path, entry in packages.items():
        relative_path(path)
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: expected a release configuration object")
        settings = {**config, **entry}
        # An unnamed root is required for root-only combined PRs to publish with
        # unprefixed tags. Keep its local CLI/scope identity independent of that.
        identifier = settings.get("component", "")
        if path == "." and identifier == "":
            identifier = "template"
        if not isinstance(identifier, str) or not COMPONENT_ID.fullmatch(identifier):
            raise ValueError(f"{path}: declare a lowercase hyphen-separated component ID")
        strategy = settings.get("release-type")
        kind = "template" if path == "." else "python" if strategy == "python" else "native"
        if strategy not in {"python", "simple"} or (kind == "template" and strategy != "simple"):
            raise ValueError(f"{path}: unsupported release strategy {strategy!r}")
        if settings.get("include-v-in-tag", True) is not True:
            raise ValueError("component tags must include v")
        tagged = settings.get("include-component-in-tag", True)
        if tagged is not (kind != "template"):
            raise ValueError(f"{path}: only the root template uses unprefixed tags")
        if settings.get("separate-pull-requests") is not False:
            raise ValueError(f"{path}: separate release PRs are unsupported")
        if settings.get("tag-separator", "-") != "-" or settings.get("pull-request-title-pattern"):
            raise ValueError(f"{path}: custom tags or individual PR titles are unsupported")
        primary = "pyproject.toml" if kind == "python" else "version.txt"
        files = [str(PurePosixPath(path) / primary)]
        for extra in entry.get("extra-files", []):
            if not isinstance(extra, dict):
                raise ValueError(f"{path}: extra-files must use typed entries")
            name = str(PurePosixPath(path) / relative_path(extra["path"]))
            valid = (
                extra.get("type") == "toml"
                and extra.get("jsonpath") == "$.project.version"
                and name.endswith("pyproject.toml")
            ) or (extra.get("type") == "generic" and name == "CMakeLists.txt")
            if not valid:
                raise ValueError(f"{path}: unsupported version metadata {name}")
            files.append(name)
        changelog = str(
            PurePosixPath(path) / relative_path(entry.get("changelog-path", "CHANGELOG.md"))
        )
        components.append(Component(path, identifier, kind, tuple(files), changelog, tagged))
    ids = [item.id for item in components]
    files = [file for item in components for file in (*item.files, item.changelog)]
    errors = registration_errors("component IDs", ids, ids) + registration_errors(
        "release ownership", files, files
    )
    paths = [item.path for item in components if item.path != "."]
    if "." in packages and set(packages["."].get("exclude-paths", [])) != set(paths):
        errors.append("template exclude-paths must list every independent component directory")
    if any(a != b and b.startswith(a + "/") for a in paths for b in paths):
        errors.append("component directories must not overlap")
    if errors:
        raise ValueError("; ".join(errors))
    return tuple(components)


def load_components(root: Path) -> tuple[Component, ...]:
    return configured_components(json.loads((root / CONFIG).read_text(encoding="utf-8")))


def select_component(components: tuple[Component, ...], identifier: str) -> Component:
    for component in components:
        if identifier == component.id:
            return component
    raise ValueError(
        f"unknown component {identifier!r}; choose " + ", ".join(c.id for c in components)
    )


def component_errors(root: Path, selected: str | None = None, tag: str | None = None) -> list[str]:
    """Check committed release state, declarations, registrations, and generated lock metadata."""
    components = load_components(root)
    versions = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    projects = python_projects(root)
    errors = registration_errors("release manifest", (c.path for c in components), versions.keys())
    python_files = [file for c in components for file in c.files if file.endswith("pyproject.toml")]
    errors += registration_errors(
        "Python release ownership", (p.as_posix() for p in projects), python_files
    )
    native_paths = [
        p.parent.relative_to(root).as_posix()
        for directory in ("native/packages", "native/apps")
        for p in (root / directory).glob("*/CMakeLists.txt")
    ]
    errors += registration_errors(
        "native release ownership", native_paths, (c.path for c in components if c.kind == "native")
    )
    chosen = (select_component(components, selected),) if selected else components
    if tag:
        matching = tuple(c for c in chosen if c.tag(c.version(root)) == tag)
        if len(matching) != 1:
            errors.append(f"release tag: no selected component matches {tag!r}")
        else:
            chosen = matching
    locked = locked_versions(root)
    for component in chosen:
        version = component.version(root)
        if versions.get(component.path) != version:
            errors.append(f"{MANIFEST}: {component.path} must equal {version}")
        for file in component.files:
            actual = version
            if file.endswith("pyproject.toml"):
                name, actual = project_metadata(root, Path(file))
                if locked.get(name) != actual:
                    errors.append(f"uv.lock: {name} must equal {actual}")
            elif file == "CMakeLists.txt":
                actual = cmake_version(root)
            if actual != version:
                errors.append(f"{file}: expected {version}, found {actual}")
        if not (root / component.changelog).is_file():
            errors.append(f"missing component changelog: {component.changelog}")
    return errors
