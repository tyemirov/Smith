# Codex Skills

This repository contains my custom Codex skills.

To install them on another machine, run:

```bash
./install-skills.sh
```

The installer symlinks each custom skill from this repository into
`~/.codex/skills`. Use `./install-skills.sh --help` for options such as
`--codex-home`, `--dry-run`, and `--force`.

Portable prompt versions for Claude and Gemini live under `portable/`.

Skills:

- `Git Commit`
- `Git Release`
- `mediaops`

Execution metadata:

- `agents/openai.yaml` is UI metadata for skill lists and default prompts.
- `agents/runtime.yaml` is a repo-local convention for execution routing when a
  host supports subagents with explicit `model` and `reasoning_effort`
  controls.
- Routing files should distinguish `fork-safe` steps from `same-worktree`
  steps so Git mutations stay in the live repository when a host runs
  subagents in isolated workspaces.

Notes:

- The repo only keeps the user-specific skills I authored.
- Secret-bearing local environment files are not tracked. See
  `mediaops/.env.example` for the expected variables.
- `mediaops/bin/mediaops` is a small wrapper. The compiled runtime is cached under
  `mediaops/.cache/bin/mediaops` when available.
- On a fresh machine, set `MEDIAOPS_REPO` to the `Sheet2Tube` source checkout or
  place that repo at `$HOME/Development/MarcoPoloResearchLab/Sheet2Tube` so the
  wrapper can build the runtime on demand.
