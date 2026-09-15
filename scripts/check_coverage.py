"""Generate and enforce coverage reports for the Python and native components."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "build/coverage"
REPORT_ROOT = BUILD_ROOT / "reports"
PYTHON_REPORT_ROOT = REPORT_ROOT / "python"
NATIVE_REPORT_ROOT = REPORT_ROOT / "native"


def run_check(label: str, command: list[str]) -> int:
    """Run one coverage stage and return its exit status."""
    print(f"==> {label}", flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def percentage(covered: int, total: int) -> float:
    """Return a coverage percentage, treating an empty metric as complete."""
    return 100.0 if total == 0 else covered * 100.0 / total


def python_metrics() -> tuple[float, float, float] | None:
    """Read Python line, branch, and aggregate coverage percentages."""
    path = PYTHON_REPORT_ROOT / "coverage.json"
    if not path.exists():
        return None
    totals = json.loads(path.read_text(encoding="utf-8"))["totals"]
    return (
        percentage(totals["covered_lines"], totals["num_statements"]),
        percentage(totals["covered_branches"], totals["num_branches"]),
        totals["percent_covered"],
    )


def native_metrics() -> tuple[float, float] | None:
    """Read native line and branch coverage percentages."""
    path = NATIVE_REPORT_ROOT / "summary.json"
    if not path.exists():
        return None
    summary = json.loads(path.read_text(encoding="utf-8"))
    return summary["line_percent"], summary["branch_percent"]


def write_summary(failures: list[str]) -> None:
    """Write a GitHub-compatible Markdown summary for available reports."""
    python = python_metrics()
    native = native_metrics()
    rows = [
        "# Coverage summary",
        "",
        "| Stack | Lines | Branches | Aggregate |",
        "| --- | ---: | ---: | --- |",
    ]

    if python is None:
        rows.append("| Python | unavailable | unavailable | unavailable |")
    else:
        line, branch, aggregate = python
        rows.append(f"| Python | {line:.1f}% | {branch:.1f}% | {aggregate:.1f}% |")

    if native is None:
        rows.append("| Native C | unavailable | unavailable | — |")
    else:
        line, branch = native
        rows.append(f"| Native C | {line:.1f}% | {branch:.1f}% | — |")

    rows.extend(["", "Thresholds: `pyproject.toml` and `tools/coverage/gcovr.cfg`."])
    if failures:
        rows.extend(["", f"Failed stages: {', '.join(failures)}."])
    else:
        rows.extend(["", "All coverage tests and thresholds passed."])

    (REPORT_ROOT / "summary.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run both coverage suites and retain every report that can be generated."""
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    PYTHON_REPORT_ROOT.mkdir(parents=True)
    NATIVE_REPORT_ROOT.mkdir(parents=True)

    failures: list[str] = []
    required_tools = ("pytest", "cmake", "ctest", "ninja", "gcc", "g++", "gcov", "gcovr")
    missing_tools = [tool for tool in required_tools if shutil.which(tool) is None]
    if missing_tools:
        failures.append(f"missing tools: {', '.join(missing_tools)}")
        write_summary(failures)
        print(f"coverage checks failed: {failures[0]}", file=sys.stderr)
        return 1

    python_status = run_check(
        "Python tests and coverage",
        [
            "pytest",
            f"--cov-report=json:{PYTHON_REPORT_ROOT / 'coverage.json'}",
            f"--cov-report=xml:{PYTHON_REPORT_ROOT / 'coverage.xml'}",
            f"--cov-report=html:{PYTHON_REPORT_ROOT / 'html'}",
        ],
    )
    if python_status != 0:
        failures.append("Python coverage")

    configure_status = run_check("Configure native coverage", ["cmake", "--preset", "coverage"])
    if configure_status != 0:
        failures.append("native configuration")
    else:
        build_status = run_check(
            "Build native coverage", ["cmake", "--build", "--preset", "coverage"]
        )
        if build_status != 0:
            failures.append("native build")
        else:
            test_status = run_check("Run native coverage tests", ["ctest", "--preset", "coverage"])
            if test_status != 0:
                failures.append("native tests")

            gcovr_status = run_check(
                "Generate and enforce native coverage",
                [
                    "gcovr",
                    "--config",
                    "tools/coverage/gcovr.cfg",
                    "--object-directory",
                    str(BUILD_ROOT / "native"),
                    "--cobertura-pretty",
                    "--cobertura",
                    str(NATIVE_REPORT_ROOT / "coverage.xml"),
                    "--html-details",
                    str(NATIVE_REPORT_ROOT / "index.html"),
                    "--json-summary-pretty",
                    "--json-summary",
                    str(NATIVE_REPORT_ROOT / "summary.json"),
                ],
            )
            if gcovr_status != 0:
                failures.append("native coverage")

    write_summary(failures)
    if failures:
        print(f"coverage checks failed: {', '.join(failures)}", file=sys.stderr)
        return 1

    print(f"coverage reports written to {REPORT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
