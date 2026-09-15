"""Preserve coverage output when prerequisites prevent a new run."""

from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from repo_tools import cli
from repo_tools.commands import check_coverage


@pytest.fixture
def coverage(repository: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, Path]:
    module = check_coverage
    monkeypatch.setattr(module, "check_environment", lambda *args, **kwargs: None)
    return module, repository / "build/coverage"


@pytest.mark.parametrize("existing", [False, True])
def test_missing_prerequisites_leave_outputs_untouched(
    coverage: tuple[ModuleType, Path],
    existing: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module, build = coverage
    reports = build / "reports"
    if existing:
        reports.mkdir(parents=True)
        (reports / "summary.md").write_bytes(b"Previous passing results\r\n")
        (reports / "report.html").write_bytes(b"Previous report\n")
    before = {path: path.read_bytes() for path in build.rglob("*") if path.is_file()}
    monkeypatch.setattr(module.shutil, "which", lambda tool: None if tool == "gcov" else tool)
    run = Mock()
    monkeypatch.setattr(module.subprocess, "run", run)
    assert cli.main(["check-coverage"], default_root=build.parents[1]) == 1
    assert before == {path: path.read_bytes() for path in build.rglob("*") if path.is_file()}
    assert build.exists() == existing
    output = capsys.readouterr().err
    assert "missing tools: gcov" in output
    assert "No fresh results generated" in output
    assert "existing coverage reports are unchanged" in output
    run.assert_not_called()


@pytest.mark.parametrize("failed", [False, True])
def test_successful_preflight_replaces_old_reports_and_reports_stage_results(
    coverage: tuple[ModuleType, Path],
    monkeypatch: pytest.MonkeyPatch,
    failed: bool,
) -> None:
    module, build = coverage
    reports = build / "reports"
    reports.mkdir(parents=True)
    previous = reports / "old.html"
    previous.write_text("old report", encoding="utf-8")
    monkeypatch.setattr(module.shutil, "which", lambda tool: tool)
    labels = []

    def run_check(label: str, command: list[str], *, root: Path) -> int:
        assert not previous.exists()
        assert (reports / "python").is_dir()
        assert (reports / "native").is_dir()
        labels.append(label)
        if label == "Python tests and coverage":
            ((reports / "python") / "coverage.json").write_text(
                '{"totals":{"covered_lines":1,"num_statements":1,"covered_branches":0,'
                '"num_branches":0,"percent_covered":100}}',
                encoding="utf-8",
            )
            return int(failed)
        if label == "Generate and enforce native coverage":
            ((reports / "native") / "summary.json").write_text(
                '{"line_percent":100,"branch_percent":100}',
                encoding="utf-8",
            )
        return 0

    monkeypatch.setattr(module, "run_check", run_check)
    assert cli.main(["check-coverage"], default_root=build.parents[1]) == int(failed)
    assert "Generate and enforce native coverage" in labels
    summary = (reports / "summary.md").read_text()
    assert "100.0%" in summary
    assert (
        "Failed stages: Python coverage." if failed else "All coverage tests and thresholds passed."
    ) in summary
