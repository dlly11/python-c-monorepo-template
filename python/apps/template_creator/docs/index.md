# Create a repository

The creator turns this working template into a new project using your names, ownership,
license, and GitHub identity. A terminal guide saves a portable TOML recipe, then uses that
saved file to generate the project. Both languages and the four example components are retained.

## Download or run with Python

Download a `template-create-vVERSION-PLATFORM-ARCH.zip` from
[GitHub Releases](https://github.com/dlly11/python-c-monorepo-template/releases).
Verify its accompanying `.sha256` file, then extract the archive. On Linux/macOS, make the
extracted executable runnable with `chmod +x template-create` if your extractor did not
preserve its permissions. Run it in a terminal; on Windows use `template-create.exe`.

| Download | Build/test baseline |
| --- | --- |
| `linux-x64`, `linux-arm64` | Ubuntu 22.04; glibc 2.35 or newer |
| `windows-x64` | Windows Server 2022 build runner; modern x64 Windows |
| `windows-arm64` | Windows 11 ARM64 |
| `macos-x64` | macOS 15 Intel |
| `macos-arm64` | macOS 14 Apple Silicon |

Linux executables target glibc, not Alpine/musl. Each archive contains one executable,
usage instructions, and dependency notices. Windows binaries have no publisher signature;
macOS binaries have only the bundler's ad-hoc signature and are not notarized. Windows
SmartScreen or macOS Gatekeeper may show trust prompts or block a downloaded executable.
Use your operating system's per-file approval flow only after verifying its origin, or use
Python instead. SHA-256 checksums detect file changes; they are not publisher signatures.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) >=0.10.9 first. The
executable bundles Python; `uv` may download an interpreter and dependency metadata during
creation. Generation also obtains isolated Ruff and clang-format tools through uv. Ruff uses
the generated lockfile's version, as does clang-format, whose pin is in the root lint group.
The generated project's hooks and CMake formatting targets use the same uv-managed formatter.
No compiler or Git
installation is needed to create the files.

To install the release wheel as a command:

```text
uv tool install ./monorepo_template_creator-VERSION-py3-none-any.whl
template-create wizard
```

To run the wheel through Python without installing it globally:

```text
uv run --no-project --python 3.12 --with ./monorepo_template_creator-VERSION-py3-none-any.whl python -m template_creator wizard
```

From this repository's source checkout:

```bash
uv sync --locked --all-packages
uv run template-create wizard
# Equivalent module entry point:
uv run python -m template_creator wizard
```

## Guided setup

`template-create` with no arguments starts the same wizard as `template-create wizard`.
The guide requires a terminal; automation should use the config commands below.

1. Set the display name, repository slug, description, shared prefix, and initial version.
2. Set the GitHub owner and documentation URL.
3. Provide the author name and public email.
4. Choose a separate private vulnerability-reporting email or HTTPS URL.
5. Provide default CODEOWNERS and optional path rules. Later matching rules take precedence.
6. Choose a license and copyright holder/year.

Review the derived names and public contact details, edit any section, then save the config.
The final prompt offers generation now or saving for later. No repository is created before
saving. Existing configuration files are never overwritten; use `wizard --config ANOTHER.toml`.
Ctrl+C cancels. A config already saved remains available if generation fails or is cancelled.
Yes/no prompts also accept `y` and `n`; unrecognized answers prompt again.

To revise a saved recipe with the same creator release:

```bash
template-create edit --config template-config.toml --output revised-config.toml
template-create generate --config revised-config.toml --output ./revised-project
```

Editing opens the same review and section choices and saves a new file; it does not generate a
project or overwrite either file. It can repair invalid field values in a structurally valid
recipe. Malformed TOML, unknown fields, unsupported schemas, and template identity mismatches
must be resolved before editing. Cancellation leaves the original file intact. Editing requires
a terminal, and the output's parent directory must already exist.

To correct CODEOWNERS, edit section 5. Enter the complete list of owners you want to keep
to replace a displayed list; pressing Enter keeps it unchanged. At least one default owner
is required. Each existing path rule has keep, edit, and remove options, so you can delete
one rule without re-entering the others. Invalid owner syntax is rejected at the owner prompt.
Managed usernames such as `@ada_acme` are supported. Use the username for Enterprise Managed
Users: GitHub does not resolve CODEOWNERS email entries to managed accounts. For other accounts,
an email must belong to the intended GitHub account. Owners need write access; teams must also be
visible. After pushing, use `repo-tools check-github-settings --extended` to read GitHub's own
CODEOWNERS diagnostics. See [GitHub's ownership rules](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).

All contact details in the recipe are intended for published project files. Do not put tokens,
passwords, private keys, or other credentials in the recipe.

## Saved configuration

The wizard produces `template-config.toml`. All listed sections/fields are required; optional
values use empty arrays or the empty custom-license string. Unknown fields are rejected so
typographical errors cannot silently change the output.

| Section | Fields and behavior |
| --- | --- |
| Top level | `schema_version = 1` |
| `project` | `name`, `slug`, `description`, `prefix`, `version` |
| `github` | `owner`, `repository` (same as `project.slug`), `docs_url` |
| `author` | `name`, `email`; written to distribution metadata and documentation |
| `security` | `contact`: email or HTTPS URL; written to the security policy |
| `ownership` | `default`: nonempty owner array; `rules`: ordered array of `{pattern, owners}` tables |
| `license` | `choice`, `holder`, integer `year`, `text` |
| `template` | `version`, `digest`, `source`; supplied by the creator, identifying its embedded template |

Slugs use at most 100 characters, matching GitHub's repository-name limit, with lowercase
hyphen-separated words starting with a letter. The wizard checks this at the slug prompt.
Prefixes use lowercase
letters/digits with optional underscores, starting with a letter; Python keywords, Windows
reserved names, and template/tooling names are rejected. The shared prefix is limited to
32 characters, including underscores. This is a creator naming policy, not a guarantee against
platform path-length limits. Earlier creators accepted longer prefixes; shorten those names
when creating a recipe for this release. Names are never truncated automatically.
Human-readable names may contain
Unicode and punctuation. GitHub identities and CODEOWNERS are syntax-checked locally; users
must still configure their actual repositories and grant owners access.

The public author email must be a valid package-author mailbox. Ordinary addresses,
plus-addressed emails such as `ada+research@example.com`, and personal GitHub noreply addresses
are supported. The unquoted `41898282+github-actions[bot]@users.noreply.github.com` address used
for bot Git commits is not valid package metadata. Validation reports `author.email` before
generation; correct that field in the guide or saved recipe. Addresses are never rewritten.

The shared prefix `acme_lab` yields `acme-lab-core`, `acme_lab_core`, C symbols beginning
`acme_lab_`, macros beginning `ACME_LAB_`, `<acme_lab/core.h>`, `acme_lab::core`, and the
CMake package `AcmeLab`. Both CLIs become `acme-lab-package-a-cli`. Component directories
remain `core`, `package_a`, `package_b`, and `package_a_cli`.

| Name | Example | Meaning |
| --- | --- | --- |
| Repository slug | `research-tools` | Repository name in `acme/research-tools`; not the owner or full URL |
| Shared prefix | `acme_lab` | Naming input shared by Python and C components |
| Distribution | `acme-lab-core` | Name used when installing a Python package |
| Import namespace | `acme_lab_core` | Name used in Python `import` statements |
| C prefix | `acme_lab_` | Prefix for exported C symbols |
| CMake package | `AcmeLab` | Name passed to `find_package` |

Changing the slug or owner in the guide updates a documentation URL that still matches the
previous GitHub Pages default. A custom URL remains unchanged.
The documentation URL updates links and Sphinx metadata; it does not configure hosting.
See [GitHub setup](../../../../docs/github-setup.md#documentation-hosting) for default Pages,
custom Pages domains, and external hosts. HTTPS URLs may use an explicit port from 1 to 65535.

The initial version defaults to `0.1.0`. For this new project, dependency lower bounds between
workspace members start at that baseline. Private `repo-tools` keeps its independent version.
Subsequent releases follow the project's normal release workflow.

Choose `MIT`, `Apache-2.0`, `BSD-3-Clause`, `Proprietary`, or `Custom`. Proprietary produces a
copyright/all-rights-reserved notice. For Custom, the wizard reads a UTF-8 license file and
embeds its complete text in `license.text`; replay does not need the original file. For other
choices, `license.text` is empty. Built-in license texts come from GitHub's
[Choose a License](https://github.com/github/choosealicense.com) catalog. Third-party dependency
licenses remain separate from the chosen first-party license.

When editing the license section, the wizard keeps previously loaded custom text by default.
Choose to replace it only when you want to load another file.

```bash
template-create validate --config template-config.toml
template-create generate --config template-config.toml --output ./acme --dry-run
template-create generate --config template-config.toml --output ./acme
```

Validation and previews do not invoke uv, access the network, or write files. Actual generation
requires a nonexistent destination with an existing parent directory. Paths are relative to
the command's working directory. A preview checks the same destination constraints, including
rejecting dangling symlinks, but does not resolve dependencies or guarantee write access.
Template identity mismatches require the original release
executable/wheel, or a newly created config; editing identity fields is not an upgrade procedure.
Source-checkout configs also change identity when canonical template inputs change.

## Generated repository and recovery

Generation stages files, regenerates `uv.lock` with uv, formats renamed code, and runs the
workspace/version checks before publishing the destination. It does not rewrite lockfile text.
Failures preserve the recipe and existing user files and clean up owned staging files during
normal exception handling. A forced process kill can leave a `.template-create-*` staging
directory or a partially transferred destination; inspect and remove only that abandoned output
before retrying. Publication is a guarded transfer, not a filesystem-wide atomic transaction.

The resulting project includes its license, updated metadata/docs/tests, ownership/security
policies, CI, release automation, and private maintenance tools. It excludes the creator and its
build machinery. A copy of the config records provenance; changing it does not update project
files, and the creator never overwrites an existing project.

Follow the generated `docs/adopting.md` to set up Git, an empty GitHub repository, Pages,
required checks, branch protection, and the first protected PR. Creation does not push files,
create tags, or apply GitHub settings. Full development validation still requires the documented
Python/native toolchain.

For offline use, prepopulate uv's interpreter, resolver, backend, and formatter caches, and set
`UV_OFFLINE=1`. The template itself is always embedded; no template download is performed.
If uv fails, correct its network/cache configuration and replay the same recipe into a new path.
