---
name: agent-runtime
description: Shared role definitions and host configuration for skills that require independent review or delegated work.
deployment:
  include:
  - all
---

# Agent Runtime

Use this package to resolve shared roles for dependent workflows.
The contract identifier is `mprlab-governor`.
The package contains the contract, renderer, and maintenance policy.

Read [the runtime contract](agents/runtime.yaml) before role selection.
Use the host bindings for the selected role.
Keep task authority with the primary agent.
Apply the task skill's authorization and validation gates.

For installation details, read [Agent orchestration](references/orchestration.md).
For model changes, host changes, or retirement, read [Lifecycle policy](references/lifecycle.md).

From the collection root, run `uv run --script install-skills` to install the skills and their runtime dependency.
Use `--dry-run` to preview changes or `--check` to verify the installation.
The installer preserves existing controller model settings.
It rejects conflicts with edited role files before it writes profile changes.
