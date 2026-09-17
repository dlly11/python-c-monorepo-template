# Versioning and releases

Each product has its own [Semantic Versioning](https://semver.org/) number, tag, and changelog.
Release Please combines pending component updates into one PR, titled `chore: release main`, on
`release-please--branches--main`. Merging it creates one GitHub Release per changed component.

| Release unit | Version source | Tag example |
| --- | --- | --- |
| Python core, package A, package B, CLI | Each component's `pyproject.toml` | `python-core-v2.0.5` |
| Native core, package A, package B, CLI | Each component's `version.txt` | `native-core-v2.0.5` |

<!-- BEGIN TEMPLATE CREATOR ONLY -->
The upstream template and repository creator remain one release unit, `template`, using root
`version.txt` and `vX.Y.Z` tags. Only its root Python/CMake metadata and creator version follow
that number. Generated repositories omit this release unit, root version/changelog, and root
`[project]`; they retain the shared uv workspace and development configuration.

The root Release Please entry must keep both `component` and `package-name` empty. This lets
Release Please publish a template-only PR from the shared release branch with an unprefixed tag.
Repository commands and commit scopes still call this release unit `template`.

The migration preserves the existing `v2.0.4` release. Product baselines begin at `2.0.4`, with
bootstrap history starting at its release commit. Existing tags are never rewritten.
<!-- END TEMPLATE CREATOR ONLY -->

The private `monorepo-repo-tools` package is outside workspace membership, independently versioned,
and excluded from release assets.

## Release recovery

Start with the failed stage. Its workflow logs explain the cause; the table selects the retry
that preserves successful work. Release creation and PR preparation also write job summaries
with the available release or PR link. A created release does not mean all asset uploads finished.

| What failed? | What to do |
| --- | --- |
| Checks on an open release PR | Follow [release PR approval and retry guidance](github-setup.md#approving-and-retrying-release-pr-checks); retry authoritative validation before its delegating check. |
| **Create GitHub release**, before a release exists | Fix the reported cause and follow the [manual release retry](#automated-release-sequence). If CI evidence expired, use the recovery row below. |
| **Prepare release PR** | Fix the reported cause and retry that failed job. Successful asset jobs need no retry; see [release job recovery](#recovering-missing-release-assets). |
| Merged release PR remains `autorelease: pending` | Follow [unpublished release recovery](#recovering-an-unpublished-merged-release). Release Please cannot prepare the next PR until publication succeeds. |
| Merged PR evidence expired or is missing | Run fresh full CI on current main and explicitly select it using [evidence recovery](#recovering-expired-ci-evidence). |
| A release exists but assets are missing | Retry the original failed asset job; use [asset recovery](#recovering-missing-release-assets) if the original run is unavailable. A new Release dispatch does not restore assets. |

## Recovering an unpublished merged release

Release Please can return success without creating a release or PR when a merged release PR
is still unpublished. The **Prepare release PR** job checks for this condition and fails with
links to the blocking PRs. Inspect the **Create GitHub release** logs, correct the publication
cause, and run Release on current `main` after the correction is merged. Keep the pending
label and release PR body intact; removing them bypasses publication instead of repairing it.

## Sources of version metadata

`tools/release-please/config.json` declares component paths, IDs, strategies, and owned metadata.
`tools/release-please/manifest.json` records their released versions. Each component owns its
`CHANGELOG.md`. The upstream template entry excludes independent product directories so a
product-only change does not trigger creator builds. Python versions are also resolved into the shared `uv.lock` by `uv lock`.
Native CMake targets and generated version headers read their own component's `version.txt`.

```bash
uv run repo-tools check-versions
uv run repo-tools check-versions --component python-core --tag python-core-v2.0.4
# Exceptional manual change; normal releases use Release Please:
uv run repo-tools set-version python-core 2.0.5
```

The setter updates only the selected component's declarations and manifest entry, refreshing
`uv.lock` when Python metadata changes. It validates before writing and restores original bytes
after failure or Ctrl+C. It does not create changelogs, tags, or GitHub Releases.

Dependency requirements express compatibility, independently of release numbers. Raise a Python
lower bound when a consumer starts using a newer dependency API; do not synchronize all bounds
automatically. A shared uv environment still requires compatible dependencies across members;
independent versions do not isolate environments. See [dependencies](dependencies.md).

Native package configs require dependencies at least as new as those used to build the archive,
within the same major version. Each archive records its build-time component versions under
`share/<component>/component-versions.txt`. See [native consumption](architecture.md#consuming-a-native-installation).

### Which components release?

Release Please attributes commits by **changed paths**, not Conventional Commit scopes. A commit
changing two component directories can release both, even with only one scope or no scope.
Shared root changes do not automatically release all products, and dependency releases do not
automatically release their consumers.

For a shared build change or a dependency fix that requires an app rebuild, include a meaningful
source/build change or release note in each affected component directory in a `fix:`/`feat:`
commit. For example, a native CLI statically embeds package A and core; releasing core alone
leaves the published CLI unchanged. Record the rebuild in the CLI's README and use a `fix:`
commit touching that file to release the rebuilt CLI. Do not create empty version-only commits.
A breaking marker affects every component touched by that commit; split unrelated changes when
they need different version effects.

## Conventional Commits

Release Please derives the next version and changelog from commits on `main`. This template
validates both new commit subjects and pull request titles. GitHub's squash and merge commit
defaults use the validated PR title as the resulting commit subject on `main`. Rebase merges
preserve the individual commit messages instead; the PR title is still checked for review clarity.

| Conventional subject | Version effect |
| --- | --- |
| `fix(python-core): handle an empty name` | Patch (`1.2.3` to `1.2.4`) |
| `feat(python-package-a): add JSON output` | Minor (`1.2.3` to `1.3.0`) |
| `feat(python-core)!: replace the result API` | Major (`1.2.3` to `2.0.0`) |
| `docs: explain local builds` | Included in history but does not initiate a release |

Use the [contribution guide](CONTRIBUTING.md#commit-messages-and-pull-requests) for subject syntax,
hook setup, and repair commands. CI event behavior and checked commit ranges are documented once
in [testing](testing.md#pr-and-post-merge-responsibilities). Bootstrap pushes skip inherited subjects.

Squashing produces one commit per PR. Creating a merge commit preserves the individual commits
as well, so their release signals and changelog entries can contribute to the release. For example,
a preserved `feat:` commit can request a minor release even if the PR title starts with `fix:`.
Rebase merging also preserves individual messages, with new SHAs and no additional merge commit.
A PR title alone cannot request a version bump or add a breaking-change marker to rebased commits.
Review the generated release PR before merging it. Release readiness and evidence recovery support
all three methods, including a rebased release branch with a separate lockfile-update commit.

For breaking changes, put `!` in the PR title and in the relevant individual commit when preserving
commits. Explain migration in a `BREAKING CHANGE:` footer in the final commit body. Squash bodies
default to the commit messages; merge commit bodies default to the PR description. With a rebase,
put release footers in the relevant individual commit: the PR description is not copied. Bodies and
footers are not linted. For a manual title check, select the open PR's current head branch and number:

```bash
gh workflow run pr-title.yml --ref YOUR_PR_BRANCH -f pr-number=123
```

## Automated release sequence

The files `tools/release-please/config.json` and `tools/release-please/manifest.json` are Release
Please policy and state. Change their structure only as part of an intentional release-policy
migration.

The release workflow runs after successful **post-merge verification on the current `main` commit**:

1. The release gate verifies the triggering repository, CI workflow, event, branch, and commit,
   then checks the latest push CI run for that commit. Its `Merged PR verification` job must pass:
   merged files must match the tested PR's recorded tree, every job in the validated CI profile must have
   succeeded, and final subjects/version metadata must be valid. The full quality suite is not
   repeated after merging. **Create GitHub release** validates the selected credentials and asks
   Release Please to create releases for merged release PRs, without opening new PRs.
   **Prepare release PR** then rechecks readiness and opens or updates the next release PR.
2. The pull request updates version declarations and changelogs for changed components and their
   manifest entries. Unchanged components keep their versions.
3. The workflow checks out the managed branch, regenerates `uv.lock`, and commits it when changed.
   In every credential mode it dispatches `ci.yml` with the PR number and exact resulting head,
   plus `pr-title.yml`. Automatic PR CI delegates to that run. Metadata-only releases use the
   [release validation profile](testing.md#release-only-validation); other changes use full CI.
4. A maintainer merges the release pull request, or optional auto-merge completes it after all
   required checks and reviews pass. Auto-merge supports every release version, including majors.
5. After the release PR is merged and post-merge verification succeeds, Release Please creates
   each component tag and GitHub Release.
6. The existing Python job and native OS jobs build from each release's immutable commit, once
   per commit/platform, smoke-test their outputs, and upload only the released component's assets.
   Python components receive their wheel and source distribution. Native components receive
   `<component>-vX.Y.Z-<OS>-<ARCH>.zip`. No unchanged sibling is uploaded or republished.
   Unit tests, coverage, linting, and sanitizers remain on PRs.

Asset jobs depend only on successful release creation. They run independently of **Prepare
release PR**, so a failure to open the next PR, refresh its lockfile, dispatch checks, or enable
auto-merge does not block uploads for the release already created. Such a preparation failure
still marks the workflow as failed and needs attention. Release creation, PR preparation, and
artifact jobs have their own permissions; App tokens remain within the job that creates them.
For default-token PR approval and required-check behavior, see
[GitHub setup](github-setup.md#approving-and-retrying-release-pr-checks).

Automatic release runs for superseded commits skip without calling Release Please. The gate
rechecks `main` immediately before that call; automatic and manual runs share one concurrency
group. A passing PR check or ordinary manual CI run does not automatically substitute for push CI.
The explicit recovery procedure below can authorize a release from fresh manual main validation.

To retry release preparation manually, select `main`:

```bash
gh workflow run release.yml --ref main
```

Manual releases stop immediately if the selected commit is no longer current or its latest push
CI is missing, pending, cancelled, or failed. Wait for successful push CI, then retry; the release
workflow does not poll or start CI for you. If a push CI run needs retrying, rerun that original CI
run so its event remains `push`. These retries are for release preparation, not missing assets;
use the recovery procedure below once a release has already been created.

The repository intentionally does not publish the example package names to PyPI. Add a separate,
environment-protected publication job using trusted publishing after replacing the example names
and choosing an artifact registry.

## Recovering expired CI evidence

Choose the recovery path using the PR's state and evidence schema:

| Situation | Recovery |
| --- | --- |
| Open PR, current schema-2 CI | Retry PR CI; for a managed release PR, retry its authoritative dispatch, not the delegating run. Ensure **CI result** runs after the selected quality jobs and uploads evidence for the current attempt. |
| Merged PR, missing schema-2 evidence | Run fresh full CI on current main and explicitly select it with `recovery-run-id`, as shown below. Current PR validation requires an open PR, so rerunning the original PR workflow after merging cannot restore its evidence. |
| Historical schema-1 CI | If the original workflow remains retryable, rerun its Python quality job to restore its record, then retry push CI. Otherwise use fresh main validation below. |

Schema-2 evidence is written by **CI result** and bound to the run attempt. A partial retry must
rerun that gate after the selected checks succeed; an artifact from an earlier attempt cannot be
reused. Historical schema-1 workflows recorded evidence in Python quality and can reuse that record
across partial retries of the same run and immutable head, provided all required jobs pass.

GitHub permits reruns only within
[30 days of the initial execution](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).
Before merging a long-lived PR whose original run can no longer be retried, push a new Conventional
Commit to obtain fresh PR validation. A changed PR head or base needs validation of that new state.

The release gate checks out full Git history. Local merged-PR verification also requires a full
checkout: for a shallow clone, run `git fetch --unshallow` before checking the integration. A shallow
history can hide preserved commits or truncate a rebased sequence and is rejected before PR reads.

First dispatch the existing full CI suite on current main:

```bash
gh workflow run ci.yml --ref main
gh run list --workflow ci.yml --branch main --event workflow_dispatch --limit 5
CI_RUN_ID=123456789  # Replace with the new run ID from the list.
gh run watch "${CI_RUN_ID}" --exit-status
```

Only after it succeeds, explicitly select that evidence for Release:

```bash
gh workflow run release.yml --ref main -f "recovery-run-id=${CI_RUN_ID}"
```

The gate requires the latest manual CI run for the exact current main commit, the correct repository
and workflow, every required quality job completed successfully, and a matching validation record
including the checkout SHA and Git tree. It independently checks the final Conventional Commit
subject and merged-PR association, plus the second parent and preserved commit subjects for merge
commits. For a rebase it checks subjects across the contiguous rewritten PR sequence, and main must
be at the PR's final rewritten commit. Skipped jobs, expired/mismatched records, or pending/failed
runs reject recovery. Actual integrated commit subjects replace the separate PR title job.
The gate rechecks the CI run and main after reading evidence; if main advances, start again on the
new head. Initialization commits without a merged PR cannot use this procedure.

This explicit dispatch authorizes release preparation/creation. It does not repair an old push run
or recover missing release assets. Ordinary automatic releases continue to require successful push
verification. Leave `recovery-run-id` empty for the ordinary manual release retry.

## GitHub repository settings

See [repository settings](github-setup.md#repository-settings) for branch protection, merge
methods, required checks, and default release permissions.

### Optional unattended releases

See [unattended release setup](github-setup.md#optional-unattended-releases) for App/PAT
credentials, auto-merge activation, and disabling automation.

### Audit the managed GitHub settings

See the [settings audit](github-setup.md#audit-the-managed-github-settings) for policy comparison,
extended diagnostics, permissions, and exit codes.

## Recovering missing release assets

If only **Prepare release PR** fails, retry that job after fixing its cause; successful asset
jobs do not need rerunning. Preparation does not create tags or GitHub Releases.

If a build or upload fails after the GitHub Release is created, open the original **Release**
workflow run and choose **Re-run failed jobs**, or rerun the specific failed asset job. Retry from
that run so the successful release-creation job's outputs remain available. GitHub documents
[rerunning workflows and individual jobs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).

Do not use a fresh **Run workflow** dispatch or **Re-run all jobs** to recover an existing release:
Release Please no longer reports that release as newly created, and the asset jobs are conditional
on that output. Rerunning a successful upload uses `--clobber` to replace its existing asset.

If the original job can no longer be retried, rebuild from the exact release tag in a clean
worktree, using the matching platform and compiler. Authenticate GitHub CLI with release-write
access. For example, to recover a native core archive on Linux X64:

```bash
RELEASE_TAG=native-core-v2.0.5
COMPONENT=native-core
git fetch origin tag "${RELEASE_TAG}"
git worktree add --detach ../release-recovery "${RELEASE_TAG}"
cd ../release-recovery
python tools/repo_tools/run.py check-versions --component "${COMPONENT}" --tag "${RELEASE_TAG}"
export CC=gcc CXX=g++
cmake --preset release
cmake --build --preset release
cmake --install build/release --prefix stage --component "${COMPONENT}"
python tools/repo_tools/run.py check-native-install "$PWD/stage" --component "${COMPONENT}"
cmake -E make_directory dist
ARCHIVE="${RELEASE_TAG}-Linux-X64.zip"
cmake -E chdir stage cmake -E tar cf "../dist/${ARCHIVE}" --format=zip .
gh release upload "${RELEASE_TAG}" "dist/${ARCHIVE}" --clobber
```

Before uploading a library archive, install its dependency archives into a clean prefix and build
an external consumer as described in [architecture](architecture.md#consuming-a-native-installation).
Use macOS/Clang or Windows/MinGW for those platform artifacts; relabeling an archive is not
cross-compilation. For Python, run `uv build --all-packages --out-dir dist` and
`python tools/repo_tools/run.py check-python-install --dist dist`, then upload only the selected
component's wheel and source distribution to its release.

<!-- BEGIN TEMPLATE CREATOR ONLY -->
Historical lockstep tags retain their original layout. Current `check-versions --tag vX.Y.Z` and
`check-native-install` can read their metadata using `--project-root` before the command. Follow
the tagged release guide and tagged CMake consumer for rebuilding those aggregate archives;
do not apply current component archive instructions to an older tag. The read-only compatibility
path does not permit lockstep updates through the current setter.
<!-- END TEMPLATE CREATOR ONLY -->

Recovery attaches assets to the existing release; it does not require a new version, tag, or
release-creation run. Inspect the release's assets after the upload completes.

<!-- BEGIN TEMPLATE CREATOR ONLY -->
## Repository creator assets

The creator wheel/source distribution follows the template release version and is
included in Python assets. Six platform-specific executable archives and their `.sha256` files
are built from the release tag. Each executable is smoke-tested before upload. Release jobs reuse
the same build command as PR CI without repeating the full quality or generated-project suite.
Only a template release starts creator jobs; a product-only release does not.
The template release remains the main download. All Actions remain pinned by SHA. The downloads are unsigned (macOS uses ad-hoc signing only).
No signing account, certificate, or notarization secret is required.

The full CI profile includes all six **Repository creator (PLATFORM-ARCH)** jobs behind the
required **CI result** gate. Generated repositories exclude those jobs from the profile.

For a failed creator upload, rerun the failed asset job in the original release run. If that run
is no longer available, check out the exact release tag on the matching platform, install the
`creator-build` group, and run `python tools/creator/build.py --target PLATFORM-ARCH` through uv.
It rebuilds and smoke-tests the archive and checksum under `dist/creator`. Upload that matching
pair to the existing release with `gh release upload TAG ARCHIVE CHECKSUM --clobber` after both
pass. Do not rebuild an old release's creator using a newer template snapshot.
<!-- END TEMPLATE CREATOR ONLY -->
