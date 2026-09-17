"""Check independently versioned components, or a historical lockstep checkout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from repo_tools.components import CONFIG, component_errors, legacy_config, load_components
from repo_tools.repository_metadata import repository_version, version_errors


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register command arguments without performing any work."""
    parser.add_argument("--tag", help="require a matching component release tag")
    parser.add_argument("--component", help="check one component ID (default: all)")


def execute(args: argparse.Namespace, *, root: Path) -> int:
    """Run the version consistency check."""

    try:
        config_path = root / CONFIG
        legacy = not config_path.exists() or legacy_config(json.loads(config_path.read_text()))
        if legacy:
            if args.component:
                raise ValueError("historical lockstep checkouts do not have component IDs")
            expected = repository_version(root)
            errors = version_errors(root, expected, args.tag)
            report = f"all repository components use version {expected}"
        else:
            errors = component_errors(root, args.component, args.tag)
            report = "\n".join(
                f"{c.id}: {c.version(root)}"
                for c in load_components(root)
                if not args.component or c.id == args.component
            )
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(f"version check failed: {error}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"version check failed: {error}", file=sys.stderr)
        return 1

    print(report)
    return 0
