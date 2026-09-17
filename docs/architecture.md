# Architecture and ownership

## Component model

Both language stacks demonstrate the same dependency direction:

```mermaid
flowchart TD
    core[core]
    packageA[package_a]
    packageB[package_b]
    packageACLI[package_a_cli]

    core --> packageA
    core --> packageB
    packageA --> packageACLI
```

- `core` defines shared value types, status contracts, and low-level utilities.
- `package_a` and `package_b` are sibling domain packages. They can depend on `core`, but not on
  one another.
- `package_a_cli` is an application boundary and may depend on `package_a`. Libraries must never
  depend on applications.

These rules keep changes local, make ownership clear, and avoid a collection of packages that is
a monolith in disguise.

## Python conventions

Each Python component is a PEP 517 project with its own `pyproject.toml`, `src` layout, import
namespace, dependencies, and tests. The repository root owns only shared development policy and
the uv workspace.

Use normalized distribution names and unambiguous organization-prefixed import names:

| Component | Distribution | Import package |
| --- | --- | --- |
| Core | `example-core` | `example_core` |
| Package A | `example-package-a` | `example_package_a` |
| Package B | `example-package-b` | `example_package_b` |
| Package A CLI | `example-package-a-cli` | `example_package_a_cli` |

Every dependency must appear in the consuming member's `[project].dependencies`, even though a
shared development environment may make undeclared imports appear to work locally.

Each component owns documentation beneath its own `docs` directory. The repository-level Sphinx
site assembles those pages without moving component-specific guidance into a central hierarchy.

## Native conventions

Native libraries expose behavioural and generated version headers under a namespaced include tree,
such as `<example/package_a.h>` and `<example/package_a_version.h>`. Consumers link through
namespaced CMake aliases:

```cmake
target_link_libraries(my_target PRIVATE example::package_a)
```

Each production target receives warnings, the C17 requirement, optional sanitizers, and
static-analysis integration through `monorepo_set_project_options`. CppUTest targets receive the
corresponding test-only C++17 policy. Target-level policy avoids leaking internal compiler flags
into external consumers.

Native library tests use CppUTest and are registered with CTest; application boundary tests remain
direct CTest process checks. CppUTest is fetched only for test-enabled builds and is excluded from
installed artifacts. Public C headers use `extern "C"` guards so both the harness and downstream
C++ programs can link to the C implementation.

## Adding a Python package

1. Copy an existing directory under `python/packages`.
2. Give the distribution and import package organization-unique names.
3. Add the member to `[tool.uv.workspace].members` if it is outside the existing glob.
4. Declare workspace dependencies normally and add their sources to `[tool.uv.sources]`.
5. Choose its own initial version and add a `python` strategy entry with a unique `component` ID
   under its path in the Release Please config. Add the same path/version to the manifest and a
   component `CHANGELOG.md`. The ID automatically becomes an allowed commit scope.
   If retaining the upstream template release, add the new path to its `exclude-paths` too.
6. Add the import package to
   coverage's `source` list and Ruff's `known-first-party` list in the root `pyproject.toml`.
7. Add a `SmokeCheck` to `SMOKE_CHECKS` in `tools/repo_tools/src/repo_tools/python_smoke_checks.py`,
   with a public API example and `SmokeCommand` cases for any installed CLI.
8. Create `docs/index.md` with overview, examples, and API reference; link it from `docs/index.md`.
   Retain a distribution README with a short usage example and absolute documentation URL.
9. Run `uv lock`, `uv run repo-tools check-workspace`, and the relevant
   [local checks](testing.md#local-validation).

The workspace checker expands uv member/exclude globs and discovers distribution names and regular
packages at `src/<namespace>/__init__.py`. It verifies smoke namespaces, coverage/Ruff names, and
Release Please's version entries, reporting missing, stale, or duplicate registrations. Overlapping
globs are deduplicated and excluded directories ignored. These remaining registrations describe
policy or examples that cannot be inferred from membership alone.

The checker is read-only and uses the standard library. It runs in Python quality CI and the local
workspace-consistency hook. This template uses regular src-layout packages; adopting namespace
packages or another layout also requires updating discovery. Native registrations retain their
existing CMake and install checks; documentation links are validated by the Sphinx build.

## Adding a native package

1. Create `native/packages/<name>/{include,src,tests}`.
2. Define a library and namespaced alias in its `CMakeLists.txt`.
3. Add a component-owned version-header template and register it with
   `monorepo_add_version_header`.
4. Apply `monorepo_set_project_options` to production C targets and
   `monorepo_set_cpp_test_options` to CppUTest executables.
5. Link only to explicitly declared targets and register the test with CTest.
6. Create a component `version.txt` and `CHANGELOG.md`; register its path, unique ID, and `simple`
   strategy in Release Please and seed its manifest version. Call `monorepo_component` before
   creating its version header, and `monorepo_install_component` with its dependency targets.
   Give it a unique CMake package name, `EXPORT_NAME`, and build/install include directories.
7. Add the directory to the root `CMakeLists.txt`.
8. Register the installed version header and macro prefix in `tools/repo_tools/src/repo_tools/commands/check_native_install.py`.
   Extend `native/tests/install_consumer` to link and exercise the new library and version header.
9. Create component-owned `docs` pages and link their index from `docs/index.md`. Add the public
   include directory to `tools/doxygen/Doxyfile`; generated headers are already discovered from
   the shared generated include tree.
10. Run the developer, analysis, sanitizer, and coverage presets, then verify a clean install with
    the external consumer and build the documentation site.

## Consuming a native installation

Build and install the release artifacts, then configure the example downstream consumer using only
an installation prefix:

```bash
cmake --preset release
cmake --build --preset release
cmake --install build/release --prefix stage
cmake -S native/tests/install_consumer -B build/install-consumer -G Ninja \
  -DMONOREPO_INSTALL_PREFIX="$PWD/stage"
cmake --build build/install-consumer
ctest --test-dir build/install-consumer --output-on-failure
```

Each library has a separate CMake package and archive:

| Component | CMake package | Imported target |
| --- | --- | --- |
| Core | `ExampleCore` | `example::core` |
| Package A | `ExamplePackageA` | `example::package_a` |
| Package B | `ExamplePackageB` | `example::package_b` |
| CLI | `ExamplePackageACli` | `example::package_a_cli` |

```cmake
find_package(ExamplePackageA 2 CONFIG REQUIRED)
target_link_libraries(my_target PRIVATE example::package_a)
```

Install dependency archives into the same prefix (or include their prefixes in `CMAKE_PREFIX_PATH`).
Package A/B locate core using their built-against minimum version and the same major version;
an absent, older, or different-major dependency fails configuration. The CLI is statically linked
and runs from its own archive without installing library archives. Archives include version headers,
license text, and `share/<component>/component-versions.txt` provenance. The installed tree is relocatable.

**Migration:** replace `find_package(MonorepoTemplate)` with the packages you consume. The old
aggregate config has been removed; target names remain unchanged. Use a clean install prefix to
avoid stale configs, and set `CMAKE_PREFIX_PATH` instead of the old `MonorepoTemplate_DIR`.
Configs now live under `<libdir>/cmake/<PackageName>`. See [releases](releases.md) for rebuild policy.

## Cross-language integration

Keep cross-language communication at explicit boundaries. If Python calls a C executable, test
the executable's command-line or protocol contract in an integration suite. If native bindings
are eventually required, create a dedicated Python distribution for that binding rather than
making every Python package depend on the native build.

<!-- BEGIN TEMPLATE CREATOR ONLY -->
## Repository creator

The upstream-only `monorepo-template-creator` application is a normal Python workspace member
with the template's release version. It has no dependency on the example packages or private
maintenance package. Its wheel includes a versioned snapshot assembled from explicitly classified
canonical files during standard PEP 517 builds; source distributions retain that snapshot.

The renderer updates the four example components and removes the creator's registrations,
workflows, and documentation from generated projects. This keeps the working repository as the
single template source. See the [creator guide](../python/apps/template_creator/docs/index.md).
<!-- END TEMPLATE CREATOR ONLY -->
