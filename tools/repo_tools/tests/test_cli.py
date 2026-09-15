"""Every command must parse help and reject unknown arguments before doing work."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from repo_tools.cli import COMMANDS

LAUNCHER = Path(__file__).resolve().parents[1] / "run.py"


@pytest.mark.parametrize("command", COMMANDS, ids=str)
@pytest.mark.parametrize("argument,status", [("--help", 0), ("--unknown-option", 2)])
def test_cli_parses_before_effects(
    command: str, argument: str, status: int, tmp_path: Path
) -> None:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GITHUB_")}
    result = subprocess.run(
        [sys.executable, "-I", str(LAUNCHER), command, argument],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == status, result.stderr
    assert "usage:" in result.stdout + result.stderr
    assert list(tmp_path.iterdir()) == []
