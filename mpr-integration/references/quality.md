# Integration Guide Quality

This file defines how integration guides should be written and how they should be tested.

## Core Rule

A guide is good only if an agent can follow it like a small program.

If the guide reads like an essay, it is too ambiguous.

## Required Writing Style

Write every guide at roughly `if/else` level:

- short steps
- exact literals
- exact files to touch
- exact success conditions
- exact failure branches
- explicit stop conditions

The primary reading path is:

`Inputs -> Decision Procedure -> Expected Result -> Verification -> Failure Map -> Stop Rules`

## Required Sections

Every concrete integration guide should contain these sections, in this order:

1. `Purpose`
2. `Inputs`
3. `Source Of Truth`
4. `Decision Procedure`
5. `Expected Result`
6. `Verification`
7. `Failure Map`
8. `Stop Rules`
9. `Change Checklist`

Optional support sections:

- `Minimal Code Or Config Example`
- `Strategy Status` for non-executable docs

`Stable Contract`, `Ownership Split`, `Files To Touch`, and `Minimal Integration Path` are no longer the primary structure. If those details matter, move them into `Inputs` or `Decision Procedure`.

## Simplification Rules

When a guide becomes hard to follow:

- merge repeated reference sections into `Inputs`
- keep one decision per numbered step
- keep local-Docker and hosted branches explicit
- prefer one exact command over three descriptive bullets
- remove background prose that does not change the next action

If a reader still has to search the repo to discover the main contract, the guide is not done.

## Agent Trial Harness

Test guides with black-box agents, not only by human reading.

The intended loop is:

1. prepare a small target app or sandbox
2. give Codex CLI or Gemini CLI one guide and one task
3. let the agent integrate using only that guide
4. run the checks listed by the guide
5. classify any failure as `guide defect`, `agent defect`, or `environment defect`

## Standard Agent Tasks

Use at least these tasks when evaluating a guide.

### Task A: Greenfield Integration

Prompt shape:

- build a minimal app page or service path that uses the integration
- follow only the supplied guide
- do not search unrelated files unless the guide says to

Expected examples:

- TAuth: a user can log in and protected routes reject unauthenticated requests
- `mpr-ui`: the correct CDN/bootstrap order is used
- Ledger: authenticated balance and reserve/capture/release flows work
- Crawler: proxy profiles load and critical-source readiness exists
- Scraper: one source client returns explicit success/failure states
- Pinguin: the app follows the documented enable/disable policy

### Task B: Seeded Misconfiguration Repair

Seed one realistic mistake, then ask the agent to fix it using only the guide.

Examples:

- wrong browser-facing port
- container-only hostname in browser config
- wrong CDN or invalid pinned version
- `localhost` used inside a container
- missing enable flag
- legacy plain-text proxy file instead of YAML

### Task C: Drift Detection

Ask the agent to compare the guide against the repo and report mismatches.

This catches stale guides even when the integration still works.

## Black-Box Evaluation Checks

At minimum, check:

- can the app page load
- can a user log in when auth is relevant
- do unauthenticated requests return `401` where expected
- do authenticated requests return `200` where expected
- are browser-facing ports correct
- are container-internal addresses absent from browser config
- are required CDN/library literals correct
- are required config keys present
- do the referenced commands or tests pass

For this repo specifically, common checks include:

- `/config-ui.yaml` exposes browser-reachable auth config
- TAuth is not exposed to the browser as `http://tauth:8443`
- `mpr-ui` uses the documented CDN/bootstrap order
- Ledger uses `ledger:50051` in-container and `localhost:50051` from host
- Pinguin uses an explicit enable/disable policy
- crawler config comes from YAML `PROXY_FILE`, not legacy plain text

## Failure Classification

Use these buckets when an agent fails.

### Guide Defect

Use this when:

- the guide omitted a required literal
- the guide omitted a required file touchpoint
- the guide failed to distinguish browser-facing vs internal addresses
- the guide failed to mention a required enable flag
- the guide failed to define the verification step that would have caught the error

### Agent Defect

Use this when:

- the guide contained the necessary instruction
- the agent ignored it
- the resulting error is directly contradicted by the guide

### Environment Defect

Use this when:

- the guide is correct
- the agent followed it
- but the local environment, secrets, ports, or tooling were unavailable

## Minimum Pass Criteria

A guide passes only if:

- both Codex and Gemini can complete the greenfield task, or
- one succeeds and the other fails only for a clearly classified agent/environment reason

and:

- the post-run checks pass
- the most likely seeded misconfiguration is repaired correctly

## Strategy-Guide Exception

Some docs are intentionally strategy-only. In this repo, [billing.md](./billing.md) is one of them.

Strategy guides should still use the same section order, but they are graded on:

- whether the contract is explicit
- whether the adapter boundaries are explicit
- whether the settlement path is explicit
- whether the verification expectations are explicit for a repo that implements the strategy

They are not graded by "can the agent finish the integration in this repo today" if the repo does not contain the provider implementation.

## Suggested Harness Contract

Wrap each agent CLI behind one stable shell contract:

```text
run-agent <agent-name> <workdir> <task-file> <output-dir>
```

Where:

- `agent-name` is `codex` or `gemini`
- `workdir` is the sandbox app
- `task-file` contains the integration task and the guide path
- `output-dir` stores logs, diffs, and test results

The evaluator should not depend on raw CLI syntax inside the wrapper.

## Current Migration Target

The concrete guides in this directory should keep moving toward this stricter shape:

- shorter `Inputs`
- direct `Decision Procedure` steps
- explicit `Expected Result`
- exact verification commands
- seeded-failure coverage
- explicit `Stop Rules`
