# Adopt and rename the template

## Reuse permission

You may use, copy, modify, distribute, and relicense the template's files, including for commercial
or proprietary projects. You are free to change the licensing of any template file. This permission
does not transfer ownership of the original
[python-c-monorepo-template repository](https://github.com/dlly11/python-c-monorepo-template);
do not claim ownership of that original template repository. Third-party dependencies retain their
own licensing terms.

This is the template's plain-language reuse permission. No standard license or SPDX identifier is
selected for your derived project; choose and document the terms appropriate to your own project.

## 1. Decide the new names

Create your repository from the template, then choose distribution, import, C API, and product names
before moving files. For example, a distribution `acme-core` can import as `acme_core` and export C
symbols beginning with `acme_`. Keep the component dependency directions described in the
[architecture guide](architecture.md).

| Naming family | Current examples | Places to update |
| --- | --- | --- |
| Product and repository | `python-c-monorepo-template`, `Python and C Monorepo Template` | Root metadata, README, docs, Sphinx title/author, Release Please package name |
| Distribution names | `example-core`, `example-package-a`, `example-package-b`, `example-package-a-cli` | Member metadata, dependency declarations, root uv sources, version-check registry, wheel smoke registry |
| Python import namespaces | `example_core`, `example_package_a`, `example_package_b`, `example_package_a_cli` | `src` directories, imports, tests, entry points, setuptools package data, Ruff first-party names, coverage sources, autodoc/examples |
| Component directories | `core`, `package_a`, `package_b`, `package_a_cli` | Both language trees, CMake subdirectories, script project lists, release extra-files, documentation toctrees |
| C symbols, macros, and include paths | `example_*`, `EXAMPLE_*`, `example/` | Headers, sources, guards, version-header templates, tests, Doxygen/examples, native install checker |
| CMake project and package | `monorepo_template`, `MonorepoTemplate`, `example::core` | Root/component CMake, `cmake` config templates and export namespaces, install destinations, downstream consumer, docs |
| Executable names | `package-a-cli` | Python entry point and installed CLI checks; native target/output name, CTest, examples, artifact checks |
| Hosting and owners | `dlly11`, repository URL, Pages URL | README/component links, Sphinx base/source URLs, PR-template link, CODEOWNERS, reuse statement's original-repository link |

The Python and native CLIs currently share a command name. Use an explicit native build/install path
when testing both, or choose distinct names in the adopted project.

## 2. Rename source and update registrations

Move the relevant directories and update references by naming family. Preserve each Python package's
`py.typed` file and each native library's installed public headers.

The shared registrations are intentionally explicit. Review these when renaming, adding, or removing
a component:

- Root `pyproject.toml`: workspace membership/sources, Ruff import names, and coverage sources.
- `scripts/check_versions.py`: `PROJECT_FILES`; `scripts/check_python.py`: `PROJECTS`.
- `scripts/check_python_install.py`: `SMOKE_CHECKS` and any installed CLI checks. Add one meaningful
  public API example for every independently shipped Python package.
- `scripts/check_native_install.py`: installed version-header paths and macro prefixes.
- Root/component CMake files and `native/tests/install_consumer`: targets, exports, installed
  package names, headers, and consumer expectations.
- Release Please's `extra-files`, Sphinx/Doxygen configuration, toctrees, and script regression
  fixtures that contain example component names.

Regenerate workspace metadata after changing declarations:

```text
uv lock
uv sync --locked --all-packages
uv run python scripts/check_workspace.py
```

Do not replace names manually inside `uv.lock` or generated build files. Configure into fresh build
directories after renaming native targets. Replace `@dlly11` in CODEOWNERS with your own maintainer;
add later component-specific patterns if ownership is split between teams.

The workspace checker reads the existing registrations and reports omissions; it does not generate
configuration. Follow the reported file names when correcting a missing or stale entry. Its source
discovery expects the regular `src/<namespace>/__init__.py` layout used by this template.

## 3. Set repository identity and initial version

Update the GitHub repository and Pages URLs, project descriptions, authors, and release package
name. Preserve the original-template link when explaining where the template came from; it should
not become a claim that you own the original repository.

For a newly created repository with no releases, choose an initial baseline such as `0.1.0` and run:

```text
uv run python scripts/set_version.py 0.1.0
uv run python scripts/check_versions.py
```

Set the `"."` value in `tools/release-please/manifest.json` to that same baseline and replace the
inherited changelog with your project's initial history. The setter deliberately does not change
Release Please state, create tags, or publish a release. Subsequent releases use the normal
[release workflow](releases.md); do not reset version history in an already released fork.
Configure Pages and required checks using that guide before relying on automation.

## 4. Find leftovers and validate

After staging renamed/new files, search tracked content (including GitHub configuration):

```bash
git grep -n -E 'example[-_:]|EXAMPLE_|MonorepoTemplate|monorepo_template|python-c-monorepo-template|dlly11' -- . ':!uv.lock'
```

Review matches rather than deleting them blindly: original-template credit, adoption examples, and
historical release notes can intentionally retain old names. Also search for your old component
directory names if you changed them.

Run the same package and native validation used by contributors:

```text
uv run python scripts/doctor.py --profile native
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_workspace.py
uv run python scripts/check_python.py
uv run python scripts/check_versions.py
uv run pytest
uv run python scripts/check_python_install.py
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
cmake --install build/dev --prefix build/dev/stage
uv run python scripts/check_native_install.py build/dev/stage
cmake -S native/tests/install_consumer -B build/install-consumer -G Ninja -DCMAKE_PREFIX_PATH="${PWD}/build/dev/stage"
cmake --build build/install-consumer
ctest --test-dir build/install-consumer --output-on-failure
uv sync --locked --all-packages --group docs
uv run --group docs python scripts/build_docs.py
```

Run the commands from the repository root: `${PWD}` expands to that absolute path in Bash, Zsh, and
PowerShell. The consumer configure command therefore searches the installation just created.
Run analysis and Linux coverage using the [contribution guide](CONTRIBUTING.md), then inspect the
rendered documentation and installed CLI output for old product names.
