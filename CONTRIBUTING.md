# Contributing

Keep changes within a component where possible and preserve the dependency directions documented
in `docs/architecture.md`.

Before opening a pull request, run:

```bash
uv sync --locked --all-packages
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_python.py
uv run python scripts/check_versions.py
uv run pytest

cmake --preset analysis
cmake --build --preset analysis
cmake --build --preset analysis --target format-c-check
ctest --preset analysis
```

Use a Conventional Commit pull request title such as `feat(package-a): add JSON output`; the
repository assumes squash merges and Release Please uses the resulting commit to calculate the
next version. See [the release guide](docs/releases.md) for the allowed types and release process.

Include tests for observable behaviour. Changes to public Python APIs, C headers, command-line
interfaces, or persistent formats require an explicit compatibility note in the pull request and
a breaking-change marker when compatibility cannot be preserved.
