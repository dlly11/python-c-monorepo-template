# Architecture and ownership

## Component model

Both language stacks demonstrate the same dependency direction:

```text
              ┌───────────┐
              │   core    │
              └─────┬─────┘
                    │
             ┌──────┴──────┐
             ▼             ▼
       ┌───────────┐ ┌───────────┐
       │ package_a │ │ package_b │
       └─────┬─────┘ └───────────┘
             │
             ▼
     ┌───────────────┐
     │ package_a_cli │
     └───────────────┘
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

## Native conventions

Native libraries expose headers under a namespaced include tree such as
`<example/package_a.h>`. Consumers link through namespaced CMake aliases:

```cmake
target_link_libraries(my_target PRIVATE example::package_a)
```

Each target receives warnings, the C17 requirement, optional sanitizers, and static-analysis
integration through `monorepo_set_project_options`. Target-level policy avoids leaking internal
compiler flags into external consumers.

Native tests are dependency-free executables registered with CTest. A real organization can
replace these with its approved C test framework without changing the component layout.

## Adding a Python package

1. Copy an existing directory under `python/packages`.
2. Give the distribution and import package organization-unique names.
3. Add the member to `[tool.uv.workspace].members` if it is outside the existing glob.
4. Declare workspace dependencies normally and add their sources to `[tool.uv.sources]`.
5. Add the project path to `scripts/check_python.py`.
6. Run `uv lock`, then the Python quality and test commands.

## Adding a native package

1. Create `native/packages/<name>/{include,src,tests}`.
2. Define a library and namespaced alias in its `CMakeLists.txt`.
3. Apply `monorepo_set_project_options` to every library, executable, and test target.
4. Link only to explicitly declared targets.
5. Add the directory to the root `CMakeLists.txt`.
6. Run the developer, analysis, and sanitizer presets.

## Cross-language integration

Keep cross-language communication at explicit boundaries. If Python calls a C executable, test
the executable's command-line or protocol contract in an integration suite. If native bindings
are eventually required, create a dedicated Python distribution for that binding rather than
making every Python package depend on the native build.
