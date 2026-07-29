# Simp

A portable Codex, Claude Code, Gemini CLI, and Antigravity skill for repository
simplification under a forward-only current-functionality contract.

Simp preserves current supported functionality. It does not preserve deprecated
APIs, legacy paths, old persisted shapes, fallbacks, aliases, dual reads or
writes, downgrade paths, or compatibility shims.

## Install

Keep `simp/` as the canonical source. Link or copy that complete directory to
the current discovery path for each host:

| Host | Project scope | Personal/global scope |
|---|---|---|
| Codex | `.agents/skills/simp/` | `~/.agents/skills/simp/` |
| Claude Code | `.claude/skills/simp/` | `~/.claude/skills/simp/` |
| Gemini CLI | `.agents/skills/simp/` | `~/.agents/skills/simp/` |
| Antigravity | `.agents/skills/simp/` | `~/.gemini/config/skills/simp/` |

Codex and Gemini CLI deliberately share the open `.agents/skills` location.
Antigravity uses the same project location and its current global location.

This repository also distributes Simp through the `tyemirov` Codex plugin.

## Portable contract

The shared `SKILL.md` uses only the portable `name` and `description`
frontmatter fields. The complete workflow, references, and template are
host-neutral. Codex-specific UI and invocation policy live in
`agents/openai.yaml`; no other host adapter is required.

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

Gemini CLI or Antigravity:

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
