"""The optional authoring adapter follows the shared commit policy."""

from pathlib import Path

import pytest
from commitizen.config import BaseConfig
from commitizen.exceptions import CustomError

from repo_tools.commitizen_adapter import RepositoryCz


def test_authoring_messages(independent_repository: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(independent_repository)
    adapter = RepositoryCz(BaseConfig())
    answers = {
        "type": "feat",
        "scope": "python-core",
        "description": " new API ",
        "body": "Details.",
        "breaking": True,
        "migration": "Use the new API.",
        "footer": "Refs: #123",
    }
    assert adapter.message(answers) == "\n\n".join(
        [
            "feat(python-core)!: new API",
            "Details.",
            "BREAKING CHANGE: Use the new API.",
            "Refs: #123",
        ]
    )
    assert adapter.validate_commit_message(commit_msg=adapter.message(answers)).is_valid
    assert adapter.message({"type": "fix", "scope": "", "description": "empty input"}) == (
        "fix: empty input"
    )
    with pytest.raises(CustomError):
        adapter.message({**answers, "scope": "typo"})
    with pytest.raises(CustomError):
        adapter.message({**answers, "description": "first\nsecond"})
    questions = adapter.questions()
    scope = next(q for q in questions if q["name"] == "scope")
    assert scope["type"] == "list"
    assert {"name": "python-core (python/packages/core)", "value": "python-core"} in scope[
        "choices"
    ]
