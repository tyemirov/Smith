---
name: "Git Release"
description: "Use when preparing and cutting a release on the repository default branch: verify there are no open PRs into the default branch, refresh it with gix, run release validation such as make ci, generate release notes with gix message changelog, choose the next semver tag, update CHANGELOG.md, commit the changelog, and publish the tag with gix release."
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
- Stop immediately if the worktree is dirty, if there are open PRs into the default branch, if tests fail, or if pushing fails.

## Autonomy

Execute the full workflow without pausing for user confirmation between steps.
The validation gates defined in this workflow are the only stopping points.
Do not ask "should I proceed?" or "should I continue?" at intermediate steps.
Report the final outcome when the workflow completes or a gate stops it.

## Workflow

1. Resolve the default branch:
   `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`
   Fallback only if needed:
   `git remote show origin | sed -n '/HEAD branch/s/.*: //p' | head -n 1`
2. Ensure there are no open PRs targeting the default branch:
   `gh pr list --base "$default_branch" --state open --json number,title,headRefName,url`
   If any PRs are open, report them and stop.
3. Ensure the local worktree is clean:
   `git status --short`
   If any tracked or untracked changes are present, report them and stop.
4. Refresh the default branch locally:
   `gix cd "$default_branch"`
   This is the required branch switch and update step. Do not release from any other branch.
5. Run the repository's release validation:
   Prefer `make ci`.
   If the repo clearly uses a different canonical full-suite command, use that instead.
   If validation fails, report the failure and stop.
6. Find the latest version tag:
   `git tag -l 'v*' --sort=-version:refname | head -n 1`
   If no version tags exist, this is the first tagged release. Use `v1.0.0` as the version without asking for confirmation.
7. Choose the next semver version. Skip this step if step 6 already determined `v1.0.0` for the initial release.
8. Generate the release changelog message:
   If `latest_tag` exists:
   `gix message changelog --since-tag "$latest_tag" --version "$next_version" --release-date "$(date +%F)"`
   Otherwise:
   `gix message changelog --version "$next_version" --release-date "$(date +%F)"`
9. Update `CHANGELOG.md` by inserting the new release section near the top of the released versions section.
   If `CHANGELOG.md` does not exist, create it with a standard header and the generated release section.
10. Commit and push only the changelog update on the default branch:
   `git add CHANGELOG.md`
   `git commit -m "Release $next_version"`
   `git push origin "$default_branch"`
   If push fails, report the failure and stop.
11. After the changelog commit is on the remote default branch, create and push the release tag:
   `gix release "$next_version"`

## Versioning

- Choose a patch bump for fixes, maintenance, documentation-only user-visible notes, dependency refreshes, and other backward-compatible corrections.
- Choose a minor bump for backward-compatible features, new workflows, or meaningful capability expansion.
- Choose a major bump only for breaking changes, incompatible contract changes, or removals that require user action.
- When the correct bump is ambiguous, prefer the smaller safe bump and explain the reasoning.

## Changelog Update

- Preserve the existing `CHANGELOG.md` structure.
- Insert the generated release notes as a new version section above the current latest released version section.
- Do not silently delete existing `Unreleased` content. If the changelog format is unusual, adapt carefully and keep the file coherent.
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

If the process stops early, report the exact blocking step and the command outcome that caused the stop.

## Guardrails

- Never continue after open PRs into the default branch are found.
- Never continue after failing validation.
- Never create a release from a non-default branch.
- Never skip updating `CHANGELOG.md`.
- Never tag before the changelog commit is pushed successfully.
