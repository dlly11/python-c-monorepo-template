# Python package A CLI examples

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
