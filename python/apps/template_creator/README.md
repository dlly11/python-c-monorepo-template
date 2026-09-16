# Repository creator

Create a configured Python/C monorepository through a terminal guide or saved TOML recipe.

```bash
template-create wizard
python -m template_creator generate --config template-config.toml --output ./my-project
```

Install the release wheel with `uv tool install PATH_TO_WHEEL`, or use one of the release's
standalone executables. Both need uv >=0.10.9 for lockfile generation. Python package usage
requires Python 3.12+; executables bundle their interpreter.

See the [creation guide](https://dlly11.github.io/python-c-monorepo-template/python/apps/template_creator/docs/index.html)
for configuration, platforms, and recovery. This application is omitted from generated projects.
