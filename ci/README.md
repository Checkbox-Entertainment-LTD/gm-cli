# Automatic private CLI releases

## Operator workflow

Edit CLI code, increase **`ci/release-version.txt`**, commit and push. Code changes and the version bump may be in the same commit. You do not need to edit `package.json` / `package-lock.json` merely to change the release version: `release_cli.py stamp` synchronizes their version fields in the build checkout before compilation.

Every pushed commit containing this CI setup is queued for `GM_CLI` in Jenkins. Ordinary commits run tests, compile and lint, and retain no installable package. A version increase also packages and publishes a private immutable GitHub release named `cli/<version>` after validation. The format is `2.3.0-checkbox.2`; values must increase numerically relative to the first parent. Introducing the version file does not publish. A release version can belong to only one source commit.

The game does not select a CLI version. At build start the infrastructure resolves the highest complete, immutable, non-prerelease `cli/` version once. Both game workers use that selection. There is no timer and no manual worker installation. Older game commits use the newest CLI after migrating their launcher; commits containing the historical pinned launcher retain their historical behavior.

## Files

- `Jenkinsfile`: exact-commit checkout, validation, version-gated publication and successful-workspace cleanup.
- `.github/workflows/checkbox-push.yml`: push event -> one job-scoped Jenkins POST per new commit. Any branch containing this workflow works; no branch naming policy.
- `ci/commit_policy.py`: first-parent version comparison and Git-history push enumeration, including combined source+bump commits and multi-commit pushes.
- `ci/release_cli.py`: synchronize package metadata, create checksummed release metadata and publish/resume immutable assets.
- `ci/check_packaged_cli.py`: execute the packaged CLI twice and verify that its installed file inventory stays unchanged. This runs after compilation and before publication. Python helpers run with bytecode writes disabled so they cannot add cache files to the verified package.
- `ci/cli_distribution.py`: independent Python bootstrap, highest successful release selection, private downloads, safe extraction, file verification, automatic Node installation and locks/atomic cache installation. Its game-side copy is the stable launcher dependency; keep both copies synchronized when changing the bootstrap itself.
- `.node-version`: required Node for this CLI. CI provisions it automatically from official archives; release metadata records the official archive checksums for the game workers.

## Release contents

`cli-release.json` records source commit, version, exact package hash and file inventory, and required Node archives/checksums. The other asset is the packaged CLI `.tgz`. Publication seals a draft only after the complete asset inventory matches. The source tag is immutable. A failed draft never becomes selectable.

## Worker caches and credentials

CLI: `~/.local/lib/checkbox-gm-cli/<package SHA>/artifact.tgz` and `package/`.
Node: `~/.local/lib/checkbox-gm-cli/node/<archive SHA>/node-v<version>-<host>/`.

The launcher installs these automatically. Verified cached files are reused; altered files fail visibly. Each installation is locked and staged before rename. Running builds retain their selected package directory. No scheduled updater runs.

Jenkins binds its existing GitHub App credential for private downloads/publication. GitHub Actions has only `JENKINS_CI_URL` and `JENKINS_BUILD_TOKEN` (a job-specific trigger token), not an administrator API token. `Contents: write` and immutable releases must be enabled for publication. Node prerequisites download over HTTPS and match the checksums recorded in the release.

## Failure/recovery

- Inspect the `GM_CLI` console and `runs/<build>/selection.json`. Failed workspaces remain available; successful ones are deleted. Jenkins retains 40 build records.
- Retry by building the same full `SOURCE_COMMIT`. Successful commits deduplicate; failed commits retry. A release tag collision with another commit fails rather than overwrites.
- Candidates are preserved at `~/.local/share/checkbox-ci/cli-candidates/<source SHA>/` before publication. Retry reuses that candidate, checks already uploaded assets and seals the original draft. Never overwrite a published package.
- Game builds archive `artifacts/cli-selection.json`: exact selected source/package/Node metadata. Changing the current release during a build does not alter that selection.
- Offline discovery fails clearly. A cached package is usable after a successful selection, but the launcher never silently claims to have checked for updates while offline.
- Exceptional rollback/replay: set infrastructure environment `GM_CLI_RECOVERY_VERSION` to an exact existing released version before `ci/gm_cli.py --resolve-cli`. Remove the override to resume automatic selection; no game version file is required. Retry an already selected build with its archived selection instead of resolving again.
- To change the same CLI again, increment the version file and push. New releases should remain backward compatible with supported workflows; a regression is a bug.

## Runtime identity

Custom-runtime game builds run `native/runtime_identity.py` after release verification. It copies the game sources into the invocation directory and prepends a global `GM_runtime_version` macro to a registered script. The official asset compiler supplies this constant from its own assembly version, so modifying only runner banner defines would not update it. The original project is untouched, stock builds bypass the override, and conflicting project overrides fail. The selected custom libraries are still independently verified; a string alone is not evidence of library consumption.

Local IDE hooks/custom-runtime caching and new platforms are deferred. This CLI package cache is only the infrastructure needed for automatic CLI installation.
