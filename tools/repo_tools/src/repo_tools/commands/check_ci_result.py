"""Require the selected CI jobs or authoritative dispatch evidence before passing the gate."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from repo_tools.ci_validation import finish


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--record", type=Path, default=Path("build/pr-validation/validation.json"))


def run(args: argparse.Namespace, *, root: Path) -> int:
    selected = json.loads(os.environ["CI_CONTEXT"])
    finish(root, selected, args.record)
    return 0


def execute(args: argparse.Namespace, *, root: Path) -> int:
    try:
        return run(args, root=root)
    except (
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        subprocess.SubprocessError,
    ) as error:
        print(f"CI validation failed: {error}", file=sys.stderr)
        return 1
