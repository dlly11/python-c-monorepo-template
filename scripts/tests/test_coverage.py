"""Preserve coverage output when prerequisites prevent a new run."""

from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def coverage(
    tmp_path: Path, scripts: dict[str, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> ModuleType:
    module = scripts["check_coverage"]
    build = tmp_path / "coverage"
    reports = build / "reports"
    for name, path in {
        "BUILD_ROOT": build,
        "REPORT_ROOT": reports,
        "PYTHON_REPORT_ROOT": reports / "python",
        "NATIVE_REPORT_ROOT": reports / "native",
    }.items():
        monkeypatch.setattr(module, name, path)
    return module


@pytest.mark.parametrize("existing", [False, True])
def test_missing_prerequisites_leave_outputs_untouched(
    coverage: ModuleType,
    existing: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if existing:
        coverage.REPORT_ROOT.mkdir(parents=True)
        (coverage.REPORT_ROOT / "summary.md").write_bytes(b"Previous passing results\r\n")
        (coverage.REPORT_ROOT / "report.html").write_bytes(b"Previous report\n")
    before = {path: path.read_bytes() for path in coverage.BUILD_ROOT.rglob("*") if path.is_file()}
    monkeypatch.setattr(coverage.shutil, "which", lambda tool: None if tool == "gcovr" else tool)
    run = Mock()
    monkeypatch.setattr(coverage.subprocess, "run", run)
    assert coverage.main([]) == 1
    assert before == {
        path: path.read_bytes() for path in coverage.BUILD_ROOT.rglob("*") if path.is_file()
    }
    assert coverage.BUILD_ROOT.exists() == existing
    output = capsys.readouterr().err
    assert "missing tools: gcovr" in output
    assert "No fresh results generated" in output
    assert "existing coverage reports are unchanged" in output
    run.assert_not_called()


@pytest.mark.parametrize("failed", [False, True])
def test_successful_preflight_replaces_old_reports_and_reports_stage_results(
    coverage: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    failed: bool,
) -> None:
    coverage.REPORT_ROOT.mkdir(parents=True)
    previous = coverage.REPORT_ROOT / "old.html"
    previous.write_text("old report", encoding="utf-8")
    monkeypatch.setattr(coverage.shutil, "which", lambda tool: tool)
    labels = []

    def run_check(label: str, command: list[str]) -> int:
        assert not previous.exists()
        assert coverage.PYTHON_REPORT_ROOT.is_dir()
        assert coverage.NATIVE_REPORT_ROOT.is_dir()
        labels.append(label)
        if label == "Python tests and coverage":
            (coverage.PYTHON_REPORT_ROOT / "coverage.json").write_text(
                '{"totals":{"covered_lines":1,"num_statements":1,"covered_branches":0,'
                '"num_branches":0,"percent_covered":100}}',
                encoding="utf-8",
            )
            return int(failed)
        if label == "Generate and enforce native coverage":
            (coverage.NATIVE_REPORT_ROOT / "summary.json").write_text(
                '{"line_percent":100,"branch_percent":100}',
                encoding="utf-8",
            )
        return 0

    monkeypatch.setattr(coverage, "run_check", run_check)
    assert coverage.main([]) == int(failed)
    assert "Generate and enforce native coverage" in labels
    summary = (coverage.REPORT_ROOT / "summary.md").read_text()
    assert "100.0%" in summary
    assert (
        "Failed stages: Python coverage." if failed else "All coverage tests and thresholds passed."
    ) in summary
