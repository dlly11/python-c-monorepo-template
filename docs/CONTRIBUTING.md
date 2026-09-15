# Contributing

Keep changes within a component where possible and preserve the dependency directions documented
in `docs/architecture.md`.

Use the [workstation guide](workstation.md) for setup and diagnostics, the
[adoption guide](adopting.md) when changing template names or adding components, and the
[dependency guide](dependencies.md) when adding or upgrading libraries and tools.

Before opening a pull request, run:

```bash
uv sync --locked --all-packages
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_workspace.py
uv run python scripts/check_python.py
uv run python scripts/check_versions.py
uv run pytest
uv run python scripts/check_python_install.py
uv sync --locked --all-packages --group coverage
uv run --group coverage python scripts/check_coverage.py
uv sync --locked --all-packages --group docs
uv run --group docs python scripts/build_docs.py

cmake --preset analysis
cmake --build --preset analysis
cmake --build --preset analysis --target format-c-check
ctest --preset analysis
```

The combined coverage command requires Linux and GCC. On macOS or Windows, run the other relevant
checks locally and rely on the existing Linux coverage job for that workflow.

Use a Conventional Commit pull request title such as `feat(package-a): add JSON output`; the
repository assumes squash merges and Release Please uses the resulting commit to calculate the
next version. PR-title edits rerun the separate title check without rerunning the build matrix.
The normal pytest command also runs the repository script tests. See [the release guide](releases.md)
for the allowed types and release process.

Include tests for observable behaviour. Changes to public Python APIs, C headers, command-line
interfaces, or persistent formats require an explicit compatibility note in the pull request and
a breaking-change marker when compatibility cannot be preserved.

The Python check runs ty separately for each workspace member and then for repository scripts and
their tests. Run the workspace consistency check after changing package names, membership, source
namespaces, or shared registrations; it reports missing, stale, and duplicate entries.

Git checks out text files with LF line endings through `.gitattributes`; `.editorconfig` configures
editors to preserve LF and the repository's formatting conventions. Binary files are automatically
detected and are not converted. Keep this policy when adding new text files on Windows.

The PR template provides short prompts for the change, validation, compatibility/dependencies, and
documentation. Use N/A for sections that do not apply.

Documentation is written in MyST Markdown. Keep package and application guidance within that
component's `docs` directory, add new pages to a local toctree, and use standard fenced Mermaid
blocks so diagrams render both on GitHub and in Sphinx. The documentation build treats Sphinx and
Doxygen warnings as errors.
