---
name: mpr-integration
description: Use when Codex needs to evaluate, repair, or scaffold integrations for Marco Polo Research Lab tools from explicit contracts, app profiles, seeded tasks, fixtures, and verification scripts. Trigger for black-box integration testing, seeded misconfiguration repair, contract drift checks, or reusable integration workflows for tools such as TAuth, `mpr-ui`, Ledger, Pinguin, crawler, scraper, or billing.
---

# MPR Integration

Run shared integration tasks from a stable contract:

1. choose a contract
2. choose an app profile
3. choose a seeded or greenfield task
4. run the bundled wrapper
5. run verification
6. classify the result as guide defect, agent defect, or environment defect

## Skill Path

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export MPR_INTEGRATION_SKILL="$CODEX_HOME/skills/mpr-integration"
export MPR_INTEGRATION_RUNNER="$MPR_INTEGRATION_SKILL/scripts/run-agent"
```

## Quick Start

Set one runner command per agent:

```bash
export MPR_INTEGRATION_CODEX_RUNNER='codex exec --cwd "$MPR_INTEGRATION_AGENT_WORKDIR" "$(cat "$MPR_INTEGRATION_AGENT_PROMPT_FILE")"'
export MPR_INTEGRATION_GEMINI_RUNNER='gemini --cwd "$MPR_INTEGRATION_AGENT_WORKDIR" --prompt-file "$MPR_INTEGRATION_AGENT_PROMPT_FILE"'
```

Run the bundled example task:

```bash
tmp_root="$(mktemp -d)"
out_dir="$(mktemp -d)"

"$MPR_INTEGRATION_RUNNER" \
  codex \
  "$tmp_root/workdir" \
  "$MPR_INTEGRATION_SKILL/assets/tasks/tauth/wrong-browser-host.toml" \
  "$out_dir"
```

The output directory will contain:

- `prompt.txt`
- `metadata.json`
- `agent.stdout.log`
- `agent.stderr.log`
- `verify.stdout.log`
- `verify.stderr.log`

## Autonomy

Execute the full workflow without pausing for user confirmation between steps.
The validation gates defined in this workflow are the only stopping points.
Do not ask "should I proceed?" or "should I continue?" at intermediate steps.
Report the final outcome when the workflow completes or a gate stops it.

## Workflow

### 1. Choose the contract

Open only the contract you need:

- `references/contracts/tauth.md`
- `references/contracts/mpr-ui.md`
- `references/contracts/ledger.md`
- `references/contracts/pinguin.md`
- `references/contracts/crawler.md`
- `references/contracts/scraper.md`
- `references/contracts/billing.md`

Read `references/quality.md` when you need the grading rubric or failure classification.

### 2. Choose the profile

Profiles bind the generic contract to exact app literals:

- cookie name
- issuer
- public origin
- tenant id
- ports
- route names

Example profile:

- `assets/profiles/trademark.toml`

### 3. Choose the task

Task files are declarative. They should say:

- which contract to use
- which profile to use
- which fixture to copy
- which seed to apply
- which verify script to run
- which prompt to send

Example task:

- `assets/tasks/tauth/wrong-browser-host.toml`

### 4. Run the wrapper

Use the stable shell contract:

```bash
"$MPR_INTEGRATION_RUNNER" <agent-name> <workdir> <task-file> <output-dir>
```

Do not embed wrapper logic into the task file. Keep the task declarative.

### 5. Interpret the result

If verification fails:

- use `references/quality.md` to classify the failure
- inspect the `metadata.json` and logs in the output directory
- report whether the failure is a guide defect, agent defect, or environment defect

## Bundled Resources

Open only what you need:

- Harness workflow and grading:
  - `references/quality.md`
  - `references/guide-template.md`
- Contracts:
  - `references/contracts/*.md`
- Example profile:
  - `assets/profiles/trademark.toml`
- Example task and seed:
  - `assets/tasks/tauth/wrong-browser-host.toml`
  - `assets/seeds/tauth/wrong-browser-host.patch`
- Example fixture:
  - `assets/fixtures/tauth-site/`
- Executable scripts:
  - `scripts/run-agent`
  - `scripts/verify/tauth.sh`

## Guardrails

- Keep task files declarative.
- Keep contracts generic and profiles app-specific.
- Put raw CLI syntax in runner env vars, not in tasks.
- Verify observable outcomes only.
- Stop when a required value is missing from the contract or profile instead of guessing.
- Use the smallest fixture that still proves the contract.
