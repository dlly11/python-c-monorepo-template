"""Plan and publish component artifacts from immutable release commits."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from repo_tools.components import component_errors, load_components
from repo_tools.repository_metadata import VERSION_PATTERN, git, project_metadata


def release_plan(root: Path, outputs: dict[str, Any]) -> list[dict[str, str]]:
    """Use only known paths and validate every tag/version before scheduling assets."""
    paths = json.loads(outputs.get("paths_released") or "[]")
    if (
        not isinstance(paths, list)
        or any(not isinstance(p, str) for p in paths)
        or len(set(paths)) != len(paths)
    ):
        raise ValueError("invalid or duplicate released paths")
    components = {c.path: c for c in load_components(root)}
    releases = []
    for path in paths:
        if path not in components:
            raise ValueError(f"unknown released path: {path}")
        component = components[path]
        prefix = "" if path == "." else path + "--"
        version, tag, sha = (outputs.get(prefix + key) for key in ("version", "tag_name", "sha"))
        if not isinstance(version, str) or VERSION_PATTERN.fullmatch(version) is None:
            raise ValueError(f"{path}: missing release version")
        if (
            tag != component.tag(version)
            or not isinstance(sha, str)
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha)
        ):
            raise ValueError(f"{path}: invalid release tag or commit")
        if outputs.get(prefix + "release_created") not in {True, "true"}:
            raise ValueError(f"{path}: release was not reported as created")
        releases.append(
            {
                "path": path,
                "component": component.id,
                "kind": component.kind,
                "version": version,
                "tag": tag,
                "sha": sha,
            }
        )
    return releases


def run(root: Path, *command: str) -> None:
    print("==>", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=root, check=True)


def publish(root: Path, releases: list[dict[str, str]], kind: str) -> None:
    """Build once per commit and platform; never upload unchanged sibling distributions."""
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for release in releases:
        if release["kind"] == kind or (kind == "python" and release["kind"] == "template"):
            actual = git(
                "rev-parse", "--verify", f"refs/tags/{release['tag']}^{{commit}}", root=root
            ).strip()
            if actual != release["sha"]:
                raise ValueError(f"release tag moved: {release['tag']}")
            groups[actual].append(release)
    for sha, batch in groups.items():
        with tempfile.TemporaryDirectory(prefix="component-assets-") as temporary:
            checkout = Path(temporary) / "source"
            run(root, "git", "worktree", "add", "--detach", str(checkout), sha)
            try:
                components = {c.path: c for c in load_components(checkout)}
                for release in batch:
                    if components[release["path"]].version(checkout) != release["version"]:
                        raise ValueError(f"release metadata does not match tag: {release['tag']}")
                    if errors := component_errors(checkout, tag=release["tag"]):
                        raise ValueError("; ".join(errors))
                if kind == "python":
                    run(checkout, "uv", "build", "--all-packages", "--out-dir", "dist")
                    run(
                        checkout,
                        sys.executable,
                        "tools/repo_tools/run.py",
                        "check-python-install",
                        "--dist",
                        "dist",
                    )
                    for release in batch:
                        owner = components[release["path"]]
                        artifacts = []
                        for name in owner.files:
                            if name != "pyproject.toml" and name.endswith("pyproject.toml"):
                                distribution, version = project_metadata(checkout, Path(name))
                                stem = distribution.replace("-", "_") + "-" + version
                                artifacts.extend(checkout.glob(f"dist/{stem}-*.whl"))
                                artifacts.extend(checkout.glob(f"dist/{stem}.tar.gz"))
                        if len(artifacts) != 2:
                            raise ValueError(
                                f"{owner.id}: expected one wheel and one source distribution"
                            )
                        run(
                            checkout,
                            "gh",
                            "release",
                            "upload",
                            release["tag"],
                            *(str(p) for p in sorted(artifacts)),
                            "--clobber",
                        )
                else:
                    run(checkout, "cmake", "--preset", "release")
                    run(checkout, "cmake", "--build", "--preset", "release")
                    full = checkout / "build/full-install"
                    run(checkout, "cmake", "--install", "build/release", "--prefix", str(full))
                    run(
                        checkout,
                        sys.executable,
                        "tools/repo_tools/run.py",
                        "check-native-install",
                        str(full),
                    )
                    run(
                        checkout,
                        "cmake",
                        "-S",
                        "native/tests/install_consumer",
                        "-B",
                        "build/consumer",
                        "-G",
                        "Ninja",
                        f"-DMONOREPO_INSTALL_PREFIX={full}",
                    )
                    run(checkout, "cmake", "--build", "build/consumer")
                    run(checkout, "ctest", "--test-dir", "build/consumer", "--output-on-failure")
                    for release in batch:
                        stage = checkout / "build/stage" / release["component"]
                        run(
                            checkout,
                            "cmake",
                            "--install",
                            "build/release",
                            "--prefix",
                            str(stage),
                            "--component",
                            release["component"],
                        )
                        run(
                            checkout,
                            sys.executable,
                            "tools/repo_tools/run.py",
                            "check-native-install",
                            str(stage),
                            "--component",
                            release["component"],
                        )
                        archive = checkout / (
                            f"{release['tag']}-{os.environ['RUNNER_OS']}-"
                            f"{os.environ['RUNNER_ARCH']}.zip"
                        )
                        run(stage, "cmake", "-E", "tar", "cf", str(archive), "--format=zip", ".")
                        run(
                            checkout,
                            "gh",
                            "release",
                            "upload",
                            release["tag"],
                            str(archive),
                            "--clobber",
                        )
            finally:
                run(root, "git", "worktree", "remove", "--force", str(checkout))


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("operation", choices=["plan", "python", "native"])


def execute(args: argparse.Namespace, *, root: Path) -> int:
    if args.operation == "plan":
        releases = release_plan(root, json.loads(os.environ.get("RELEASE_OUTPUTS", "{}")))
        values = {
            "tooling-sha": git("rev-parse", "HEAD", root=root).strip(),
            "releases": json.dumps(releases, separators=(",", ":")),
            "python": str(any(r["kind"] in {"python", "template"} for r in releases)).lower(),
            "native": str(any(r["kind"] == "native" for r in releases)).lower(),
        }
        if output := os.environ.get("GITHUB_OUTPUT"):
            with Path(output).open("a", encoding="utf-8") as stream:
                for name, value in values.items():
                    stream.write(f"{name}={value}\n")
        print(values["releases"])
    else:
        publish(root, json.loads(os.environ["RELEASES"]), args.operation)
    return 0
