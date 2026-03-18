# Portable Prompts

These files are plain Markdown prompt versions of the Codex skills in this
repository. They are intended for assistants that do not support Codex's native
`SKILL.md` loading model, including Claude and Gemini.

Available prompts:

- `shared/git-commit.md`
- `shared/git-release.md`
- `shared/mediaops.md`

Usage:

1. Pick the prompt that matches the workflow you want.
2. Paste its contents into a Claude Project instruction, a Gemini Gem
   instruction, or another assistant's system/custom prompt field.
3. Give the assistant terminal access if you want it to execute commands rather
   than only explain them.
4. Keep the repository checkout and any required tools available in the
   assistant's working environment.

Tool assumptions:

- `git-commit.md` expects `git` and `gix`.
- `git-release.md` expects `git`, `gh`, `gix`, and the repository's normal CI
  or release validation command such as `make ci`.
- `mediaops.md` expects this repository checkout plus the `Sheet2Tube` source
  repo available via `MEDIAOPS_REPO` or at
  `$HOME/Development/MarcoPoloResearchLab/Sheet2Tube`.

Platform notes:

- See `claude/README.md` for Claude-specific setup guidance.
- See `gemini/README.md` for Gemini-specific setup guidance.
