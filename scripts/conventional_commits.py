"""Shared Conventional Commit subject policy for commit messages and PR titles."""

from __future__ import annotations

import re

SUBJECT_PATTERN = re.compile(
    r"(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?!?: \S(?:.*\S)?"
)


def valid_subject(subject: str) -> bool:
    """Require a supported lowercase type and a nonempty, single-line description."""
    return (
        len(subject.splitlines()) == 1
        and not any(ord(character) < 32 or ord(character) == 127 for character in subject)
        and SUBJECT_PATTERN.fullmatch(subject) is not None
    )
