# Claude Setup

Use the files under `../shared/` as project-level instructions or as the first
message in a Claude conversation.

Recommended workflow:

1. Create a Claude Project for the repository or workflow.
2. Copy one prompt from `../shared/` into the Project instructions.
3. Attach or open the relevant repository so Claude can inspect files.
4. Enable terminal/tool access if you want command execution.

Notes:

- Keep the prompt focused. Use one primary prompt per Project unless you are
  intentionally combining behaviors.
- For `mediaops`, make sure Claude can see this repository and the `Sheet2Tube`
  source checkout or a valid `MEDIAOPS_REPO`.
