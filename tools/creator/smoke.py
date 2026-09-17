"""Exercise actual creator entry points and optionally validate their generated project."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

from template_creator.config import save, validate
from template_creator.snapshot import SOURCE_URL, load


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--full", action="store_true")
    parser.add_argument(
        "--cpputest-source", type=Path, help="local CppUTest source for full checks"
    )
    args = parser.parse_args()
    root = args.work_dir.resolve()
    root.mkdir(parents=True)
    snapshot = load()
    slug = "acme-research-repository-with-a-long-name"
    config = validate(
        {
            "schema_version": 1,
            "project": {
                "name": (
                    'Acme "Research 研究" — an international collaboration for scientific '
                    "software, infrastructure, and reproducible experiments"
                ),
                "slug": slug,
                "description": "Research tools.",
                "prefix": "acme_research_infrastructure_lab",
                "version": "0.2.0",
            },
            "github": {
                "owner": "acme",
                "repository": slug,
                "docs_url": "https://acme.invalid/docs/",
            },
            "author": {
                "name": "Ada Researcher and the International Collaboration for "
                "Scientific Software, Infrastructure, and Reproducible Experiments",
                "email": "ada+research@acme.invalid",
            },
            "security": {"contact": "security@acme.invalid"},
            "ownership": {"default": ["@ada"], "rules": []},
            "license": {"choice": "MIT", "holder": "Acme Research", "year": 2026, "text": ""},
            "template": {
                "version": snapshot.version,
                "digest": snapshot.digest,
                "source": SOURCE_URL,
            },
        },
        snapshot,
    )
    recipe = root / "recipe.toml"
    save(config, recipe)
    command = (
        [str(args.executable.resolve())]
        if args.executable
        else [sys.executable, "-I", "-m", "template_creator"]
    )
    environment = dict(os.environ)
    for variable in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        environment.pop(variable, None)
    if args.executable:
        uv = shutil.which("uv")
        if uv is None:
            raise ValueError("uv is required")
        # Only uv is on PATH: the executable must supply its own Python runtime.
        commands_dir = root / "commands"
        commands_dir.mkdir()
        shutil.copyfile(uv, commands_dir / Path(uv).name)
        (commands_dir / Path(uv).name).chmod(0o755)
        # uv's long-shebang wrappers use these standard POSIX utilities.
        if os.name != "nt":
            for utility in ("realpath", "dirname"):
                executable = shutil.which(utility)
                if executable is None:
                    raise ValueError(f"missing standard utility: {utility}")
                (commands_dir / utility).symlink_to(executable)
        environment["PATH"] = str(commands_dir)
    for arguments in (
        ["--help"],
        ["edit", "--help"],
        ["--version"],
        ["validate", "--config", str(recipe)],
        ["generate", "--config", str(recipe), "--output", str(root / "generated project")],
    ):
        subprocess.run([*command, *arguments], cwd=root, env=environment, check=True, timeout=600)
    if not args.full:
        return
    project = root / "generated project"
    environment["PATH"] = os.environ["PATH"]
    # Doxygen can exit successfully after configuration warnings, even with
    # WARN_AS_ERROR enabled. Check parsing explicitly for the quoted display name.
    doxygen = subprocess.run(
        ["doxygen", "-x", "tools/doxygen/Doxyfile"],
        cwd=project,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
        timeout=30,
    )
    if doxygen.stderr.strip():
        raise ValueError(f"generated Doxygen configuration has warnings:\n{doxygen.stderr}")
    commands = [
        ["uv", "sync", "--locked", "--all-packages", "--group", "docs"],
        ["uv", "run", "--no-sync", "ruff", "check", "."],
        ["uv", "run", "--no-sync", "ruff", "format", "--check", "."],
        ["uv", "run", "--no-sync", "repo-tools", "check-python"],
        ["uv", "run", "--no-sync", "pytest", "--no-cov"],
        ["uv", "build", "--all-packages", "--out-dir", "build/distributions"],
        [
            "uv",
            "run",
            "--no-sync",
            "repo-tools",
            "check-python-install",
            "--dist",
            "build/distributions",
        ],
        ["cmake", "--preset", "dev"],
        ["cmake", "--build", "--preset", "dev"],
        ["cmake", "--build", "--preset", "dev", "--target", "format-c-check"],
        ["ctest", "--preset", "dev"],
        ["cmake", "--install", "build/dev", "--prefix", "build/stage"],
        ["uv", "run", "--no-sync", "repo-tools", "check-native-install", "build/stage"],
        [
            "cmake",
            "-S",
            "native/tests/install_consumer",
            "-B",
            "build/consumer",
            "-G",
            "Ninja",
            f"-DMONOREPO_INSTALL_PREFIX={project / 'build/stage'}",
        ],
        ["cmake", "--build", "build/consumer"],
        ["ctest", "--test-dir", "build/consumer", "--output-on-failure"],
        ["uv", "run", "--no-sync", "repo-tools", "build-docs"],
    ]
    for command in commands:
        if args.cpputest_source and command == ["cmake", "--preset", "dev"]:
            command.extend(
                [
                    f"-DFETCHCONTENT_SOURCE_DIR_CPPUTEST={args.cpputest_source.resolve()}",
                    "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
                ]
            )
        print("==>", " ".join(command), flush=True)
        subprocess.run(command, cwd=project, env=environment, check=True, timeout=900)
    wheels = list((project / "build/distributions").glob("*.whl"))
    if len(wheels) != 4:
        raise ValueError("generated project must distribute exactly its four example components")
    for wheel in wheels:
        with ZipFile(wheel) as archive:
            metadata = BytesParser().parsebytes(
                archive.read(
                    next(
                        name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
                    )
                )
            )
            licenses = [name for name in archive.namelist() if name.endswith("/licenses/LICENSE")]
            if metadata["License-Expression"] != "MIT" or len(licenses) != 1:
                raise ValueError(f"{wheel.name}: missing license metadata/text")
            if archive.read(licenses[0]) != (project / "LICENSE").read_bytes():
                raise ValueError(f"{wheel.name}: incorrect license text")
    if not (project / f"build/stage/share/licenses/{slug}/LICENSE").is_file():
        raise ValueError("native installation is missing its license")


if __name__ == "__main__":
    main()
