"""Shared Conventional Commit subject policy for commit messages and PR titles."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from difflib import get_close_matches
from pathlib import Path

from repo_tools.components import CONFIG, configured_components, legacy_config
from repo_tools.context import resolve_root
from repo_tools.repository_metadata import git

TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)

SUBJECT_PATTERN = re.compile(
    r"(?P<type>" + "|".join(TYPES) + r")"
    r"(?:\((?P<scope>[a-z0-9][a-z0-9._/-]*)\))?!?: \S(?:.*\S)?"
)


def scope_policy(root: Path, revision: str | None = None) -> dict[str, str] | None:
    """Read policy as data only, including when checking an older Git revision."""

    def read(name: str) -> str | None:
        if revision:
            try:
                return git("show", f"{revision}:{name}", root=root)
            except subprocess.CalledProcessError:
                # Distinguish an absent historical path from an unreadable revision.
                git("rev-parse", "--verify", f"{revision}^{{commit}}", root=root)
                return None
        path = root / name
        return path.read_text(encoding="utf-8") if path.exists() else None

    project = tomllib.loads(read("pyproject.toml") or "")
    release = json.loads(read(CONFIG) or "{}")
    policy = project.get("tool", {}).get("repo-tools", {}).get("conventional-commits")
    if policy is None:
        if release and not legacy_config(release):
            raise ValueError("independent releases require tool.repo-tools.conventional-commits")
        return None
    shared = policy.get("shared-scopes")
    if (
        not isinstance(shared, list)
        or any(
            not isinstance(s, str) or re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", s) is None
            for s in shared
        )
        or len(set(shared)) != len(shared)
    ):
        raise ValueError("shared-scopes must contain unique lowercase hyphen-separated names")
    scopes = {c.id: c.path for c in configured_components(release)}
    if scopes.keys() & set(shared):
        raise ValueError("shared scopes must not collide with component IDs")
    return {**scopes, **dict.fromkeys(shared, "shared")}


def subject_errors(subject: str, scopes: dict[str, str] | None = None) -> list[str]:
    if not valid_subject(subject):
        return ["expected type(scope)!: description; scope and ! are optional"]
    match = SUBJECT_PATTERN.fullmatch(subject)
    scope = match["scope"] if match else None
    if scope and scopes is not None and scope not in scopes:
        suggestions = get_close_matches(scope, scopes, n=2)
        hint = f"; perhaps {', '.join(suggestions)}" if suggestions else ""
        return [f"unknown scope {scope!r}{hint}; run repo-tools list-scopes"]
    return []


def valid_subject(subject: str) -> bool:
    """Require a supported lowercase type and a nonempty, single-line description."""
    return (
        len(subject.splitlines()) == 1
        and not any(ord(character) < 32 or ord(character) == 127 for character in subject)
        and SUBJECT_PATTERN.fullmatch(subject) is not None
    )


def check_commit(commit: str, *, base: str, root: Path | None = None) -> bool:
    """Check a preserved commit, exempting only proven base-branch synchronization merges."""
    parents = git("show", "--no-patch", "--format=%P", commit, "--", root=root).split()
    if len(parents) == 2 and base not in {"0" * 40, "0" * 64}:
        baseline = git(
            "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}", root=root
        ).strip()

        def in_base(parent: str) -> bool:
            try:
                git("merge-base", "--is-ancestor", parent, baseline, root=root)
            except subprocess.CalledProcessError as error:
                if error.returncode != 1:
                    raise
                return False
            return True

        # GitHub's Update branch merges main into the PR: first parent is the PR,
        # second parent is main (possibly older than the current base). Check the
        # graph, not the subject or author; regular and unrelated merges stay linted.
        if in_base(parents[1]) and not in_base(parents[0]):
            print(f"Exempt base-branch synchronization merge: {commit[:12]}")
            return True
    return check_message(
        git("show", "--no-patch", "--format=%B", commit, "--", root=root),
        commit[:12],
        root=root,
        revision=commit,
    )


def check_message(
    message: str, label: str, *, root: Path | None = None, revision: str | None = None
) -> bool:
    """Check only the subject; bodies and release footers remain free-form."""
    subject = message.split("\n", 1)[0]
    if root is None:
        try:
            root = resolve_root(None)
        except ValueError:
            root = Path.cwd()
    scopes = scope_policy(root, revision)
    if scopes is not None and revision:
        parents = git("show", "--no-patch", "--format=%P", revision, "--", root=root).split()
        if parents:
            # A removal/rename commit may describe the component using its old name.
            scopes = {**(scope_policy(root, parents[0]) or {}), **scopes}
    errors = subject_errors(subject, scopes)
    if not errors:
        return True
    print(f"invalid Conventional Commit subject ({label}): {subject!r}", file=sys.stderr)
    for error in errors:
        print(error, file=sys.stderr)
    print("example: feat(python-package-a): add JSON output", file=sys.stderr)
    return False
