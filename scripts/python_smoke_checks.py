"""Explicit public API examples for independently delivered Python wheels."""

# Keep one observable API example per independently delivered component.
SMOKE_CHECKS = {
    "example-core": (
        "example_core",
        """
from example_core import Message, MessageKind, create_message, normalize_name
assert normalize_name(" Ada  Lovelace ") == "Ada Lovelace"
assert create_message(kind=MessageKind.GREETING, source="smoke", prefix="Hi", name="Ada") == (
    Message(kind=MessageKind.GREETING, source="smoke", text="Hi, Ada!")
)
""",
    ),
    "example-package-a": (
        "example_package_a",
        """
from example_package_a import GreetingService
message = GreetingService().greet("Ada")
assert (message.kind, message.source, message.text) == ("greeting", "package_a", "Hello, Ada!")
""",
    ),
    "example-package-b": (
        "example_package_b",
        """
from example_package_b import FarewellService
message = FarewellService().farewell("Ada")
assert (message.kind, message.source, message.text) == ("farewell", "package_b", "Goodbye, Ada!")
""",
    ),
    "example-package-a-cli": (
        "example_package_a_cli",
        """
from example_package_a_cli.cli import build_parser
assert build_parser().parse_args(["Ada"]).name == "Ada"
""",
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
