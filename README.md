# Python and C Monorepo Template

A practical starting point maintaining multiple Python and C deliverables
in one repository. Python uses uv workspaces, setuptools, Ruff, ty, and pytest. Native code uses
CMake, CTest, CppUTest, clang-format, clang-tidy, and cppcheck.

The example is deliberately small but real: both language stacks implement the same component
graph, compile or install independently, and have tests at each boundary.

```text
core ──> package_a ──> package_a_cli
  └────> package_b
```

## Repository layout

```text
.
├── python/
│   ├── packages/
│   │   ├── core/
│   │   ├── package_a/
│   │   └── package_b/
│   └── apps/
│       └── package_a_cli/
├── native/
│   ├── packages/
│   │   ├── core/
│   │   ├── package_a/
│   │   └── package_b/
│   └── apps/
│       └── package_a_cli/
├── cmake/                       # shared compiler and analysis policy
├── docs/                        # repository-wide documentation and Sphinx landing page
├── scripts/                     # repository-level orchestration
├── tools/                       # Sphinx, Doxygen, and release tool configuration
├── CMakeLists.txt               # native build graph
├── CMakePresets.json            # dev, analysis, sanitizer, and release builds
├── pyproject.toml               # uv workspace and shared Python policy
├── version.txt                  # canonical repository version
└── uv.lock                      # committed Python dependency lock
```

The root is an orchestration layer, not a deployable product. Every directory below
`python/packages`, `python/apps`, `native/packages`, and `native/apps` represents an independently
owned component with its own public API and tests.

See [the architecture guide](docs/architecture.md) for package boundaries and dependency rules.
Start with the [workstation setup guide](docs/workstation.md) for Linux, macOS, or Windows.

## Prerequisites

- Python 3.12 or newer
- uv 0.10.9 or newer
- CMake 3.25 or newer
- Ninja
- A C17 compiler: GCC or Clang (MSVC options are provided but are not verified in CI)
- A C++17 compiler for native test builds
- clang-format, clang-tidy, and cppcheck for native quality checks
- GCC and gcov for native coverage checks
- Doxygen 1.9.2 or newer for documentation builds

The compiler and native analysis tools are intentionally system dependencies. Installing them
through the organization's approved workstation image, package mirror, or development container
keeps Python dependency resolution separate from the native toolchain.

Check your existing tools with `python scripts/doctor.py --profile all`. Use `--profile python`
for Python-only work; see [diagnostic profiles](docs/workstation.md#understanding-doctor-output)
for other workflows.

## Python workflow

```bash
uv sync --locked --all-packages
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_workspace.py
uv run python scripts/check_python.py
uv run pytest
uv run python scripts/check_python_install.py
uv run package-a-cli "Ada Lovelace"
```

`ty` runs once per workspace member, then checks repository scripts and their tests using root
configuration. This preserves package boundaries and avoids accidentally treating the entire
monorepo as one import root. The workspace checker verifies that component registrations for type
checking, coverage, smoke checks, and releases match the actual packages.

Workspace dependencies are declared as normal distribution dependencies in member
`pyproject.toml` files and resolved locally through `[tool.uv.sources]` at the repository root.
The install check builds all distributions, then exercises each wheel in its own clean environment.
See [dependency management](docs/dependencies.md) for tool versions, upgrades, and conflicting
dependency requirements.
The root uv configuration pins setuptools for both editable installations and distribution builds.

## Native workflow

Build and test the C projects:

```bash
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
./build/dev/native/apps/package_a_cli/package-a-cli Ada
./build/dev/native/apps/package_a_cli/package-a-cli --version
```

Test-enabled builds fetch the SHA-256-pinned CppUTest 4.0 source archive. Restricted environments
can supply an approved local source tree without changing project files:

```bash
cmake --preset dev -DFETCHCONTENT_SOURCE_DIR_CPPUTEST=/approved/sources/cpputest
```

Set `FETCHCONTENT_FULLY_DISCONNECTED=ON` as well when configuration must not attempt any network
access. Release builds use `BUILD_TESTING=OFF`, do not fetch CppUTest, and require only a C compiler.

Run the complete static-analysis build:

```bash
cmake --preset analysis
cmake --build --preset analysis
cmake --build --preset analysis --target format-c-check
ctest --preset analysis
```

The native CI matrix uses GCC on Linux, Clang on macOS, and GCC/MinGW on Windows. For a local
Windows Ninja build, select GCC with `CC=gcc` and `CXX=g++` in the build environment.

The analysis preset requires all three native quality tools:

- **clang-format** is exposed through `format-c` and `format-c-check` build targets.
- **clang-tidy** runs as part of every C compilation in the analysis preset.
- **cppcheck** also runs as part of every C compilation in the analysis preset.

For runtime memory and undefined-behaviour checks on GCC or Clang:

```bash
cmake --preset asan
cmake --build --preset asan
ctest --preset asan
```

## Coverage

Python coverage is branch-aware and must remain at or above 90% aggregate coverage. Native C
coverage must remain at or above 90% line and 80% branch coverage. Generate both report sets with
one command:

```bash
uv sync --locked --all-packages --group coverage
uv run --group coverage python scripts/check_coverage.py
```

Annotated HTML, machine-readable reports, and a combined summary are written beneath
`build/coverage/reports`. Native coverage uses the Linux/GCC-only `coverage` CMake preset; the
normal native matrix remains compiler- and platform-independent. See the
[testing and coverage guide](docs/testing.md) for report details and CI policy.

## Documentation

The [documentation site](https://dlly11.github.io/python-c-monorepo-template/) combines
repository guidance, MyST Markdown, Mermaid diagrams, Python autodoc, and native API references
generated by Doxygen and Breathe. Each package and application owns a `docs` directory containing
its overview and copyable examples.

Build the same warning-free HTML site used by CI and GitHub Pages:

```bash
uv sync --locked --all-packages --group docs
uv run --group docs python scripts/build_docs.py
```

Pull requests and manual CI runs validate the site; pushes to `main` build it in the Pages workflow
for deployment, avoiding a duplicate CI build.

Open `build/docs/html/index.html` after the build. Doxygen is a system prerequisite; the remaining
documentation dependencies are locked by uv in the separate `docs` dependency group.

## Pre-commit

After installing both the Python and native prerequisites:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

The install command sets up both `pre-commit` and `commit-msg` hooks. Run it again in existing
clones to enable commit-message validation. Fast file-level Ruff, ty, clang-format, and cppcheck
checks run before commits; the message hook requires a Conventional Commit subject such as
`fix(core): handle empty input`. CI also validates new commit subjects and PR titles. See
[Contributing](docs/CONTRIBUTING.md) for manual checks and correcting rejected messages.
The full compilation-database-aware clang-tidy analysis remains in the CMake analysis preset and CI.

## Versioning and releases

All Python and native components share one Semantic Versioning release number. Native CMake builds
generate and install a version header for each library and the CLI from that value. Release Please
uses Conventional Commits on `main`, with squash commit subjects taken from validated PR titles,
to maintain a reviewable release pull request,
changelog, `vX.Y.Z` tag, and GitHub Release. The release workflow also attaches Python
distributions and cross-platform native install archives.

Check the committed version metadata at any time with:

```bash
uv run python scripts/check_versions.py
```

See [the release guide](docs/releases.md) for commit conventions, the automated release sequence,
repository settings, and the exceptional manual version command.

## Template adoption checklist

Follow the [adoption and renaming guide](docs/adopting.md) for the naming table, shared registrations,
initial version setup, and validation commands.

Before using this template for a production repository:

1. Replace the `example-*` distribution names and `example_*` import packages.
2. Replace example components with organization-owned domains and assign CODEOWNERS.
3. Choose and document licensing terms for your derived project using the permission below.
4. Pin approved compiler and analysis-tool versions in the corporate build image.
5. Configure an internal Python index and native dependency source if required.
6. Add artifact signing, SBOM, vulnerability scanning, and provenance policies expected by the
   organization, then configure trusted publishing for the chosen artifact registry.
7. Protect `main` and require the Python, native, analysis, and sanitizer CI jobs.

## Reuse permission

You may use, copy, modify, distribute, and relicense the template's files, including for commercial
or proprietary projects. You are free to change the licensing of any template file. This permission
does not transfer ownership of the original
[python-c-monorepo-template repository](https://github.com/dlly11/python-c-monorepo-template);
do not claim ownership of that original template repository. Third-party dependencies retain their
own licensing terms.

## Why C is separate from Python packaging

The example C libraries and executables are independent deliverables; they are not Python
extension modules. Consequently, `uv sync` never needs a compiler and the native build does not
depend on Python packaging internals. Cross-language integration can be added explicitly through
subprocess, RPC, files, or a separately designed stable C API when a real product requires it.
