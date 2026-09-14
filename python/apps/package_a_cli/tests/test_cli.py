"""Tests for the Python Package A CLI."""

import pytest

from example_package_a_cli import main


def test_cli_prints_greeting(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["Ada Lovelace"]) == 0
    assert capsys.readouterr().out == "Hello, Ada Lovelace!\n"


def test_cli_accepts_custom_prefix(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--prefix", "Welcome", "Grace"]) == 0
    assert capsys.readouterr().out == "Welcome, Grace!\n"
