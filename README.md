# Smith

Custom skills for Codex and Claude Code.

## Codex Plugin Marketplace

This repository is a Codex plugin marketplace. GitHub discoverability comes
from the checked-in marketplace and plugin package layout:

- `./.agents/plugins/marketplace.json`
- `./plugins/email-cleanup`
- `./plugins/git-commit`
- `./plugins/git-release`
- `./plugins/tidy-folder`

After this repository is published, install the marketplace from GitHub:

```bash
codex plugin marketplace add tyemirov/Smith --ref master
codex plugin add email-cleanup@agent-skills
codex plugin add git-commit@agent-skills
codex plugin add git-release@agent-skills
codex plugin add tidy-folder@agent-skills
```

## Local Development

Regenerate the checked-in plugin packages from the source skill directories:

```bash
./sync-plugins.sh
```

By default, this only updates repository files under `./plugins/` and
`./.agents/plugins/marketplace.json`. It does not register or install anything
in the local Codex configuration.

Use `./sync-plugins.sh --help` for options such as `--plugin-parent`,
`--marketplace-path`, `--marketplace-name`, and `--dry-run`.

For local smoke testing only, register this checkout as a local marketplace and
install the plugins:

```bash
./sync-plugins.sh --install-local
```

To remove legacy direct Codex skill symlinks that point back to this repository
during local cleanup:

```bash
./sync-plugins.sh --remove-direct-skills
```

### Legacy Direct Skill Symlinks

```bash
./install-skills.sh
```

This legacy installer links skills directly into Codex and Claude Code from a
single source:

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
