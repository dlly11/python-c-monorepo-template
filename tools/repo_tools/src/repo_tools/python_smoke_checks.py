"""Explicit API and installed command checks for independently delivered Python wheels."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeCommand:
    """An executable in the wheel environment and its expected behavior."""

    executable: str
    arguments: tuple[str, ...]
    status: int = 0
    stdout: str | None = None
    stderr_contains: str | None = None


@dataclass(frozen=True)
class SmokeCheck:
    """One distribution's import namespace, API example, and optional CLI cases."""

    namespace: str
    example: str
    commands: tuple[SmokeCommand, ...] = ()


# Keep one observable API example per independently delivered component.
SMOKE_CHECKS = {
    # BEGIN TEMPLATE CREATOR ONLY
    "monorepo-template-creator": SmokeCheck(
        "template_creator",
        "from template_creator.snapshot import load\nassert load().version == expected_version\n",
        commands=(
            SmokeCommand("template-create", ("--help",)),
            SmokeCommand("template-create", ("--version",)),
            SmokeCommand("python", ("-I", "-m", "template_creator", "--help")),
        ),
    ),
    # END TEMPLATE CREATOR ONLY
    "example-core": SmokeCheck(
        "example_core",
        """
from example_core import (
    Message,
    MessageKind,
    create_message,
    normalize_name,
)
assert normalize_name(" Ada  Lovelace ") == "Ada Lovelace"
assert create_message(kind=MessageKind.GREETING, source="smoke", prefix="Hi", name="Ada") == (
    Message(kind=MessageKind.GREETING, source="smoke", text="Hi, Ada!")
)
""",
    ),
    "example-package-a": SmokeCheck(
        "example_package_a",
        """
from example_package_a import GreetingService
message = GreetingService().greet("Ada")
assert (message.kind, message.source, message.text) == ("greeting", "package_a", "Hello, Ada!")
""",
    ),
    "example-package-b": SmokeCheck(
        "example_package_b",
        """
from example_package_b import FarewellService
message = FarewellService().farewell("Ada")
assert (message.kind, message.source, message.text) == ("farewell", "package_b", "Goodbye, Ada!")
""",
    ),
    "example-package-a-cli": SmokeCheck(
        "example_package_a_cli",
        """
from example_package_a_cli.cli import build_parser
assert build_parser().parse_args(["Ada"]).name == "Ada"
""",
        commands=(
            SmokeCommand("package-a-cli", ("Ada",), stdout="Hello, Ada!\n"),
            SmokeCommand("package-a-cli", ("Ada", "--prefix", "Welcome"), stdout="Welcome, Ada!\n"),
            SmokeCommand(
                "package-a-cli",
                ("   ",),
                status=2,
                stdout="",
                stderr_contains="name must contain at least one non-whitespace character",
            ),
        ),
    ),
}

INSTALL_CHECK = """
import importlib
import importlib.metadata
import pathlib
import sys

name, namespace, expected_version = sys.argv[1:]
assert importlib.metadata.version(name) == expected_version
module = importlib.import_module(namespace)
location = pathlib.Path(module.__file__).resolve()
assert location.is_relative_to(pathlib.Path(sys.prefix).resolve()), location
assert location.with_name("py.typed").is_file(), "missing py.typed"
"""
