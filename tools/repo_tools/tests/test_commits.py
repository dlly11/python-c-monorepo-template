"""Commit enforcement against real Git histories and commit-msg input files."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def git_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., str]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)

    def git(*arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], check=True, capture_output=True, encoding="utf-8"
        ).stdout.strip()

    git("init", "--initial-branch=main")
    git("config", "user.name", "Commit tests")
    git("config", "user.email", "commits@example.invalid")
    git("commit", "--allow-empty", "-m", "Historical non-conventional subject")
    return git


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("fix: handle input\n", 0),
        ("feat(core)!: change API\n\nDetails.\n\nBREAKING CHANGE: use the new API.\n", 0),
        ("chore(main): release 1.2.3\r\n\r\nRelease notes.\r\n", 0),
        ("fix: handle input\n\n# Editor instructions\n", 0),
        ("fixup! fix: handle input\n", 1),
        ("Merge branch 'main'\n", 1),
        ("\nfix: missing first line\n", 1),
        ("fix:   \n", 1),
        ("", 1),
    ],
)
def test_message_file(
    modules: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    message: str,
    expected: int,
) -> None:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_bytes(message.encode("utf-8"))
    monkeypatch.setattr(sys, "argv", ["check_commits.py", "--message-file", str(path)])
    assert modules["check_commits"].main() == expected


def test_range_excludes_existing_history_and_reports_every_failure(
    modules: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    git_repository: Callable[..., str],
) -> None:
    git = git_repository
    base = git("rev-parse", "HEAD")
    git("commit", "--allow-empty", "-m", "fix: handle input\n\nBody with a feat: example.")
    monkeypatch.setattr(sys, "argv", ["check_commits.py", "--base", base])
    assert modules["check_commits"].main() == 0
    assert "Checked 1 commit(s); 0 invalid" in capsys.readouterr().out

    git("commit", "--allow-empty", "-m", "First invalid subject")
    git("commit", "--allow-empty", "-m", "Second invalid subject")
    assert modules["check_commits"].main() == 1
    captured = capsys.readouterr()
    assert "Checked 3 commit(s); 2 invalid" in captured.out
    assert "First invalid subject" in captured.err
    assert "Second invalid subject" in captured.err
    assert "Historical" not in captured.err


def test_pr_head_excludes_synthetic_merge_and_base_branch_commits(
    modules: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    git_repository: Callable[..., str],
) -> None:
    git = git_repository
    git("switch", "-c", "topic")
    git("commit", "--allow-empty", "-m", "feat: add feature")
    head = git("rev-parse", "HEAD")
    git("switch", "main")
    git("commit", "--allow-empty", "-m", "Unrelated base branch history")
    base = git("rev-parse", "HEAD")
    git("merge", "--no-ff", "topic", "-m", "Synthetic PR merge")

    monkeypatch.setattr(sys, "argv", ["check_commits.py", "--base", base, "--head", head])
    assert modules["check_commits"].main() == 0
    monkeypatch.setattr(sys, "argv", ["check_commits.py", "--base", base])
    assert modules["check_commits"].main() == 1


@pytest.mark.parametrize("base", ["0" * 40, "0" * 64])
def test_initial_push_checks_root_commit(
    modules: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    git_repository: Callable[..., str],
    base: str,
) -> None:
    monkeypatch.setattr(sys, "argv", ["check_commits.py", "--base", base])
    assert modules["check_commits"].main() == 1
    assert "Historical non-conventional subject" in capsys.readouterr().err


def test_manual_dispatch_on_default_branch_has_no_new_commits(
    modules: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    git_repository: Callable[..., str],
) -> None:
    git_repository("update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(sys, "argv", ["check_commits.py", "--base", "origin/main"])
    assert modules["check_commits"].main() == 0
    assert "Checked 0 commit(s)" in capsys.readouterr().out


@pytest.mark.parametrize("ref", ["missing-ref", "--all"])
def test_missing_or_option_like_ref_fails_closed(
    modules: dict[str, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    git_repository: Callable[..., str],
    ref: str,
) -> None:
    monkeypatch.setattr(sys, "argv", ["check_commits.py", f"--base={ref}"])
    assert modules["check_commits"].main() == 1
    assert "cannot validate commits" in capsys.readouterr().err


def test_missing_message_file_fails_closed(
    modules: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["check_commits.py", "--message-file", str(tmp_path / "missing")]
    )
    assert modules["check_commits"].main() == 1
