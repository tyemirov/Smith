# Smith

Custom agent skills. Simp uses one portable workflow across Codex, Claude Code,
OpenCode, Gemini CLI, and Antigravity.

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
- `tyemirov:whip`
- `tyemirov:agent-runtime`

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

## Local installation

The public repository contains the installer and required runtime dependency.
Install Git, `uv`, and the agent CLI before installation.
Clone the public repository once:

```bash
git clone https://github.com/tyemirov/Smith.git agentSkills
cd agentSkills
```

Install all skills, shared roles, and bundled Codex reviewers with one command:

```bash
uv run --script install-skills
```

The command requires no private repository access.
Keep this checkout available because installed skills link to its files.
Run the same command again to install new skills.
Existing unrelated skills and controller model settings remain unchanged.
A conflicting skill or edited role file stops installation before profile changes.

Use `--target codex` to select Codex explicitly.
Use `--skill whip` to select Whip and its reviewer.
For workflows such as `gitcommit`, the installer adds `agent-runtime` automatically.
Use `--check` to verify installed files without changes.

The installer detects supported agent commands through `PATH`.
It reads each skill's YAML affinity declaration before installation.
It installs only skills that permit the detected agent.
Use `--dry-run` to inspect the operations without changes.

Every skill must declare `deployment` in its `SKILL.md` YAML header.
The installer reads this custom field to select agents.

For all supported installed agents:

```yaml
deployment:
  include:
  - all
```

Use `"*"` in place of `all` for the same selection. Quote the asterisk in YAML.

For selected agents:

```yaml
deployment:
  include:
  - openai
  - muse
```

To exclude specific agents:

```yaml
deployment:
  exclude:
  - claude
```

The agent names are `openai`, `claude`, `opencode`, `antigravity`, and `muse`.
`openai` selects Codex. Its command name and CLI target remain `codex`.
Declare exactly one of `include` or `exclude` with a nonempty list of distinct names.
`include` accepts specific names or one `all` or `"*"` entry.
`exclude` accepts only specific names.
Missing declarations, unknown agents, and invalid fields stop installation before target changes.
Duplicate skill directory names across collections also stop installation.

The public `agent-runtime` package owns shared role assignments and host bindings.
Task `agents/runtime.yaml` files reference the installed `mprlab-governor` contract.
The public installer includes this dependency with selected workflows.
Use `--dry-run` for a preview and `--check` for a read-only drift check.

`sync-plugins.sh` builds the checked-in Codex plugin package.
It does not install skills or register a marketplace.

## Skills

| Skill | Codex | Claude Code |
|---|---|---|
| Email Cleanup | `tyemirov:Email Cleanup` | `/email-cleanup` |
| Git Commit | `tyemirov:Git Commit` | `/git-commit` |
| Git Release | `tyemirov:Git Release` | `/git-release` |
| Simp | `tyemirov:simp` | `/simp` |
| Tidy Folder | `tyemirov:Tidy Folder` | `/tidy-folder` |
| [Whip](whip/README.md) | `tyemirov:whip` | `/whip` |

### Whip document revisions

Whip preserves approved document content through baseline comparisons and independent review.
See [Whip](whip/README.md) for the method, examples, and reviewer setup.

Install all public skills and bundled Codex reviewers from this checkout:

```bash
uv run --script install-skills
```

The public installer preserves existing skill links, unrelated skills, and controller model settings.
It preserves identical reviewer files and stops before writes when reviewer contents conflict.
Use `--dry-run` for a preview and `--check` for verification.
The plugin bundle contains Whip, but its reviewer needs the setup described in the Whip README.

### Simp across hosts

Simp's complete directory can be linked into each host without changing its
workflow:

| Host | Invocation | Personal/global discovery path |
|---|---|---|
| Codex | `$simp audit repo` | `~/.agents/skills/simp/` |
| Claude Code | `/simp audit repo` | `~/.claude/skills/simp/` |
| OpenCode | `Use the simp skill to audit this repository.` | `~/.config/opencode/skills/simp/` |
| Gemini CLI | `Use the simp skill to audit this repository.` | `~/.agents/skills/simp/` |
| Antigravity | `Use the simp skill to audit this repository.` | `~/.gemini/config/skills/simp/` |

See [`simp/README.md`](simp/README.md) for project-scoped locations and apply
mode examples.

## Skill format

Each skill is a self-contained directory with a `SKILL.md` file containing YAML
frontmatter (`name`, `description`) and the full workflow prompt. Each skill declares its installer selection under `deployment`.
The Markdown workflow remains shared across agents.

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
