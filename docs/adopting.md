# Adopt and rename the template

## Create a configured repository

Use the [repository creator](../python/apps/template_creator/docs/index.md) to download an
executable or run the Python command. Its step-by-step guide saves your identity, licensing,
ownership, and naming choices to TOML, then generates a new repository with a valid lockfile.
The creator supports Linux, Windows, and macOS on x64 and ARM64.

The following manual procedure remains available for existing checkouts and custom layouts.

## Reuse permission

See the [template's reuse permission](https://github.com/dlly11/python-c-monorepo-template/blob/main/README.md#reuse-permission). For manual adoption, choose
and document your project's license; the creator records the license chosen in its guide.

## Initialize CI and the first protected PR

Create the repository from the template and enable Actions. If GitHub emits an initial
branch-creation push, CI runs the full quality suite against the inherited baseline and skips
merged-PR verification. The release workflow skips preparation because there is no verified merge.
If no initialization run was created, manually dispatch `ci.yml` on main to validate the baseline;
that run also does not authorize a release.

Configure branch protection and merge methods using the [release guide](releases.md), then make
renaming, version, and setup changes on a feature branch. Open a PR and let its full CI and title
checks pass before merging. This first protected PR integration establishes ordinary post-merge
verification and release automation. Do not bypass the PR requirement to commit setup changes
directly to main. An initial commit's inherited subject is not retroactively rewritten.

## 1. Decide the new names

Create your repository from the template, then choose distribution, import, C API, and product names
before moving files. For example, a distribution `acme-core` can import as `acme_core` and export C
symbols beginning with `acme_`. Keep the component dependency directions described in the
[architecture guide](architecture.md).

| Naming family | Current examples | Places to update |
| --- | --- | --- |
| Product and repository | `python-c-monorepo-template`, `Python and C Monorepo Template` | Root metadata, README, docs, Sphinx title/author, Release Please package name |
| Distribution names | `example-core`, `example-package-a`, `example-package-b`, `example-package-a-cli` | Member metadata, dependency declarations, root uv sources, wheel smoke registry |
| Python import namespaces | `example_core`, `example_package_a`, `example_package_b`, `example_package_a_cli` | `src` directories, imports, tests, entry points, setuptools package data, Ruff first-party names, coverage sources, autodoc/examples |
| Component directories | `core`, `package_a`, `package_b`, `package_a_cli` | Both language trees, CMake subdirectories, release extra-files, documentation toctrees |
| C symbols, macros, and include paths | `example_*`, `EXAMPLE_*`, `example/` | Headers, sources, guards, version-header templates, tests, Doxygen/examples, native install checker |
| CMake project and package | `monorepo_template`, `MonorepoTemplate`, `example::core` | Root/component CMake, `cmake` config templates and export namespaces, install destinations, downstream consumer, docs |
| Executable names | `package-a-cli` | Python entry point and installed CLI checks; native target/output name, CTest, examples, artifact checks |
| Hosting and owners | `dlly11`, repository URL, Pages URL | README/component links, Sphinx base/source URLs, PR-template link, CODEOWNERS, reuse statement's original-repository link |

The private `monorepo-repo-tools` distribution and `repo_tools` import namespace can keep their
names when adopting the template. Keep them outside workspace membership, release registrations,
and product coverage sources; retain `repo_tools` in Ruff’s first-party names. Their private
version is independent of `version.txt`.

The Python and native CLIs currently share a command name. Use an explicit native build/install path
when testing both, or choose distinct names in the adopted project.

## 2. Rename source and update registrations

Move the relevant directories and update references by naming family. Preserve each Python package's
`py.typed` file and each native library's installed public headers.

The shared registrations are intentionally explicit. Review these when renaming, adding, or removing
a component:

- Root `pyproject.toml`: workspace membership/sources, Ruff import names, and coverage sources.
- `tools/repo_tools/src/repo_tools/python_smoke_checks.py`: each `SMOKE_CHECKS` entry owns its
  distribution's import namespace, public API example, and installed CLI cases. Update the registry
  key and executable names together when renaming an application. Add one meaningful public API
  example for every independently shipped Python package.
- `tools/repo_tools/src/repo_tools/commands/check_native_install.py`: installed version-header paths and macro prefixes.
- Root/component CMake files and `native/tests/install_consumer`: targets, exports, installed
  package names, headers, and consumer expectations.
- Release Please's `extra-files`, Sphinx/Doxygen configuration, toctrees, and tooling regression
  fixtures that contain example component names.

Regenerate workspace metadata after changing declarations:

```text
uv lock
uv sync --locked --all-packages
uv run repo-tools check-workspace
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
uv run repo-tools set-version 0.1.0
uv run repo-tools check-versions
```

Set the `"."` value in `tools/release-please/manifest.json` to that same baseline and replace the
inherited changelog with your project's initial history. The setter deliberately does not change
Release Please state, create tags, or publish a release. Subsequent releases use the normal
[release workflow](releases.md); do not reset version history in an already released fork.
Configure Pages and required checks using that guide before relying on automation.
Review `tools/github/repository-policy.json` and run
`uv run repo-tools check-github-settings --repo OWNER/REPO` after configuring the new
repository. The audit reports drift without applying settings; see the release guide for access
requirements and exit codes. Keep policy and workflow branch/check names aligned when renaming.

## 4. Find leftovers and validate

After staging renamed/new files, search tracked content (including GitHub configuration):

```bash
git grep -n -E 'example[-_:]|EXAMPLE_|MonorepoTemplate|monorepo_template|python-c-monorepo-template|dlly11' -- . ':!uv.lock'
```

Review matches rather than deleting them blindly: original-template credit, adoption examples, and
historical release notes can intentionally retain old names. Also search for your old component
directory names if you changed them.

Run the [local validation checklist](testing.md#local-validation) and
[installed native consumer](architecture.md#consuming-a-native-installation). Inspect the rendered
documentation and installed CLI output for old product names. Replace the template reporting
address in [SECURITY.md](SECURITY.md) with your own monitored private channel.

For adding components without renaming the template, use the
[architecture guide](architecture.md#adding-a-python-package).
