"""List configured Conventional Commit scopes and their component paths."""

import argparse
from pathlib import Path

from repo_tools.conventional_commits import scope_policy


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """No additional arguments are needed."""


def execute(args: argparse.Namespace, *, root: Path) -> int:
    scopes = scope_policy(root)
    if scopes is None:
        raise ValueError("this historical checkout does not define commit scopes")
    for name, path in sorted(scopes.items()):
        print(f"{name}: {path}")
    print("Scope is optional. Release Please selects components from changed file paths.")
    return 0
