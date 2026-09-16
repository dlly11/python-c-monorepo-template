"""Configure and create a Python/C repository from an embedded template."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from zipfile import BadZipFile

from template_creator import config, snapshot
from template_creator.generate import generate
from template_creator.render import render
from template_creator.wizard import summary, wizard


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="template-create", description=__doc__)
    parser.add_argument(
        "--version", action="store_true", help="show the bundled template version and digest"
    )
    commands = parser.add_subparsers(dest="command")
    guide = commands.add_parser("wizard", help="create a configuration step by step")
    guide.add_argument("--config", type=Path, default=Path("template-config.toml"))
    validate = commands.add_parser(
        "validate", help="validate a configuration without writing files"
    )
    validate.add_argument("--config", type=Path, required=True)
    create = commands.add_parser(
        "generate", help="generate a new repository from a saved configuration"
    )
    create.add_argument("--config", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument(
        "--dry-run", action="store_true", help="preview without writing or invoking uv"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        template = snapshot.load()
        if args.version:
            print(f"template-create {template.version}\ntemplate SHA-256: {template.digest}")
        elif args.command in {None, "wizard"}:
            if not sys.stdin.isatty():
                parser.error(
                    "wizard requires a terminal; use generate --config FILE --output DIRECTORY"
                )
            wizard(template, getattr(args, "config", Path("template-config.toml")))
        else:
            recipe = config.load(args.config, template)
            if args.command == "validate":
                print("Configuration is valid.\n" + summary(recipe))
            elif args.dry_run:
                print(summary(recipe))
                print(f"\nDestination: {args.output.absolute()}\nFiles:")
                print("\n".join(sorted(render(template, recipe))))
            else:
                generate(template, recipe, args.output)
    except (KeyboardInterrupt, EOFError):
        print("Cancelled. Any saved config is available for retry.", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, BadZipFile, subprocess.SubprocessError) as error:
        print(f"template-create: {error}", file=sys.stderr)
        return 1
    return 0
