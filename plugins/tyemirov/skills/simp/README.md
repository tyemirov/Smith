# Simp

A portable Codex, Claude Code, Antigravity CLI, and Antigravity App skill for repository
simplification under a forward-only current-functionality contract.

Simp preserves current supported functionality. It does not preserve deprecated
APIs, legacy paths, old persisted shapes, fallbacks, aliases, dual reads or
writes, downgrade paths, or compatibility shims.

## Install

From the collection root, install Simp with this command:

```bash
./install-skills --skill simp
```

Keep `simp/` as the canonical source. Link or copy that complete directory to
the current discovery path for each host:

| Host | Project scope | Personal/global scope |
|---|---|---|
| Codex | `.agents/skills/simp/` | `~/.agents/skills/simp/` |
| Claude Code | `.claude/skills/simp/` | `~/.claude/skills/simp/` |
| Antigravity CLI (`agy`) | `.agents/skills/simp/` | `~/.gemini/antigravity-cli/skills/simp/` |
| Antigravity App (desktop) | `.agents/skills/simp/` | `~/.gemini/config/skills/simp/` |

Antigravity CLI and the desktop app share the project location but use different global directories.
The installer target `antigravity` requires `agy` and installs CLI skills.
For the desktop app, link or copy the skill to its listed directory.
See the [official skill paths](https://antigravity.google/docs/skills).

This repository also distributes Simp through the `tyemirov` Codex plugin.

## Portable contract

The shared `SKILL.md` declares `name`, `description`, and `deployment` in its YAML header.
The collection installer uses `deployment` to select permitted hosts.
The complete workflow, references, and template are host-neutral. The `agents/openai.yaml` file contains Codex UI metadata and invocation policy.
The other hosts use the shared workflow.

Implicit activation is safe: `audit` is the default and cannot modify the
repository. The skill enters `apply` mode only when the user explicitly selects
`apply`.

## Use

Codex:

```text
$simp audit repo
$simp annotate internal/payments
$simp apply pkg/parser
```

Claude Code:

```text
/simp audit repo
/simp annotate internal/payments
/simp apply pkg/parser
```

Antigravity CLI (`agy`):

```text
/simp audit repo
/simp annotate internal/payments
/simp apply pkg/parser
```

Antigravity App (desktop):

```text
Use the simp skill to audit this repository.
Use the simp skill to annotate internal/payments.
Use the simp skill. Apply it to pkg/parser.
```

`audit` leaves the repository unchanged. `apply` processes one independently
verified candidate at a time.

## Design choice

The skill treats simplification as an optimization objective constrained by the
repository's one canonical current functionality contract. Repository
instructions outrank stale tests, examples, fixtures, documentation, and old
callers. Obsolete contracts and their supporting artifacts are removal targets.
