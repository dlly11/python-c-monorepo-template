"""Commit enforcement against real Git histories and commit-msg input files."""

from collections.abc import Callable
from pathlib import Path

import pytest

from repo_tools import cli


@pytest.fixture
def git_repository(
    repository: Path, monkeypatch: pytest.MonkeyPatch, git: Callable[..., str]
) -> Callable[..., str]:
    monkeypatch.chdir(repository)

    git("init", "--initial-branch=main")
    git("config", "user.name", "Commit tests")
    git("config", "user.email", "commits@example.invalid")
    git("commit", "--allow-empty", "-m", "Historical non-conventional subject")
    return git


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("fix: handle input\n", 0),
        (
            "\n\n".join(
                [
                    "feat(python-core)!: change API",
                    "Details.",
                    "BREAKING CHANGE: use the new API.\n",
                ]
            ),
            0,
        ),
        ("chore: release main\r\n\r\nRelease notes.\r\n", 0),
        ("fix: handle input\n\n# Editor instructions\n", 0),
        ("fixup! fix: handle input\n", 1),
        ("Merge branch 'main'\n", 1),
        ("\nfix: missing first line\n", 1),
        ("fix:   \n", 1),
        ("", 1),
    ],
)
def test_message_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    message: str,
    expected: int,
) -> None:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_bytes(message.encode("utf-8"))
    arguments = ["check-commits", "--message-file", str(path)]
    assert cli.main(arguments) == expected


def test_range_excludes_existing_history_and_reports_every_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    git_repository: Callable[..., str],
) -> None:
    git = git_repository
    base = git("rev-parse", "HEAD")
    git("commit", "--allow-empty", "-m", "fix: handle input\n\nBody with a feat: example.")
    arguments = ["check-commits", "--base", base]
    assert cli.main(arguments) == 0
    assert "Checked 1 commit(s); 0 invalid" in capsys.readouterr().out

    git("commit", "--allow-empty", "-m", "First invalid subject")
    git("commit", "--allow-empty", "-m", "Second invalid subject")
    assert cli.main(arguments) == 1
    captured = capsys.readouterr()
    assert "Checked 3 commit(s); 2 invalid" in captured.out
    assert "First invalid subject" in captured.err
    assert "Second invalid subject" in captured.err
    assert "Historical" not in captured.err


def test_pr_head_excludes_synthetic_merge_and_base_branch_commits(
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

    arguments = ["check-commits", "--base", base, "--head", head]
    assert cli.main(arguments) == 0
    arguments = ["check-commits", "--base", base]
    assert cli.main(arguments) == 1


@pytest.mark.parametrize("base", ["0" * 40, "0" * 64])
def test_initial_push_checks_root_commit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    git_repository: Callable[..., str],
    base: str,
) -> None:
    arguments = ["check-commits", "--base", base]
    assert cli.main(arguments) == 1
    assert "Historical non-conventional subject" in capsys.readouterr().err


def test_manual_dispatch_on_default_branch_has_no_new_commits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    git_repository: Callable[..., str],
) -> None:
    git_repository("update-ref", "refs/remotes/origin/main", "HEAD")
    arguments = ["check-commits", "--base", "origin/main"]
    assert cli.main(arguments) == 0
    assert "Checked 0 commit(s)" in capsys.readouterr().out


@pytest.mark.parametrize("ref", ["missing-ref", "--all"])
def test_missing_or_option_like_ref_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    git_repository: Callable[..., str],
    ref: str,
) -> None:
    arguments = ["check-commits", f"--base={ref}"]
    assert cli.main(arguments) == 1
    assert "cannot validate commits" in capsys.readouterr().err


def test_missing_message_file_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    arguments = ["check-commits", "--message-file", str(tmp_path / "missing")]
    assert cli.main(arguments) == 1


@pytest.mark.parametrize("advance_base", [False, True])
@pytest.mark.parametrize("invalid_subject", [False, True])
def test_update_branch_merge_checks_its_regular_commits(
    git_repository: Callable[..., str],
    capsys: pytest.CaptureFixture[str],
    advance_base: bool,
    invalid_subject: bool,
) -> None:
    git = git_repository
    git("switch", "-c", "dependabot/update")
    git(
        "commit",
        "--allow-empty",
        "-m",
        "Invalid change" if invalid_subject else "chore(deps): update",
    )
    git("switch", "main")
    git("commit", "--allow-empty", "-m", "Unrelated base history")
    base = git("rev-parse", "HEAD")
    git("switch", "dependabot/update")
    git("merge", "--no-ff", "main", "-m", "Merge branch 'main' into dependabot/update")
    head = git("rev-parse", "HEAD")
    if advance_base:
        git("switch", "main")
        git("commit", "--allow-empty", "-m", "More base history")
        base = git("rev-parse", "HEAD")
    assert cli.main(["check-commits", "--base", base, "--head", head]) == int(invalid_subject)
    captured = capsys.readouterr()
    assert "Exempt base-branch synchronization merge" in captured.out
    assert "Unrelated base history" not in captured.err
    assert ("Invalid change" in captured.err) == invalid_subject


@pytest.mark.parametrize("kind", ["ordinary", "side-branch", "reverse", "octopus"])
def test_merge_subject_alone_cannot_bypass_policy(
    git_repository: Callable[..., str], kind: str
) -> None:
    git = git_repository
    base = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    topic = git("commit-tree", tree, "-p", base, "-m", "fix: change")
    side = git("commit-tree", tree, "-p", base, "-m", "fix: other change")
    parents = {
        "ordinary": [topic],
        "side-branch": [topic, side],
        "reverse": [base, topic],
        "octopus": [topic, base, side],
    }[kind]
    head = git(
        "commit-tree",
        tree,
        *(arg for parent in parents for arg in ("-p", parent)),
        "-m",
        "Merge branch 'main' into topic",
    )
    assert cli.main(["check-commits", "--base", base, "--head", head]) == 1
