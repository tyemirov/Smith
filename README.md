# Smith

Custom agent skills. Simp uses one portable workflow across Codex, Claude Code,
Gemini CLI, and Antigravity.

## Codex Plugin Marketplace

This repository is a Codex plugin marketplace. GitHub discoverability comes
from the checked-in marketplace and plugin package layout:

- `./.agents/plugins/marketplace.json`
- `./plugins/tyemirov`

After this repository is published, install the marketplace from GitHub:

```bash
codex plugin marketplace add tyemirov/Smith --ref master
codex plugin add tyemirov@agent-skills
```

The installed skills appear under the `tyemirov` plugin namespace:

- `tyemirov:Email Cleanup`
- `tyemirov:Git Commit`
- `tyemirov:Git Release`
- `tyemirov:simp`
- `tyemirov:Tidy Folder`

## Local Development

Regenerate the checked-in plugin bundle from the source skill directories:

```bash
./sync-plugins.sh
```

By default, this only updates repository files under `./plugins/` and
`./.agents/plugins/marketplace.json`. It does not register or install anything
in the local Codex configuration.

Use `./sync-plugins.sh --help` for options such as `--plugin-parent`,
`--marketplace-path`, `--marketplace-name`, and `--dry-run`.

For local smoke testing only, register this checkout as a local marketplace and
install the plugin:

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
| Email Cleanup | `tyemirov:Email Cleanup` | `/email-cleanup` |
| Git Commit | `tyemirov:Git Commit` | `/git-commit` |
| Git Release | `tyemirov:Git Release` | `/git-release` |
| Simp | `tyemirov:simp` | `/simp` |
| Tidy Folder | `tyemirov:Tidy Folder` | `/tidy-folder` |

### Simp across hosts

Simp's complete directory can be linked into each host without changing its
workflow:

| Host | Invocation | Personal/global discovery path |
|---|---|---|
| Codex | `$simp audit repo` | `~/.agents/skills/simp/` |
| Claude Code | `/simp audit repo` | `~/.claude/skills/simp/` |
| Gemini CLI | `Use the simp skill to audit this repository.` | `~/.agents/skills/simp/` |
| Antigravity | `Use the simp skill to audit this repository.` | `~/.gemini/config/skills/simp/` |

See [`simp/README.md`](simp/README.md) for project-scoped locations and apply
mode examples.

## Skill format

Each skill is a self-contained directory with a `SKILL.md` file containing YAML
frontmatter (`name`, `description`) and the full workflow prompt. Simp keeps
these standard fields as its complete shared frontmatter so Codex, Claude Code,
Gemini CLI, and Antigravity consume the same workflow.

Optional metadata files:

- `agents/openai.yaml`: UI metadata, invocation policy, and default prompts for
  Codex.
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
