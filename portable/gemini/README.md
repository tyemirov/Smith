# Gemini Setup

Use the files under `../shared/` as Gem instructions or paste them at the start
of a Gemini session.

Recommended workflow:

1. Create a Gem for the repository or workflow.
2. Copy one prompt from `../shared/` into the Gem instructions.
3. Open the repository or provide file access so Gemini can inspect local files.
4. Enable shell/tool access if you want Gemini to execute commands.

Notes:

- Keep each Gem narrow. Use one prompt per Gem unless you want a deliberately
  blended workflow.
- For `mediaops`, make sure Gemini can access this repository and the
  `Sheet2Tube` source checkout or a valid `MEDIAOPS_REPO`.
