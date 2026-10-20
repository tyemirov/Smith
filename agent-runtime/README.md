# Agent Runtime

Agent Runtime supplies shared roles and host configuration for skills that delegate work or require independent review.
Its contract identifier is `mprlab-governor`.

## Problem

Separate role definitions in each skill can drift apart.
One workflow can then select different models or review rules from another workflow with the same responsibilities.

## Method

The package keeps one shared contract and renders the configuration for each supported host.
Task workflows reference roles from that contract.
The primary agent retains task authority and the final result.

| Role | Responsibility |
| --- | --- |
| Explorer | Inspect source code and report evidence |
| Worker | Implement a bounded change and run validation |
| Researcher | Retrieve primary documentation for a bounded question |
| Architect | Review substantial plans, repeated errors, and completed long tasks |

The installer preserves controller model settings and instructions outside its managed section.
It checks for conflicts with edited role files before profile changes.
A governance receipt records the source package and generated file hashes.

## Install and use

Use the [collection installation guide](https://github.com/tyemirov/Smith#local-installation).
Run this command from the collection root to install the runtime alone:

```bash
./install-skills --skill agent-runtime
```

The installer also includes this package when a selected workflow requires it.
Dependent skills read the contract before role selection.
For direct inspection, read [the runtime contract](agents/runtime.yaml) and [SKILL.md](SKILL.md).

## Example

Install Git Commit and its shared runtime dependency:

```bash
./install-skills --skill gitcommit
./install-skills --skill gitcommit --check
```

The first command installs both skills and the selected host's role configuration.
The second command verifies the installation without writes.
Existing controller model settings remain unchanged.

Read [Agent orchestration](references/orchestration.md) for host behavior and installation details.
Read [Lifecycle policy](references/lifecycle.md) before model changes, host changes, or retirement.
