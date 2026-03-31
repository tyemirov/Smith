# Integration Guide Template

Use this template for any shared integration manual.

Write it like a small runbook, not like a narrative explainer.

Primary reading path:

`Inputs -> Decision Procedure -> Expected Result -> Verification -> Failure Map`

## Purpose

- What the tool or service owns.
- What remains app-local.
- Whether the guide is concrete, optional, or strategy-only.

## Inputs

List every input an agent needs before it starts work.

- Exact literals:
  - env vars
  - config keys
  - routes
  - events
  - cookie names
  - ports
  - domains or origins
- Files to touch:
  - app config
  - service config
  - orchestration
  - runtime wiring
  - frontend or templates
  - tests
- Address table:

| Input | Consumed by | Type | Required locally | Required when hosted | Notes |
| --- | --- | --- | --- | --- | --- |
| `EXAMPLE_VAR` | app | browser-facing or internal | yes | yes | short note |

## Source Of Truth

- `path/to/env/example`
- `path/to/compose/orchestration`
- `path/to/service/config`
- `path/to/app/config`
- `path/to/runtime/wiring`
- `path/to/template/ui`
- `path/to/tests`

## Decision Procedure

Write this as explicit numbered if/else steps.

Example shape:

1. If local Docker is used, set `A`.
2. Else if hosted deployment is used, set `B`.
3. If browser traffic must reach the service, expose `C` on a browser-facing origin.
4. If app runtime needs internal service discovery, use `D`.
5. If a required flag is disabled, stop and report.
6. Otherwise wire the runtime adapter and continue.

## Minimal Code Or Config Example

```text
Replace this block with the smallest valid example.
```

## Expected Result

Describe what should be true when the integration is correct.

- API result:
- UI result:
- runtime result:
- observable logs or result state:

## Verification

Prefer exact commands over vague descriptions.

```bash
# local bring-up

# smoke test

# automated tests
```

## Failure Map

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| exact observable failure | broken contract | concrete repair |

## Stop Rules

Tell the agent when to stop instead of guessing.

- Stop if:
- Stop if:
- Report:

## Change Checklist

- [ ] Inputs list exact literals and files to touch.
- [ ] Browser-facing and container-internal addresses are separated.
- [ ] Decision Procedure uses direct if/else steps.
- [ ] Expected Result is observable.
- [ ] Verification contains copy-pasteable commands.
- [ ] At least one real failure mode is documented.
- [ ] Stop Rules are present.
