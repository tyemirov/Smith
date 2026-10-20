# Git Release

Git Release prepares and publishes repository artifacts through separate lifecycle phases.
It keeps the prepared artifact identity consistent through publication.

## Problem

A release process can build one artifact during validation and a different artifact during publication.
Combining preparation, publication, and deployment can also obscure which operations succeeded.

## Method

| Phase | Operation | Result |
| --- | --- | --- |
| Release | Validate and prepare artifacts locally | Manifest, payload hashes, local commit, and tag |
| Publish | Verify and publish the prepared artifacts | Remote references and verified publication results |
| Deploy | Activate an exact published artifact | A separate deployment result under repository guidance |

Release requires the default branch and a clean working directory.
It runs the repository CI gate and declared artifact targets.
Publish verifies the manifest and payload hashes before remote writes.
Each phase requires the corresponding user request.

## Install and use

Use the [collection installation guide](https://github.com/tyemirov/Smith#local-installation).
Run this command from the collection root:

```bash
./install-skills --skill gitrelease
```

The installer includes [Agent Runtime](../agent-runtime/README.md).
The target repository must define the documented lifecycle targets and required artifact tools.
Publication also requires access to the selected remote destinations.

Select `tyemirov:Git Release` in the Codex plugin, or use `$Git Release` after direct installation.
In Claude Code, use `/git-release`.

## Example

```text
Use Git Release to prepare the next release locally.
Run the repository validation and prepare all declared artifacts.
Report the selected version, local tag, and manifest path.
```

The result records prepared artifacts under `.git/mprlab-release` and identifies their hashes.
A later request can publish that exact prepared release:

```text
Use Git Release to publish the prepared release and verify each publication target.
```

Read [SKILL.md](SKILL.md) for version selection, bundled commands, and phase boundaries.
