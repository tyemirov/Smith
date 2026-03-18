---
name: "GitCommit"
description: "Turn the current Git worktree into a commit. Use when Codex should inspect the full set of introduced changes relative to the previous commit, draft a commit message with `gix message commit`, commit all tracked and untracked changes, and push when the repository has a clear remote target. Trigger for requests like \"commit this\", \"write a commit message and commit everything\", or \"commit and push the current changes.\""
---

# GitCommit Skill

Use `$GitCommit` when the user wants a diff-based commit message, a full-tree commit, and an optional push.

## Preconditions

- Require `git` and `gix`.
- Work inside a Git repository.
- Respect repo-local instructions before committing or pushing. If `AGENTS.md`, `POLICY.md`, or similar docs require validation, ensure the required checks have passed or stop and report the missing gate.
- Never amend, rebase, force-push, or guess a remote when the target is ambiguous unless the user explicitly asks.

## Workflow

1. Inspect the repository state before mutating anything:

   ```bash
   git rev-parse --show-toplevel
   git status --short --branch
   git branch --show-current
   git remote
   git rev-parse --abbrev-ref --symbolic-full-name @{upstream}
   git rev-parse -q --verify HEAD
   git diff --name-only --diff-filter=U
   ```

2. Detect in-progress Git operations before staging or committing. Check for active merge, rebase, cherry-pick, or revert state via `MERGE_HEAD`, `rebase-merge`, `rebase-apply`, `CHERRY_PICK_HEAD`, and `REVERT_HEAD`. Stop and tell the user to finish or abort that operation first.

3. Stop early when commit or push would be unsafe or pointless:
   - not a Git repository
   - clean worktree
   - detached `HEAD`
   - unmerged files
   - required repo validation missing or failing

4. Stage the complete change set:

   ```bash
   git add -A
   ```

   Use staged diff generation instead of worktree diff generation so new files, deletions, and renames are included in the commit message.

5. Draft the commit message from the staged diff:

   ```bash
   commit_message_file="$(mktemp)"
   trap 'rm -f "$commit_message_file"' EXIT
   gix message commit --diff-source staged > "$commit_message_file"
   ```

   If the command fails, stop and report the exact error. Explain that all current changes remain staged and give the next action:
   - fix `gix` or LLM credentials/configuration
   - provide a manual commit message
   - unstage with `git reset` only if the user explicitly wants to undo the staging step

6. Commit the staged tree with the generated message:

   ```bash
   git commit -F "$commit_message_file"
   ```

   If `git commit` fails, report the exact failure and do not attempt a push. Common causes include hooks, missing author identity, or an empty staged diff after files changed during the workflow.

7. Decide whether to push:
   - no remotes: skip push and report that the commit is local only
   - upstream configured: run `git push`
   - no upstream and exactly one remote: run `git push -u <remote> HEAD`
   - no upstream and multiple remotes: honor repo-local policy if it clearly names the push remote; otherwise stop after the local commit and tell the user which remotes exist and how to continue

8. If push fails, report the failure clearly. Do not rewrite history, retry with force, or hide the fact that the commit exists locally.

## Initial Commit

If the repository has no `HEAD` yet, treat the staged tree as the full initial commit. Still use `git add -A` before `gix message commit --diff-source staged`. If `gix` cannot produce a message for the initial commit, stop and explain that the working tree is staged but no commit was created.

## Reporting

Always report:

- repository root
- current branch
- whether the worktree was clean or changed
- the generated commit subject
- the new commit hash if a commit was created
- whether a push happened, and to which remote and branch
- if the flow stopped, the exact blocking step and the next action

Use direct, actionable outcomes such as:

- `Committed abc1234 on feature/x with message "fix(api): handle empty token". Pushed to origin/feature/x.`
- `Committed abc1234 on feature/x, but did not push. No Git remotes are configured, so the commit is local only.`
- `Committed abc1234 locally, but did not push. Branch feature/x has no upstream and multiple remotes exist: origin, upstream. Tell me which remote to use or run git push -u <remote> HEAD.`
- `Stopped before commit. gix message commit --diff-source staged failed after staging all changes. Fix the gix configuration or give me a manual commit message; the index still contains the full staged change set.`
- `Nothing to commit. The worktree is clean on feature/x.`

## Guardrails

- Do not silently drop untracked files; `git add -A` is required.
- Do not push to a guessed remote when multiple candidates exist and no policy resolves the choice.
- Do not continue after commit-message generation, commit, or push failures.
- Do not hide partial success. If the commit succeeded but push failed, say so explicitly.
