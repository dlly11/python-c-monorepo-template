# Testing and coverage

The repository runs tests at component boundaries and enforces coverage across production Python
and native C source. Compatibility tests, static analysis, sanitizers, and coverage remain
separate CI responsibilities so each failure identifies one kind of problem.

## Local validation

Run from the repository root after [workstation setup](workstation.md). This full checklist assumes
Linux/GCC. Coverage runs the Python and native tests; a separate pytest invocation is unnecessary.

```bash
uv run pre-commit run --all-files
uv sync --locked --all-packages --group coverage --group docs
uv run --no-sync python scripts/check_versions.py
uv run --no-sync python scripts/check_python_install.py
uv run --no-sync python scripts/check_coverage.py
uv run --no-sync python scripts/build_docs.py
cmake --preset analysis
cmake --build --preset analysis
cmake --build --preset analysis --target format-c-check
cmake --preset asan
cmake --build --preset asan
ctest --preset asan
```

On macOS or Windows, replace the coverage command with `uv run pytest --no-cov` and the `dev`
configure/build/CTest presets. The sanitizer preset is unavailable on Windows. For native changes,
also exercise the [installed consumer](architecture.md#consuming-a-native-installation).

For a focused Python change, use `uv run pytest --no-cov PATH_TO_TESTS` during development. Build
documentation with `uv run --group docs python scripts/build_docs.py` and open
`build/docs/html/index.html`; Sphinx and Doxygen warnings fail the build.

## PR and post-merge responsibilities

| Event | Quality work | Commit subjects | Release eligibility |
| --- | --- | --- | --- |
| Pull request | Full suite and separate title check | PR head commits outside the event's base SHA | Tested evidence for the later merge |
| Manual CI | Full suite on selected branch | Commits outside `origin/main` (none on main) | Explicit recovery only on current main |
| Ordinary main push | Merged PR verification and version check | New squash/merge subjects and preserved PR commits | Latest successful verified push on current main |
| Initial branch creation (zero previous SHA) | Full suite; no validation record | Inherited history is the baseline and is skipped | Never |

Python 3.12 runs in **Coverage**; compatibility jobs cover 3.13 and 3.14. Required check names live
in `tools/github/repository-policy.json`. Pages builds/deploys independently on main. Release builds
and smoke-tests tagged artifacts without repeating the PR test and analysis suite.

Push CI on `main` runs only `Merged PR verification`. It walks the new first-parent history (the
sequence of integrations onto main), accepting squash commits and two-parent merge commits. For
each integration it checks the subject, finds its merged GitHub PR, verifies that the original head
has a successful CI run with every required CI job completed successfully, and compares the merged
Git tree with the recorded tested tree. A merge commit must have the PR head as its second parent;
the verifier also checks subjects of the preserved PR commits newly introduced to main. Intermediate
PR commits do not need their own validation records: CI certifies the final integrated contents.
Skipped checks are not accepted as passing. Version metadata is checked without installing tools
or rebuilding packages. The other CI jobs appear skipped on push runs because they already ran
on the PR.

The Python quality job uploads a small `pr-validation` JSON record of the actual checkout and
tree, tied to its repository, run ID, and original head SHA. This distinguishes the PR's synthetic
merge commit from the eventual squash or merge commit while verifying identical tracked contents. Normal
PR runs and full manually dispatched release-branch runs both produce this record. It is validation
metadata, not a distributable build artifact. Release distributions are built from their tag.

The verifier reads records from the selected CI run only, fails on missing or expired evidence,
and never executes downloaded content. GitHub's repository artifact retention applies. Original
runs can be retried only within [30 days of their initial run](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).
Within that window, rerun the original PR CI including Python quality, then retry push CI. A partial
rerun can reuse the quality job's record from the same run and immutable head.

After that window, or when the original run is unavailable, use the explicit
[release evidence recovery procedure](releases.md): run fresh manual
CI on current main, then supply its run ID to a manual Release dispatch. This exercises the full
suite on the exact merged commit. Missing evidence never counts as success, and the failed
historical push run is not rewritten as passing. Before merging a long-lived PR, push a new
Conventional Commit to obtain fresh PR validation if the original run can no longer be retried.

CI regressions cover both merge methods with matching trees, content mismatches, wrong parents or
subjects, mixed merge methods in one push, wrong runs, missing/skipped jobs, release-bot manual
dispatches, fork PRs, and unavailable artifacts. These
tests run in the existing pytest suite. The post-merge job needs contents, actions, and pull-request
read permissions. Documentation deployment continues to build and deploy independently.

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
Installation runs from the selected project root so uv discovers its index configuration. Pass
credentials through uv's supported environment settings; the wheel environment is still explicitly
selected and separate from the workspace.

Checks run outside the checkout with isolated Python imports and no inherited `PYTHONPATH` or user
site-packages. They verify installed versions, module locations, `py.typed`, dependency consistency,
public API examples, and the installed CLI's normal, custom-prefix, and invalid-input behavior.
API/CLI checks time out after ten seconds; uv build/install commands after five minutes.
Failures report the package and command output and return a nonzero exit status. Temporary build
artifacts and environments are removed on both success and failure.

Add a `SMOKE_CHECKS` entry in `scripts/python_smoke_checks.py` when introducing a Python distribution. These checks cover
the exercised install/API paths; the ordinary component tests remain responsible for deeper behavior.
CI runs the wheel checks once in the existing Python quality job, alongside the separate Python
version test matrix. The release workflow continues to build the same distribution formats.

To smoke-test already-built release wheels without rebuilding them, run
`uv run python scripts/check_python_install.py --dist dist`. Release CI uses this mode before
uploading the exact wheels it checked. Use `--project-root CHECKOUT` to select version metadata
and build/index configuration from another checkout; see [asset recovery](releases.md#recovering-missing-release-assets). This validates the published artifacts while the full
unit-test and analysis suite remains on PRs.

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

Each first-party native CTest test, including the installed consumer, has a 60-second execution
limit. The CLI output-comparison helper additionally stops its child process after ten seconds
and reports the executable and limit. These limits apply to local builds and CI.

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

The command first checks that required tools are available. Missing prerequisites return a failure
without changing existing reports or creating a new report directory; the error explicitly states
that no fresh results were generated. Previous reports still describe their original run.

After preflight succeeds, the command removes the previous `build/coverage` directory, runs both
test suites, enforces their thresholds, and writes reports beneath `build/coverage/reports`:

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

The `Coverage` job runs once on Linux with Python 3.12 and GCC and provides the Python 3.12 test
result. Python 3.13 and 3.14 compatibility jobs use
`--no-cov` because collecting identical data on every supported interpreter would not improve the
gate. The coverage job writes its table to the GitHub Actions job summary and retains the complete
report directory as the `coverage-reports` artifact for 14 days. Reports are uploaded even when a
test or threshold fails, when enough data was generated to create them.

## Native release smoke checks

`python scripts/check_native_install.py PREFIX` validates the version headers and runs the exact
installed CLI for `--version` and a greeting. Missing executables, nonzero exits, unexpected output,
and ten-second execution timeouts fail the check. The command must run on the target platform.

Both PR native jobs and release publishing also build the existing C++ consumer against the
Release installation and run its CTest check. Pass `-DMONOREPO_INSTALL_PREFIX=ABSOLUTE_PREFIX` when
configuring the consumer; package discovery is restricted to that installation. This catches missing
libraries, broken exports, and link/runtime failures without repeating the full unit-test suite in
release jobs. Failed checks prevent packaging and upload.

## Workflow linting

The Python quality job runs `uv run pre-commit run actionlint --all-files`. Local commits use the
same actionlint hook for changed workflow files. Its version is pinned in the pre-commit config;
optional ShellCheck and Pyflakes integrations are disabled so installed optional tools do not
change the result. No separate workflow-lint job is required.
