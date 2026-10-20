# Agent Orchestration

## Source And Authority

Agent Runtime owns the shared role tree in `agents/runtime.yaml`.
Task skills own their steps in their own `agents/runtime.yaml` files.
Each task contract uses `kind: workflow` and `governance: mprlab-governor`.
Task contracts contain role references instead of model assignments.
The shared host bindings contain all role model assignments.

The host supplies native delegation, concurrency limits, context handling, and tool execution.
The shared instructions define role selection and the architect checkpoints.
The primary agent owns task decisions and the final result.
Use the primary checkout for every role.
Apply the task's independent review and authorization gates.
A step with `required_review: true` requires independent review.
An optional `review_condition` limits that requirement to the stated cases.
Apply the shared architect checkpoints separately.

The shared instructions require an architect review before a large plan, after a repeated unexpected error, and before long-task completion.
These instructions guide the agent. They are not runtime hooks.
Record the actual execution method and review evidence.

## Installation

The public installer reads `[runtime]` in `agents/install.toml`.
The descriptor names the contract, renderer, and optional reference files.
The renderer emits three operation types: owned file, marked section, and scoped TOML values.
The installer validates every selected host plan before it writes governance files.
It checks for local edits and unowned file conflicts.
It preserves instructions outside the marked section.
It preserves the main model and effort in Codex configuration.
It validates scoped TOML operations without applying model defaults.
Approval policies and approval reviewers remain under host control.

The installer adds Agent Runtime for task skills that depend on it.
For a later workflow install, the host's `.governance/mprlab-governor.json` receipt identifies the shared source.
Keep that source available at its installed path.

```bash
./install-skills --dry-run
./install-skills --check
```

`--dry-run` shows governance diffs and planned skill operations.
`--check` returns zero when selected outputs match their source.
It returns one when drift exists.
Neither command changes host files or builds a backend.
Use the same command without these options to install approved changes.
Use `--force` to replace skill packages with existing content.
A Runtime-generated agent conflict still requires explicit reconciliation.
Bundled reviewers use `codex/agents/*.toml` inside each skill.
The installer validates their names and preflights destination conflicts before writes.
Identical reviewer files remain unchanged.
Use `--force` to back up and replace a conflicting bundled reviewer.

Muse packages contain tracked source files and explicitly declared runtime resources.
The installer preserves workflow role references during package creation.
It performs no per-skill model substitution.

## Host Adapters

| Host | Native role files | Model assignment | Shared instructions |
| --- | --- | --- | --- |
| Codex | `agents/mpr-*.toml` | Preserved controller, Sol worker, Luna explorer and researcher, Astra architect | Marked section in `AGENTS.md` |
| Claude Code | `agents/mpr-*.md` | Inherited model. Medium role effort and high architect effort | Marked section in `CLAUDE.md` |
| OpenCode | `agents/mpr-*.md` | Inherit the current model and effort | Marked section in `AGENTS.md` |
| Antigravity | `config/agents/mpr-*.md` | Inherit the current model and effort | Marked section in `GEMINI.md` |
| Muse | `governance/mprlab-governor.json` | Agent-read catalog with inherited model assignments | Agent Runtime and dependent task instructions |

Muse's catalog requires the agent to read and apply the contract.
It does not register native persistent agents.
The other adapters use the documented native role formats.
Read roles receive read-only instructions and native restrictions where supported.
The current host's permission settings still control tool execution.

## Model Updates

Before a model or orchestration change, apply [the lifecycle policy](lifecycle.md).
Agents own qualification tests and evidence collection.
The user supplies decisions and missing authorization.
The `maintenance` field names this policy relative to the skill root.
The governance contract remains under `agents/runtime.yaml`.
The renderer adds the policy reference to native instructions and the Muse catalog.
Read the policy only when orchestration maintenance applies.


1. Examine supported model IDs and effort values in the destination host.
2. Change the relevant host bindings in the shared contract.
3. Run the installer with `--dry-run`.
4. Review the generated diffs and reported conflicts.
5. Run the installer to update owned outputs.
6. Run the installer with `--check`.
7. Start a new host session and verify actual delegation metadata when available.

`inherit` follows the current host model selection.
An explicit model ID remains pinned until the shared source changes.
The installer does not infer a replacement from a model name.
Active profiles and invocation flags can override main configuration.
Inspect them separately and report their effect before model acceptance.

## Sources

- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [OpenCode agents](https://opencode.ai/docs/agents/)
- [Antigravity subagents](https://antigravity.google/docs/subagents)
- [Antigravity rules](https://antigravity.google/docs/rules)

Verify these native formats when a host update changes its agent contract.
