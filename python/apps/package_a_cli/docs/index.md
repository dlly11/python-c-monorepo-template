# Python package A CLI

`example-package-a-cli` exposes the greeting service as the `package-a-cli` command. The
application depends on package A and keeps argument parsing at the application boundary.

## Python package A CLI examples

Run the console script from the synchronized uv workspace:

```console
$ uv run package-a-cli "Ada Lovelace"
Hello, Ada Lovelace!
```

Select a different greeting prefix:

```console
$ uv run package-a-cli --prefix Welcome "Grace Hopper"
Welcome, Grace Hopper!
```

The same application can be invoked as a Python module:

```bash
uv run python -m example_package_a_cli Ada
```

## Python package A CLI API

The API page documents the import-safe parser and entry point. The executable `__main__` module
is intentionally excluded from autodoc.

```{automodule} example_package_a_cli.cli
:members:
```
