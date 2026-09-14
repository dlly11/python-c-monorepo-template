# Tool configuration

This directory contains configuration and support files for tools that accept an explicit path
without weakening their normal developer experience.

- `release-please/` contains Release Please's policy and version-state manifest. The release
  workflow passes both paths explicitly.

Configuration based on conventional discovery remains at the repository root. In particular,
Clang tooling, EditorConfig, Git, pre-commit, uv, and CMake integrations expect their standard
filenames in the project or a parent directory. Keeping those entry points at the root lets CLIs,
editors, and language servers work without repository-specific flags.
