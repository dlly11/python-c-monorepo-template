# Testing and coverage

The repository runs tests at component boundaries and enforces coverage across production Python
and native C source. Compatibility tests, static analysis, sanitizers, and coverage remain
separate CI responsibilities so each failure identifies one kind of problem.

## Python distribution checks

The Python quality job builds wheels and source distributions, then checks every wheel in a separate
temporary environment. Run the same check locally:

```bash
uv run python scripts/check_python_install.py
```

The script uses a fresh artifact directory and checks distribution names and versions before
installing. Each environment receives only its target wheel and declared dependencies. Local wheel
constraints ensure sibling dependencies come from this build without installing unrelated members.
Third-party runtime dependencies use the installer's configured indexes; the current example has
none. Build backends still need an available index or cache, as with `uv build`.
For a private index, supply uv's index environment settings so both build and isolated install
commands can access it; installs run outside the checkout and do not discover its uv configuration.

Checks run outside the checkout with isolated Python imports and no inherited `PYTHONPATH` or user
site-packages. They verify installed versions, module locations, `py.typed`, dependency consistency,
public API examples, and the installed CLI's normal, custom-prefix, and invalid-input behavior.
Failures report the package and command output and return a nonzero exit status. Temporary build
artifacts and environments are removed on both success and failure.

Add a `SMOKE_CHECKS` entry in the script when introducing a Python distribution. These checks cover
the exercised install/API paths; the ordinary component tests remain responsible for deeper behavior.
CI runs the wheel checks once in the existing Python quality job, alongside the separate Python
version test matrix. The release workflow continues to build the same distribution formats.

## Native unit tests

CTest remains the native test orchestrator. The core, package A, and package B test executables use
CppUTest as their unit-test harness, while the package A CLI uses process-level CTest checks for
output and exit behaviour. Existing CTest names remain stable for filtering and CI diagnostics.

CppUTest is written in C++, so test-enabled native builds require a C++17 compiler. Public C headers
provide `extern "C"` guards for both the test harness and downstream C++ consumers. The dependency
is fetched only when `BUILD_TESTING=ON` and is excluded from installation and release archives.

CLI process tests check exit status, standard output, and standard error independently, including
empty input. Linux additionally checks that greeting and version output fail when redirected to
`/dev/full`. UBSan findings are fatal in sanitizer builds.

## Repository script tests

Workflow regression tests mock GitHub API reads to verify release eligibility, stale/pending/failed
CI handling, manual and fork PR-title context, and GitHub policy drift. They run in the existing
pytest suite without network access or additional CI jobs. Live settings audits are manual and
read-only; see [the release guide](releases.md).

The normal `uv run pytest` command also discovers `scripts/tests`. These tests cover version
validation, version-update rollback, native install validation, commit/PR-title syntax, wheel isolation,
workspace registration consistency, and workstation diagnostics. Temporary-workspace tests cover
added/removed/renamed members, exclusions, duplicate names, namespace drift, and incorrect release
entries. Commit validation tests use real temporary Git repositories to cover introduced ranges,
legacy history, synthetic PR merges, initial pushes, and unresolved refs. They also cover message
files, multiline bodies, Windows line endings, and invalid subjects. Other tests use temporary
files and mocked subprocesses where appropriate. The
wheel-isolation regression installs tiny fixture wheels with uv in offline mode; it checks that an
undeclared dependency fails even when its source is available on `PYTHONPATH`. That regression skips
when uv is unavailable; normal development and CI runs provide uv.
Script tests do not access the network or change committed metadata.
Coverage thresholds continue to measure production packages rather than orchestration scripts.

## Coverage policy

| Stack | Measured scope | Required coverage |
| --- | --- | --- |
| Python | The four import packages, with branch measurement enabled | 90% aggregate |
| Native C | Source below `native/*/*/src`; C++ tests and generated files are excluded | 90% lines and 80% branches |

Python uses coverage.py through pytest-cov. Native coverage uses GCC/G++ instrumentation, gcov, and
gcovr. The native coverage preset is intentionally Linux and GCC only; the normal native matrix
uses GCC on Linux, Clang on macOS, and GCC/MinGW on Windows. MSVC has compiler-option support in
CMake but is not verified by the current CI matrix.

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
