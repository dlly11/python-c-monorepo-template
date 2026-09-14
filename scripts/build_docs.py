"""Build the complete Python and native API documentation site."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "build/docs"


def main() -> int:
    """Generate Doxygen XML and build warning-free Sphinx HTML."""
    required_tools = ("cmake", "doxygen", "ninja")
    tools = {tool: shutil.which(tool) for tool in required_tools}
    missing_tools = [tool for tool, path in tools.items() if path is None]
    if missing_tools:
        print(
            f"documentation build failed: missing tools: {', '.join(missing_tools)}",
            file=sys.stderr,
        )
        return 1

    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    BUILD_ROOT.mkdir(parents=True)

    try:
        subprocess.run(
            [
                str(tools["cmake"]),
                "-S",
                str(ROOT),
                "-B",
                str(BUILD_ROOT / "native"),
                "-G",
                "Ninja",
                "-DBUILD_TESTING=OFF",
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [str(tools["doxygen"]), str(ROOT / "tools/doxygen/Doxyfile")],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "sphinx",
                "-W",
                "--keep-going",
                "-b",
                "html",
                "-c",
                str(ROOT / "tools/sphinx"),
                str(ROOT),
                str(BUILD_ROOT / "html"),
            ],
            cwd=ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        return error.returncode

    print(f"documentation written to {BUILD_ROOT / 'html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
