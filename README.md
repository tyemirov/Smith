# Smith

Custom skills for Codex and Claude Code.

## Installation

```bash
./install-skills.sh
```

This installs skills into both platforms from a single source:

- **Codex**: symlinks each skill directory into `~/.codex/skills/`
- **Claude Code**: symlinks each `SKILL.md` into `~/.claude/commands/` as a
  slash command (e.g., `/git-release`)

Use `./install-skills.sh --help` for options such as `--codex-home`,
`--claude-home`, `--dry-run`, and `--force`.

## Skills

| Skill | Codex | Claude Code |
|---|---|---|
| Email Cleanup | `$Email Cleanup` | `/email-cleanup` |
| Git Commit | `$Git Commit` | `/git-commit` |
| Git Release | `$Git Release` | `/git-release` |
| Tidy Folder | `$Tidy Folder` | `/tidy-folder` |

## Skill format

Each skill is a self-contained directory with a `SKILL.md` file containing YAML
frontmatter (`name`, `description`) and the full workflow prompt. This single
file serves both Codex (via the directory symlink) and Claude Code (via the
file symlink).

Optional metadata files:

- `agents/openai.yaml`: UI metadata for Codex skill lists and default prompts.
- `agents/runtime.yaml`: subagent routing when a host supports explicit `model`
  and `reasoning_effort` controls. Routing files distinguish `fork-safe` steps
  from `same-worktree` steps so Git mutations stay in the live repository.

## Python helpers

Python helper scripts must be executable and use a `uv` script shebang:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
```

Declare script dependencies inline in the `dependencies` list. Skill workflows
should invoke helpers directly, for example `./scripts/helper.py`, rather than
through `python3`, `pip`, `pipx`, or a global virtual environment.
`uv` should be available on `PATH`; scripts that need to re-exec through `uv`
may also honor a `UV` environment variable.
