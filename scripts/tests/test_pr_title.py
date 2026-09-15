"""Conventional Commit subjects used by release automation."""

import sys
from types import ModuleType

import pytest


@pytest.mark.parametrize(
    "title, expected",
    [
        ("fix: handle invalid input", 0),
        ("feat(package-a): add output", 0),
        ("feat(core)!: replace API", 0),
        ("refactor!: remove deprecated API", 0),
        ("chore(main): release 1.2.3", 0),
        ("docs(native/core): explain buffers", 0),
        ("Fix: handle input", 1),
        ("feat(): missing scope", 1),
        ("feat: ", 1),
        ("feat:   ", 1),
        ("feat:  extra leading space", 1),
        ("feat: trailing space ", 1),
        ("fix: subject\rbody", 1),
        ("fix: subject\twith tab", 1),
        ("fix: subject\u2028body", 1),
        ("feat:no space", 1),
        ("update dependencies", 1),
        ("fix: subject\nbody", 1),
        ("", 1),
    ],
)
def test_title_validation(
    title: str, expected: int, scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["check_pr_title.py", title])
    assert scripts["check_pr_title"].main() == expected
