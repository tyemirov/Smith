# Harness Workflow

Use this skill when the job is to evaluate or repair an integration from explicit contracts instead of repo archaeology.

## Resource Split

- `references/contracts/*.md`
  The reusable tool contracts.
- `assets/profiles/*.toml`
  App-specific literal bindings.
- `assets/tasks/**/*.toml`
  Declarative greenfield or seeded tasks.
- `assets/seeds/**/*.patch`
  Realistic broken states.
- `assets/fixtures/**`
  Minimal apps or sandboxes the agent edits.
- `scripts/run-agent`
  Wrapper that orchestrates task execution.
- `scripts/verify/*.sh`
  Observable verification only.

## Recommended Sequence

1. Read the relevant contract.
2. Read the target app profile.
3. Read the task file.
4. Run `scripts/run-agent`.
5. Inspect verification output.
6. Classify any failure.

## Failure Classification

Use the rubric from `references/quality.md`:

- guide defect
- agent defect
- environment defect

## Preferred Task Shape

Keep task files declarative:

- `id`
- `mode`
- `contract`
- `profile`
- `fixture`
- `seed_patch`
- `verify_script`
- `prompt`

Do not put execution logic inside the task file.
