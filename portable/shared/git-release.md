# Git Release

Use this prompt with an assistant that has terminal access. The goal is to
prepare and cut a release from the repository default branch, with explicit
validation gates and no hidden history rewriting.

## Mission

When the user asks for a release, verify the repository is ready, resolve the
default branch, ensure there are no open PRs targeting it, refresh that branch,
run release validation, update `CHANGELOG.md`, create a release commit, and then
publish the tag with `gix release`.

## Optional Subagent Routing

If the platform supports subagents with explicit model selection, use this
routing:

- `release-preflight`: `worker`, `gpt-5.3-codex-spark`, `low`, `fork-safe`.
  Resolve the default branch, inspect open PRs, confirm worktree cleanliness,
  identify the release validation command, and find the latest version tag.
  Re-verify blocking facts in the live worktree before continuing.
- `release-versioning`: `worker`, `gpt-5.4-mini`, `medium`, `fork-safe`.
  Choose the next semver version from validated facts and provide the bump
  rationale.
- `release-execution`: `worker`, `gpt-5.3-codex-spark`, `medium`,
  `same-worktree`. Update `CHANGELOG.md`, commit, push, and run `gix release`.
  If the platform cannot guarantee same-worktree execution, keep this step in
  the main thread.

If the platform lacks subagents or explicit model controls, run the whole
workflow inline.

## Preconditions

- Require `gh`, `git`, `gix`, and the repository's standard build tooling.
- Work from the repository root.
- Stop immediately if the worktree is dirty, if there are open PRs into the
  default branch, if tests fail, or if pushing fails.
- Never release from a non-default branch.

## Workflow

1. Resolve the default branch:

   ```bash
   gh repo view --json defaultBranchRef --jq .defaultBranchRef.name
   ```

   Fallback only if needed:

   ```bash
   git remote show origin | sed -n '/HEAD branch/s/.*: //p' | head -n 1
   ```

2. Ensure there are no open PRs targeting the default branch:

   ```bash
   gh pr list --base "$default_branch" --state open --json number,title,headRefName,url
   ```

   If any PRs are open, report them and stop.

3. Ensure the local worktree is clean:

   ```bash
   git status --short
   ```

   If any tracked or untracked changes are present, report them and stop.

4. Refresh the default branch locally:

   ```bash
   gix cd "$default_branch"
   ```

   This is the required branch switch and update step. Do not release from any
   other branch.

5. Run the repository's release validation:
   - prefer `make ci`
   - if the repo clearly uses a different canonical full-suite command, use that
     instead
   - if validation fails, report the failure and stop

6. Find the latest version tag:

   ```bash
   git tag -l 'v*' --sort=-version:refname | head -n 1
   ```

   If no version tags exist, treat the current version as `v0.0.0` and handle
   the release as the first tagged release.

7. Choose the next semver version.

8. Generate the release changelog message:

   If `latest_tag` exists:

   ```bash
   gix message changelog --since-tag "$latest_tag" --version "$next_version" --release-date "$(date +%F)"
   ```

   Otherwise:

   ```bash
   gix message changelog --version "$next_version" --release-date "$(date +%F)"
   ```

9. Update `CHANGELOG.md` by inserting the new release section near the top of
   the released versions section. If `CHANGELOG.md` does not exist, report that
   and stop.

10. Commit and push only the changelog update on the default branch:

   ```bash
   git add CHANGELOG.md
   git commit -m "Release $next_version"
   git push origin "$default_branch"
   ```

   If push fails, report the failure and stop.

11. After the changelog commit is on the remote default branch, create and push
    the release tag:

   ```bash
   gix release "$next_version"
   ```

## Versioning

- Choose a patch bump for fixes, maintenance, documentation-only user-visible
  notes, dependency refreshes, and other backward-compatible corrections.
- Choose a minor bump for backward-compatible features, new workflows, or
  meaningful capability expansion.
- Choose a major bump only for breaking changes, incompatible contract changes,
  or removals that require user action.
- When the correct bump is ambiguous, prefer the smaller safe bump and explain
  the reasoning.

## Changelog Update

- Preserve the existing `CHANGELOG.md` structure.
- Insert the generated release notes as a new version section above the current
  latest released version section.
- Do not silently delete existing `Unreleased` content. If the changelog format
  is unusual, adapt carefully and keep the file coherent.
- The changelog entry should use the chosen version and the current release date.

## Reporting

Report:

- resolved default branch
- latest existing tag
- chosen next tag and bump rationale
- validation command run and whether it passed
- whether `CHANGELOG.md` was updated
- release commit hash
- whether `gix release` completed

If the process stops early, report the exact blocking step and the command
outcome that caused the stop.

## Guardrails

- Never continue after open PRs into the default branch are found.
- Never continue after failing validation.
- Never create a release from a non-default branch.
- Never skip updating `CHANGELOG.md`.
- Never tag before the changelog commit is pushed successfully.
