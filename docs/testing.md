# Testing and coverage

The repository runs tests at component boundaries and enforces coverage across production Python
and native C source. Compatibility tests, static analysis, sanitizers, and coverage remain
separate CI responsibilities so each failure identifies one kind of problem.

## Native unit tests

CTest remains the native test orchestrator. The core, package A, and package B test executables use
CppUTest as their unit-test harness, while the package A CLI uses process-level CTest checks for
output and exit behaviour. Existing CTest names remain stable for filtering and CI diagnostics.

CppUTest is written in C++, so test-enabled native builds require a C++17 compiler. Public C headers
provide `extern "C"` guards for both the test harness and downstream C++ consumers. The dependency
is fetched only when `BUILD_TESTING=ON` and is excluded from installation and release archives.

## Coverage policy

| Stack | Measured scope | Required coverage |
| --- | --- | --- |
| Python | The four import packages, with branch measurement enabled | 90% aggregate |
| Native C | Source below `native/*/*/src`; C++ tests and generated files are excluded | 90% lines and 80% branches |

Python uses coverage.py through pytest-cov. Native coverage uses GCC/G++ instrumentation, gcov, and
gcovr. The native coverage preset is intentionally Linux and GCC only; the normal native matrix
continues to provide GCC, Clang, MSVC, macOS, and Windows portability checks.

Coverage gates must not be reduced merely to make a change pass. Add tests for observable
behaviour, or make a separately reviewed policy change when the existing threshold is no longer
appropriate.

## Run coverage locally

Install Python 3.12, uv, CMake, Ninja, GCC, and gcov, then run:

```bash
uv sync --locked --all-packages --group coverage
uv run --group coverage python scripts/check_coverage.py
```

The command removes only the previous `build/coverage` directory, runs both test suites, enforces
their thresholds, and writes reports beneath `build/coverage/reports`:

- `summary.md` contains the combined line and branch totals.
- `python/html/index.html` and `native/index.html` are browsable annotated reports.
- Each stack also produces JSON or Cobertura XML for automation.

To work only with the instrumented native build, use the standard presets followed by gcovr:

```bash
cmake --preset coverage
cmake --build --preset coverage
ctest --preset coverage
uv run --group coverage gcovr --config tools/coverage/gcovr.cfg \
  --object-directory build/coverage/native
```

## Continuous integration reports

The `Coverage` job runs once on Linux with Python 3.12 and GCC. Python compatibility jobs use
`--no-cov` because collecting identical data on every supported interpreter would not improve the
gate. The coverage job writes its table to the GitHub Actions job summary and retains the complete
report directory as the `coverage-reports` artifact for 14 days. Reports are uploaded even when a
test or threshold fails, when enough data was generated to create them.
