# Tool configuration

This directory contains configuration and support files for tools that accept an explicit path
without weakening their normal developer experience.

- `release-please/` contains Release Please's policy and version-state manifest. The release
  workflow passes both paths explicitly.
- `sphinx/` configures the repository-wide MyST, Mermaid, autodoc, and Breathe documentation site.
- `doxygen/` configures XML generation for the public native C headers consumed by Breathe.
- `github/repository-policy.json` defines the managed repository settings and required check names.
  The read-only audit and CI evidence checks share this policy.
- `coverage/` defines gcovr source filtering and the native line and branch thresholds.

Configuration based on conventional discovery remains at the repository root. In particular,
Clang tooling, EditorConfig, Git, pre-commit, uv, and CMake integrations expect their standard
filenames in the project or a parent directory. Keeping those entry points at the root lets CLIs,
editors, and language servers work without repository-specific flags.

## Script support modules

`scripts/repository_metadata.py` discovers uv members and reads shared version/Git metadata.
`scripts/python_smoke_checks.py` owns the explicit distribution API examples.
`scripts/github_api.py` provides read-only GitHub transport, and `scripts/github_checks.py` owns
policy comparison and validation evidence. Executable scripts parse arguments and orchestrate those
helpers; they do not import other command entry points. Regression tests live in `scripts/tests`.

Component additions are described in [architecture](../docs/architecture.md#adding-a-python-package).
Type/version checks discover members automatically; release, coverage, smoke, and documentation
policy still require explicit registration.
