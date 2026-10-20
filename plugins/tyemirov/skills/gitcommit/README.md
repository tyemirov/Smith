# Git Commit

Git Commit turns the selected repository changes into a commit with a message based on the staged diff.
It can push the commit when the remote destination is clear.

## Problem

A commit can omit new files or describe changes that differ from the actual diff.
An incomplete repository check can also miss an unfinished merge or required validation.

## Method

1. Inspect the branch, changed files, remote destination, and active Git operations.
2. Complete the repository's required validation.
3. Stage the authorized changes, including new files.
4. Generate the commit message with `gix message commit --diff-source staged`.
5. Create the commit and push when the request and remote configuration permit it.
6. Report the commit identifier and push result separately.

The default workflow covers all current changes.
State any scope restrictions in the request.
A message-generation or commit failure stops the workflow and reports the failed step.

## Install and use

Use the [collection installation guide](https://github.com/tyemirov/Smith#local-installation).
Install `git` and `gix` before use.
Run this command from the collection root:

```bash
./install-skills --skill gitcommit
```

The installer includes [Agent Runtime](../agent-runtime/README.md) for the shared roles.
Open the target repository and select `tyemirov:Git Commit` in the Codex plugin.
For a direct skill installation, use `$Git Commit`.
In Claude Code, use `/git-commit`.

## Example

```text
Use Git Commit to validate and commit all current changes in this repository.
Generate the message from the staged diff and push to the configured upstream.
```

The result includes the branch, generated message, commit identifier, and remote push status.
A local commit remains a separate result if the push fails.

Read [SKILL.md](SKILL.md) for the complete workflow and failure handling.
