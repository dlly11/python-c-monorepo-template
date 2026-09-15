# Private repository tooling

This standard `src`-layout package contains the repository's maintenance commands and their tests.
It has no runtime dependencies. It is an editable development dependency, not a released workspace
component; its private version is independent of the product version.

From the repository root:

```bash
uv sync --locked --all-packages
uv run repo-tools --help
uv run repo-tools check-versions
uv run repo-tools doctor --profile python
```

The installed CLI and `python -m repo_tools` discover a checkout from the current directory.
To select another checkout, put `--project-root PATH` before the command:

```bash
uv run repo-tools --project-root ../another-checkout check-versions
```

Before installing dependencies, CI and workstation diagnostics use the one source launcher:

```bash
python tools/repo_tools/run.py doctor --profile all
python tools/repo_tools/run.py check-versions
```

The launcher defaults to its containing checkout. Its explicit `--project-root` option can target
another checkout, including an old release. Help and standalone message checks need no checkout.
Relative file arguments are relative to the working directory, regardless of the selected root.

`commands/` contains argument parsers and implementations; package-level modules hold shared helpers.
Commands receive the checkout explicitly and do not change the process working directory.
Tests live alongside `src/` and are included in the normal repository pytest run.

See the [workstation guide](../../docs/workstation.md), [testing guide](../../docs/testing.md), and
[release guide](../../docs/releases.md) for workflows. CLI help is the reference for command options.
