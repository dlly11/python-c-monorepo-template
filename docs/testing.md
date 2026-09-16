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
uv run --no-sync repo-tools check-versions
uv run --no-sync repo-tools check-python-install
uv run --no-sync repo-tools check-coverage
uv run --no-sync repo-tools build-docs
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
documentation with `uv run --group docs repo-tools build-docs` and open
`build/docs/html/index.html`; Sphinx and Doxygen warnings fail the build.

## PR and post-merge responsibilities

| Event | Quality work | Commit subjects | Release eligibility |
| --- | --- | --- | --- |
| Pull request | Full suite and separate title check | PR head commits outside the event's base SHA | Tested evidence for the later merge |
| Manual CI | Full suite on selected branch | Commits outside `origin/main` (none on main) | Explicit recovery only on current main |
| Ordinary main push | Merged PR verification and version check | New squash/merge subjects and preserved or rebased PR commits | Latest successful verified push on current main |
| Initial branch creation (zero previous SHA) | Full suite; no validation record | Inherited history is the baseline and is skipped | Never |

Python 3.12 runs in **Coverage** on Linux/GCC; compatibility jobs cover 3.13 and 3.14 with
`--no-cov` to avoid collecting the same coverage on every interpreter. Required check names live
in `tools/github/repository-policy.json`. Pages builds/deploys independently on main. Release
builds and smoke-tests tagged artifacts without repeating the PR test and analysis suite.

Push CI on `main` runs only `Merged PR verification`. It walks the new first-parent history backward
from the push head, accepting squash commits, two-parent merge commits, and rebased PR sequences.
For each integration it checks the subjects, finds its merged GitHub PR, verifies that the original head
has a successful CI run with every required CI job completed successfully, and compares the merged
Git tree with the recorded tested tree. A merge commit must have the PR head as its second parent;
the verifier also checks subjects of the preserved PR commits newly introduced to main. Intermediate
PR commits do not need their own validation records: CI certifies the final integrated contents.

For a rebase, GitHub's `merge_commit_sha` identifies the final rewritten commit. The verifier groups
the contiguous preceding commits using GitHub's [commit-to-PR associations](https://docs.github.com/en/rest/commits/commits#list-pull-requests-associated-with-a-commit),
validates each subject, and compares only the final tree with the PR record. Every new first-parent
commit must be accounted for, and push boundaries must contain complete PR integrations. Missing
or ambiguous associations within the push fail verification; no commit is skipped merely because
the final contents match. Original and rewritten commit counts or SHAs need not match to reuse CI.

Skipped checks are not accepted as passing. Version metadata is checked without installing tools
or rebuilding packages. The other CI jobs appear skipped on push runs because they already ran
on the PR.

The Python quality job uploads a small `pr-validation` JSON record of the actual checkout and
tree, tied to its repository, run ID, and original head SHA. This distinguishes the PR's synthetic
merge commit from the final integrated commit while verifying identical tracked contents. Normal
PR runs and full manually dispatched release-branch runs both produce this record. It is validation
metadata, not a distributable build artifact. Release distributions are built from their tag.

The verifier reads records from the selected CI run only, fails on missing or expired evidence,
and never executes downloaded content. GitHub's repository artifact retention applies. See
[CI evidence recovery](releases.md#recovering-expired-ci-evidence) for retry limits, rerunning
original validation, and authorizing recovery from fresh CI on current main.

The post-merge job needs contents, actions, and pull-request read permissions.

## Python distribution checks

The Python quality job builds wheels and source distributions, then checks every wheel in a separate
temporary environment. Run the same check locally:

```bash
uv run repo-tools check-python-install
```

The command uses a fresh artifact directory and checks distribution names and versions before
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

The same command separately builds and installs the private `repo-tools` package. Its smoke checks
verify console and module help outside the checkout and a version check against an explicit target.
The tooling wheel uses its own version and artifact directory.

Add a `SMOKE_CHECKS` entry in
[python_smoke_checks.py](../tools/repo_tools/src/repo_tools/python_smoke_checks.py) when introducing
a product distribution. Each `SmokeCheck` holds its import namespace, API example, and optional
`SmokeCommand` cases for installed executables. Command cases specify the executable name without
a platform suffix, arguments, and expected exit status/output. Keep CLI expectations in that entry when renaming
or adding an application; the installer runs those cases from the isolated environment rather
than matching product names. These checks cover the exercised install/API paths; ordinary
component tests remain responsible for deeper behavior.
CI runs the wheel checks once in the existing Python quality job, alongside the separate Python
version test matrix. The release workflow continues to build the same distribution formats.

To smoke-test already-built release wheels without rebuilding them, run
`uv run repo-tools check-python-install --dist dist`. Release CI uses this mode before
uploading the exact wheels it checked. This mode checks product artifacts only and does not build
or install private tooling. Put `--project-root CHECKOUT` before `check-python-install` to select
version metadata and build/index configuration from another checkout; see
[asset recovery](releases.md#recovering-missing-release-assets). This validates the published artifacts
while the full unit-test and analysis suite remains on PRs.

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

## Private tooling tests

The normal `uv run pytest` command discovers `tools/repo_tools/tests`, covering:

- GitHub policy, commit/title validation, all three merge methods, CI evidence, and release recovery.
- Workspace registrations, product version consistency, and version-update rollback.
- Installed artifacts, checkout selection, isolated Python environments, and prerequisite failures.

Tests use temporary files, real local Git repositories and virtual environments, and mocked GitHub
API reads. They do not access the network or change committed metadata. The wheel-isolation
regression uses uv offline to verify that undeclared imports fail even with source on `PYTHONPATH`;
it skips when uv is unavailable. Normal development and CI provide uv.

Private tooling is linted, type-checked, and tested in the existing jobs; coverage thresholds
measure product code. Live GitHub settings audits are manual and read-only; see the
[release guide](releases.md).

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
uv run --group coverage repo-tools check-coverage
```

For an approved local CppUTest tree, add `--cpputest-source PATH`; see the
[offline native setup](native-quality.md#cpputest-dependency-policy). Preconfiguring a CMake cache
with a local source is insufficient because coverage cleans its build directory before each run.

Coverage rejects platforms other than Linux before probing dependencies or changing outputs.
Documentation and coverage check that the selected checkout's first-party packages and required
Python tools are available through the running interpreter, including documentation extensions
and the theme. They run Python tools as isolated modules, so another `pytest`, `gcovr`, or `sphinx`
executable on PATH cannot select a different environment. Coverage also checks its native executables.

These prerequisite failures leave existing reports unchanged. Follow the reported sync and rerun
commands; previous reports still describe their original run. A later build or test failure can
leave partial output. `--project-root` selects checkout files, not a Python environment; see the
[package guide](../tools/repo_tools/README.md#checkout-and-python-environment).

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

The `Coverage` job writes its table to the GitHub Actions job summary and retains the complete
report directory as the `coverage-reports` artifact for 14 days. Reports are uploaded even when a
test or threshold fails, when enough data was generated to create them. See
[CI responsibilities](#pr-and-post-merge-responsibilities) for interpreter assignments.

## Native release smoke checks

`python tools/repo_tools/run.py check-native-install PREFIX` validates the version headers and runs the exact
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

<!-- BEGIN TEMPLATE CREATOR ONLY -->
## Repository creator validation

Creator tests run in the existing Python suite. Six **Repository creator (PLATFORM-ARCH)** jobs
build and smoke-test executables with only uv on PATH. The Linux x64 job additionally validates
a generated project, including Python quality/tests/wheels, native tests/install/consumer, and docs.
All six jobs are required upstream; generated repositories omit those jobs and policy entries.
The existing `check-python` command also type-checks the build helpers in `tools/creator`.

Build and check a local executable with:

```bash
uv sync --locked --all-packages --group creator-build
uv run --no-sync python tools/creator/check_inventory.py
uv run --no-sync python tools/creator/build.py --target linux-x64
uv run --no-sync python tools/creator/smoke.py --work-dir build/creator/full --full
```

Use the matching `linux`, `windows`, or `macos` and `x64` or `arm64` target for your host.
The full smoke check requires Linux and the normal native/documentation prerequisites. Choose
an unused work directory for each run. Builds include the tracked-file inventory, source-distribution
round-trip tests, wheel smoke checks, and existing version/registration checks.
<!-- END TEMPLATE CREATOR ONLY -->
