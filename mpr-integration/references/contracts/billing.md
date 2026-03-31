# Billing Integration Strategy

This repo ships the credits side through Ledger, but it does not ship a full provider-side billing implementation such as Stripe or Paddle checkout, webhook verification, or portal flows. This guide is therefore strategy-only.

## Strategy Status

- Concrete in this repo:
  - Ledger-backed credits
  - app-local credits service
  - authenticated balance API
- Not concrete in this repo:
  - checkout session creation
  - customer portal flows
  - webhook verification and parsing
  - provider-specific billing adapters

## Purpose

- The billing layer should own checkout, portal, webhook verification, and provider-event parsing.
- The app should own product catalog policy, provider selection per deployment, and settlement into Ledger.
- Ledger should remain the canonical credits boundary even when billing is added.

## Inputs

- Exact literals and boundaries that should exist in a billing-enabled repo:
  - one active billing provider per deployment
  - one provider-neutral grant event before Ledger settlement
  - canonical settlement fields: `user`, `credits`, `reference`, `reason_code`, `metadata`, `provider`, `event_id`
  - adapter boundaries: checkout creation, portal-session creation, webhook verification, webhook parsing, grant resolution, catalog validation
- Files to touch in a billing-enabled repo:
  - billing config schema and validation
  - provider adapter package
  - webhook handler package
  - settlement path into the Ledger or credits service
  - billing summary and activity API
  - frontend checkout and billing views
  - provider contract tests and end-to-end settlement tests

| Input | Consumed by | Type | Required locally | Required when hosted | Notes |
| --- | --- | --- | --- | --- | --- |
| provider config | billing adapter | internal | maybe | yes | Secrets, price ids, webhook secret, portal config. |
| canonical grant event | app + Ledger settlement path | internal | yes | yes | Provider-neutral event after verification and parsing. |
| Ledger client and credits service | app | internal | yes | yes | Billing should settle through Ledger, not UI math. |
| checkout and billing routes | browser + app | browser-facing | maybe | yes | User-visible billing entry points. |

## Source Of Truth

- [Ledger integration](./ledger.md)
- `ISSUES.md` entries `[I036]`, `[I039]`, and `[I070]`

## Decision Procedure

1. Decide which billing provider is active for the deployment. Do not build runtime fallback across multiple providers.
2. Add strict provider config validation and fail startup if required provider settings are missing.
3. Implement provider-specific behavior behind billing adapter interfaces.
4. Verify and parse provider webhooks into one provider-neutral grant event.
5. Apply that canonical grant event through the shared Ledger or credits boundary.
6. Expose billing summary, activity, delinquency, and checkout entry points through app-owned APIs and UI.
7. Add contract tests for provider parsing and end-to-end settlement tests for checkout or renewal to Ledger.

## Expected Result

- The deployment uses one explicit provider.
- Provider-specific code stays inside billing adapters.
- Duplicate provider events do not double-grant credits.
- All successful billing events settle into Ledger exactly once.
- User-visible billing state comes from app APIs, not ad hoc frontend math.

## Verification

```bash
# repo-level contract check available in this repo today
rg -n 'Grant|Reserve|Capture|Release|/api/balance' \
  internal/credits/service.go \
  internal/api/balance_handler.go \
  cmd/grant-credits/main.go

# issue-history contract check for the intended billing shape
rg -n '\[I036\]|\[I039\]|\[I070\]' ISSUES.md
```

In a repo that implements provider billing for real, the guide should also contain exact commands for:

- provider config validation
- checkout creation
- webhook signature verification
- duplicate-event idempotency
- end-to-end billing-to-Ledger settlement

## Failure Map

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Credits are granted twice for one payment | event idempotency is not enforced before Ledger settlement | Use canonical `event_id` handling before applying credits. |
| Billing config works in one env and silently degrades in another | provider config is not validated strictly | Fail startup on invalid provider config. |
| UI logic branches everywhere for each provider | provider behavior leaked outside adapters | Push provider-specific logic behind billing interfaces. |
| Payment succeeds but credits never appear | webhook parsing and Ledger settlement are not joined by a canonical grant contract | Introduce one provider-neutral grant event before Ledger application. |

## Stop Rules

- Stop if the deployment cannot choose one active billing provider.
- Stop if the app wants to grant credits directly from frontend or webhook code without a Ledger settlement boundary.
- Stop if provider-specific logic is expected to leak into unrelated app handlers or UI code.

## Change Checklist

- [ ] One active billing provider per deployment is explicit.
- [ ] Provider config validation is strict.
- [ ] Checkout, portal, webhook verification, and parsing are adapterized.
- [ ] A canonical grant event exists before Ledger settlement.
- [ ] Duplicate provider events are idempotent.
- [ ] A billing-enabled repo documents exact end-to-end settlement tests.
