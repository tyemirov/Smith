---
name: "Git Release"
description: "Use when preparing and cutting a release on the repository default branch: verify there are no open PRs into the default branch, refresh it with gix, run release validation such as make ci, generate release notes, choose the next release tag using SemVer or CalVer, update CHANGELOG.md, commit and push the changelog, publish the tag, create or update the GitHub Release object, and verify any GitHub Pages or release deployment surfaces."
---

# Git Release Skill

Use `$Git Release` when the user wants Codex to prepare and cut a release from the repository default branch.

## Runtime Routing

If the host supports subagents with explicit `model` and `reasoning_effort`, read `agents/runtime.yaml` before running this skill.

- Keep the controller in the main thread responsible for user communication, live-worktree verification, and final reporting.
- Delegate only steps whose `workspace` requirement the host can satisfy.
- In hosts where subagents run in forked workspaces, only delegate `fork-safe` planning or inspection steps. Run `same-worktree` steps such as changelog edits, commits, pushes, and tagging inline in the controller.
- If subagents or model controls are unavailable, run the full workflow inline and preserve the same guardrails.

## Preconditions

- `gh`, `git`, `gix`, and the repository's standard build tooling must be installed.
- Work from the repository root.
- Stop immediately if the worktree is dirty, if there are open PRs into the default branch, if tests fail, if pushing fails, if the GitHub Release object cannot be created or verified, or if a configured release deployment such as GitHub Pages fails.

## Bundled Helper

Use `scripts/release_helper.py` for deterministic gates and file edits. Resolve the path relative to this skill directory.

- `preflight` checks tool availability, resolves the default branch, checks open PRs, checks worktree cleanliness, detects SemVer and CalVer tags, generates a CalVer candidate, and reports validation command candidates as JSON.
- `insert-changelog` inserts the generated release notes into `CHANGELOG.md` without duplicating an existing release heading.
- `publish-release` creates or updates the GitHub Release object from the exact generated release notes.
- `verify-release` verifies the local and remote tag, GitHub Release object, release notes body, relevant Actions runs, GitHub Pages configuration, Pages reachability, optional Pages text expectations, and final worktree status.

The helper does not decide whether a repo should use SemVer or CalVer, choose a SemVer bump, decide a nonstandard validation command, or infer custom website freshness unless explicit expected text is provided. Make those decisions from repository context, then pass the result into the helper. If the helper exits nonzero, stop and report its JSON output.

## Autonomy

Execute the full workflow without pausing for user confirmation between steps.
The validation gates defined in this workflow are the only stopping points.
Do not ask "should I proceed?" or "should I continue?" at intermediate steps.
Report the final outcome when the workflow completes or a gate stops it.

## Workflow

1. Run the deterministic preflight helper from the repository root:
   `release_timestamp="$(date +%Y-%m-%dT%H:%M:%S)"`
   `release_date="${release_timestamp%%T*}"`
   `python3 /path/to/gitrelease/scripts/release_helper.py preflight --release-timestamp "$release_timestamp"`
   Use its JSON output to set `default_branch`. If it exits nonzero, report the blocking facts and stop.
2. Refresh the default branch locally:
   `gix cd "$default_branch"`
   This is the required branch switch and update step. Do not release from any other branch.
3. Re-run preflight after the refresh:
   `python3 /path/to/gitrelease/scripts/release_helper.py preflight --default-branch "$default_branch" --release-timestamp "$release_timestamp"`
   Use this JSON output for `version_info`, `latest_tag`, and validation candidates. If it exits nonzero, report the blocking facts and stop.
4. Run the repository's release validation:
   Prefer `make ci`.
   If the repo clearly uses a different canonical full-suite command, use that instead.
   If validation fails, report the failure and stop.
5. Choose the versioning scheme, changelog boundary tag, and next release version from the refreshed `version_info`.
   - If using CalVer, use the helper's `version_info.next_calver` candidate by default only when `version_info.calver_candidate.ok` is true.
   - If using SemVer and no SemVer tags exist, this is the first SemVer release; use `v1.0.0` without asking for confirmation.
   - If using SemVer and SemVer tags exist, choose the next SemVer bump from repository changes.
   - Set `latest_tag_for_changelog` to the latest released tag that should bound release notes. Usually this is the latest tag for the chosen scheme. When intentionally transitioning schemes, use `version_info.latest_any_version_tag` so old changes are not repeated.
   - If using CalVer and `version_info.calver_candidate.ok` is false, stop and report the timestamp/order problem rather than inventing a non-timestamp version.
6. Generate the release changelog message and keep the exact generated Markdown available for the GitHub Release object:
   `release_notes_file="$(mktemp)"`
   If `latest_tag_for_changelog` exists:
   `gix message changelog --since-tag "$latest_tag_for_changelog" --version "$next_version" --release-date "$release_date" | tee "$release_notes_file"`
   Otherwise:
   `gix message changelog --version "$next_version" --release-date "$release_date" | tee "$release_notes_file"`
7. Update `CHANGELOG.md` with the deterministic helper:
   `python3 /path/to/gitrelease/scripts/release_helper.py insert-changelog --notes-file "$release_notes_file"`
   The helper creates `CHANGELOG.md` if needed and inserts the generated section near the top of the released versions section.
8. Commit and push only the changelog update on the default branch:
   `git add CHANGELOG.md`
   `git commit -m "Release $next_version"`
   `release_commit="$(git rev-parse HEAD)"`
   `git push origin "$default_branch"`
   If push fails, report the failure and stop.
9. After the changelog commit is on the remote default branch, create and push the release tag:
   `gix release "$next_version"`
10. Create or update the GitHub Release object with the helper. Do not assume a pushed tag is enough:
   `python3 /path/to/gitrelease/scripts/release_helper.py publish-release --version "$next_version" --notes-file "$release_notes_file"`
11. Run deterministic remote verification:
   `python3 /path/to/gitrelease/scripts/release_helper.py verify-release --version "$next_version" --release-commit "$release_commit" --notes-file "$release_notes_file"`
   Add `--watch-run "$run_id"` for any release, package, documentation, or deployment workflow that the helper output shows should be watched to completion.
   Add `--expect-pages-text "$next_version"` or `--expect-pages-text "$release_commit"` when the GitHub Pages site exposes version, changelog, or build metadata at its root URL.
   If the helper exits nonzero, report the exact mismatch and stop. If it exits zero but shows repo-specific release/deployment runs that still need human judgment, inspect those runs and stop on any required release/deploy failure.
12. Refresh tags after remote verification:
   `git fetch --tags origin`

## Versioning

Release tags may use SemVer or CalVer.

- CalVer means calendar versioning. The default CalVer tag format is timestamp-derived: `YYYY.M.D.H[.m[.s]]`. For example, a release at 17:00 on April 23, 2026 is `2026.4.23.17`; a release at 17:05 is `2026.4.23.17.5`.
- CalVer must match the release timestamp and increase with time. Do not use an arbitrary same-day sequence counter.
- The helper starts with hour precision, then uses minute or second precision only when needed to avoid colliding with an existing timestamp tag. If the timestamp is not later than the latest CalVer tag, stop and report the clock/order issue.
- Prefer CalVer for applications, sites, internal tools, skills, documentation projects, and repositories where release identity matters more than compatibility signaling.
- Prefer SemVer for libraries, CLIs, packages, APIs, plugins, or other artifacts consumed by downstream users who reasonably expect SemVer compatibility guarantees.
- If the repository has an explicit versioning policy, follow it.
- If existing tags consistently use one scheme, continue that scheme unless the user explicitly asked to change it.
- If tags are mixed, inspect packaging metadata, release notes, and the user request. Preserve SemVer for externally consumed packages; otherwise prefer CalVer and explain the transition.
- Choose a patch bump for fixes, maintenance, documentation-only user-visible notes, dependency refreshes, and other backward-compatible corrections.
- Choose a minor bump for backward-compatible features, new workflows, or meaningful capability expansion.
- Choose a major bump only for breaking changes, incompatible contract changes, or removals that require user action.
- When the SemVer bump is ambiguous, prefer the smaller safe bump and explain the reasoning.

## Changelog Update

- Preserve the existing `CHANGELOG.md` structure.
- Insert the generated release notes as a new version section above the current latest released version section.
- Do not silently delete existing `Unreleased` content. If the changelog format is unusual, adapt carefully and keep the file coherent.
- The changelog entry should use the chosen version and the current release date.

## Reporting

Report:

- resolved default branch
- versioning scheme and rationale
- latest existing tag for that scheme
- changelog boundary tag
- chosen next tag
- validation command run and whether it passed
- whether `CHANGELOG.md` was updated
- release commit hash
- whether `gix release` completed
- remote tag verification result
- GitHub Release object URL and verification result
- release/deployment workflow results
- GitHub Pages status and URL when configured
- final worktree cleanliness

If the process stops early, report the exact blocking step and the command outcome that caused the stop.

## Guardrails

- Never continue after open PRs into the default branch are found.
- Never continue after failing validation.
- Never create a release from a non-default branch.
- Never skip updating `CHANGELOG.md`.
- Never tag before the changelog commit is pushed successfully.
- Never treat a pushed tag as equivalent to a published GitHub Release object.
- Never finish a release without re-reading GitHub's remote state for the tag and release object.
- Never ignore a configured GitHub Pages site or release deployment surface.
- Never imply SemVer compatibility guarantees for a CalVer release.
- Never increment a CalVer suffix independently of the release timestamp.
