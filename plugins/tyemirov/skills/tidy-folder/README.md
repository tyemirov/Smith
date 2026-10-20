# Tidy Folder

Tidy Folder organizes a specified folder around subjects, projects, and the way you search for files.
It preserves useful groups and records file operations for restoration.

## Problem

Files become difficult to find when names and folders hide their purpose.
An extension alone cannot distinguish a school record from a project document.

## Method

For authorized file operations, create the snapshot and run lock before the scan.

1. Inspect the target folder and collect evidence from names, content, metadata, and existing groups.
2. Propose destinations based on the most specific supported subject or project.
3. Review ambiguous placements and refine the folder hierarchy.
4. Validate the move manifest before authorized file operations.
5. Record moves and reversible cleanup operations in ledgers.
6. Audit the result and report the final folder structure.

The Scout, Router, Gatekeeper, Supervisor, and Executor roles have separate responsibilities.
The workflow records whether a review used one agent or an independent subagent.
Unresolved placement blockers stop file operations.

## Install and use

Use the [collection installation guide](https://github.com/tyemirov/Smith#local-installation).
Run this command from the collection root:

```bash
./install-skills --skill tidy-folder
```

The installer includes [Agent Runtime](../agent-runtime/README.md).
Give the agent an explicit target folder and the requested operation.
Select `tyemirov:Tidy Folder` in the Codex plugin, or use `/tidy-folder` in Claude Code.
Python helpers use `uv` through their script shebangs.

## Example

```text
Use Tidy Folder to review /path/to/Downloads and propose a folder structure.
Group files by project or subject and preserve coherent project directories.
Show the proposed destinations and unresolved ambiguities before any file operations.
```

A project cover image belongs with its project when the content supplies that evidence.
A school registration form belongs with the school records.

To authorize the next step, identify the same target and request the reorganization.
The workflow validates the current actions and preserves snapshot and ledger records.

Read [SKILL.md](SKILL.md) for the evidence rules, helper commands, and restoration procedure.
