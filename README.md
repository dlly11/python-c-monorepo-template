# Python and C Monorepo Template

A small working example of independently packaged Python and native C components, with shared
quality policy, documentation, and lockstep releases. Python uses uv workspaces; native code uses
CMake and CTest. The C deliverables are independent libraries and executables.

```text
core ──> package_a ──> package_a_cli
  └────> package_b
```

## Quick start

Install the prerequisites for your platform using the [workstation guide](docs/workstation.md).
From the repository root:

```bash
uv sync --locked --all-packages
uv run package-a-cli "Ada Lovelace"
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
./build/dev/native/apps/package_a_cli/package-a-cli Ada
```

Native tests require a C++ compiler and CppUTest. See [offline native builds](docs/native-quality.md#cpputest-dependency-policy)
when dependencies must come from an approved local source.

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
├── tools/                       # private repo-tools package and tool configuration
├── CMakeLists.txt               # native build graph
├── CMakePresets.json            # dev, analysis, sanitizer, and release builds
├── pyproject.toml               # uv workspace and shared Python policy
├── version.txt                  # canonical repository version
└── uv.lock                      # committed Python dependency lock
```

## Guides

- [Documentation site](https://dlly11.github.io/python-c-monorepo-template/): component examples and API references.
- [Contributing](docs/CONTRIBUTING.md): development workflow, commit policy, and pull requests.
- [Testing](docs/testing.md): local checks, coverage, and CI responsibilities.
- [Architecture](docs/architecture.md): component boundaries, new packages, and native consumption.
- [Dependencies](docs/dependencies.md): shared environments, conflicts, and tool upgrades.
- [Releases](docs/releases.md): version metadata, GitHub settings, and recovery.
- [Adopting the template](docs/adopting.md): naming, registration, and initialization.
- [Security](docs/SECURITY.md): private vulnerability reporting.

## Reuse permission

You may use, copy, modify, distribute, and relicense the template's files, including for commercial
or proprietary projects. You are free to change the licensing of any template file. This permission
does not transfer ownership of the original
[python-c-monorepo-template repository](https://github.com/dlly11/python-c-monorepo-template);
do not claim ownership of that original template repository. Third-party dependencies retain their
own licensing terms.
