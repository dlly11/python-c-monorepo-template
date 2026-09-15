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

## Commit messages and pull requests

Use a Conventional Commit subject for every new commit and the PR title, for example
`feat(package-a): add JSON output`. Install both local hooks after synchronizing the workspace:

```bash
uv run pre-commit install
```

Run this again in existing clones: installing only the earlier `pre-commit` hook does not install
the new `commit-msg` hook. The message hook checks the first line, sharing the same policy as the
PR-title validator. Bodies and footers remain free-form. File checks run at the `pre-commit` stage.

Manual checks:

```bash
uv run python scripts/check_pr_title.py "feat(package-a): add JSON output"
COMMIT_MESSAGE_FILE=$(git rev-parse --git-path COMMIT_EDITMSG)
uv run python scripts/check_commits.py --message-file "${COMMIT_MESSAGE_FILE}"
git fetch origin
uv run python scripts/check_commits.py --base origin/main --head HEAD
```

`pre-commit run --all-files` runs file checks; it does not check a commit message. To exercise the
message hook directly, use the same resolved path:

```bash
COMMIT_MESSAGE_FILE=$(git rev-parse --git-path COMMIT_EDITMSG)
uv run pre-commit run conventional-commit --hook-stage commit-msg --commit-msg-filename "${COMMIT_MESSAGE_FILE}"
```

These shell examples use Bash (including Git Bash on Windows). Git resolves the correct path for
both ordinary clones and linked worktrees, where `.git` is a file. `COMMIT_EDITMSG` exists after a
commit attempt; before then, create a temporary text file containing your proposed subject and
pass its path instead. Quoting the path also supports directories containing spaces.

If a new commit is rejected, correct its subject and retry. For the latest existing commit, use
`git commit --amend -m "fix(core): handle empty input"`. For older commits on your PR branch, use
`git rebase -i origin/main` and mark the affected commits `reword`; resolve any `fixup!` or `squash!`
commits before submitting. Rebase onto `origin/main` when updating a branch. Default Git merge and
revert messages also fail the subject policy; supply a subject such as `revert: undo JSON output`.
After rewriting an already pushed branch, coordinate with anyone using it and push with
`git push --force-with-lease`.

The **Python quality** CI check validates the commits introduced by a PR even if local hooks were
skipped. The separate **Conventional PR title** check reruns on title edits without rerunning the
build matrix. Merge with **Squash and merge**, keeping the validated PR title as the resulting
commit subject; Release Please uses that commit to calculate the next version. Put `!` in the PR
title for breaking changes so the marker survives squashing.

Manual title workflow runs must select the open PR's current head branch in this repository and
its matching PR number. The workflow verifies the head repository, branch, and commit before
checking the live title. Ordinary PR events also validate fork PRs using their actual head commit.

The normal pytest command also runs the repository script tests. See [the release guide](releases.md)
for the allowed types, enforced ranges, GitHub settings, and release process.

## Change requirements

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
