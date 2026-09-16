"""Build a creator executable from its installed wheel and package release assets."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]


def run(*arguments: str) -> None:
    subprocess.run(list(arguments), cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        choices=[
            f"{os}-{arch}" for os in ("linux", "windows", "macos") for arch in ("x64", "arm64")
        ],
    )
    args = parser.parse_args()
    host = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}[platform.system()]
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}[
        platform.machine().lower()
    ]
    if args.target != f"{host}-{arch}":
        parser.error(f"target {args.target} does not match build host {host}-{arch}")
    version = (ROOT / "version.txt").read_text().strip()
    build = ROOT / "build/creator" / args.target
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    wheel_dir = build / "wheels"
    run(
        "uv",
        "build",
        "--package",
        "monorepo-template-creator",
        "--out-dir",
        str(wheel_dir),
    )
    wheel = next(wheel_dir.glob("*.whl"))
    application = build / "application"
    run("uv", "pip", "install", "--no-deps", "--target", str(application), str(wheel))
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "template-create",
        "--noupx",
        "--paths",
        str(application),
        "--collect-data",
        "template_creator",
        "--distpath",
        str(build / "bin"),
        "--workpath",
        str(build / "freeze"),
        "--specpath",
        str(build),
        str(application / "template_creator/__main__.py"),
    )
    binary = build / "bin" / ("template-create.exe" if host == "windows" else "template-create")
    run(
        sys.executable,
        str(ROOT / "tools/creator/smoke.py"),
        "--executable",
        str(binary),
        "--work-dir",
        str(build / "smoke"),
    )
    notices = build / "notices"
    notices.mkdir()
    for dependency in ("tomlkit", "pyinstaller"):
        distribution = importlib.metadata.distribution(dependency)
        for file in distribution.files or []:
            if "license" in file.name.lower() or file.name == "COPYING.txt":
                destination = notices / dependency / str(file)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(distribution.locate_file(file)), destination)
    for source in (ROOT / "tools/creator/notices").iterdir():
        shutil.copyfile(source, notices / source.name)
    output = ROOT / "dist/creator"
    output.mkdir(parents=True, exist_ok=True)
    name = f"template-create-v{version}-{args.target}.zip"
    with ZipFile(output / name, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(binary, binary.name)
        archive.write(ROOT / "python/apps/template_creator/README.md", "README.md")
        for file in sorted(notices.rglob("*")):
            if file.is_file():
                archive.write(file, "licenses/" + file.relative_to(notices).as_posix())
    checksum = hashlib.sha256((output / name).read_bytes()).hexdigest()
    (output / (name + ".sha256")).write_text(f"{checksum}  {name}\n", encoding="utf-8")
    print(output / name)


if __name__ == "__main__":
    main()
