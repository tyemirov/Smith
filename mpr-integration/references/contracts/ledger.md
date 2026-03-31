# Ledger Integration

Ledger is the shared virtual-credit service. Ledger owns balances and reservation settlement. The app owns when to grant, reserve, capture, release, and expose balances.

## Purpose

- Ledger owns user balances and idempotent grant, reserve, capture, and release operations.
- The app owns the gRPC wiring and the app-local credits service.
- The app owns `/api/balance` and any onboarding grant policy.

## Inputs

- Exact literals:
  - config keys: `ledger.grpc_addr`, `ledger.tenant_id`, `ledger.ledger_id`
  - host-run port: `localhost:50051`
  - app-container address in local Docker: `ledger:50051`
  - default namespace in this repo: tenant `trademark`, ledger `default`
  - authenticated balance route: `GET /api/balance`
  - balance response keys: `total`, `available`
  - deterministic key prefixes: `welcome-`, `job-`, `reserve-`, `capture-`, `release-`
- Files to touch:
  - `.env.example`
  - `docker-compose.yml`
  - `configs/config.yaml`
  - `configs/config.localhost.yaml`
  - `cmd/server/main.go`
  - `internal/config/config.go`
  - `internal/clients/ledger.go`
  - `internal/credits/service.go`
  - `internal/api/balance_handler.go`
  - `internal/api/onboarding.go`
  - `cmd/grant-credits/main.go`
  - `cmd/mint-token/main.go`
  - `test/live/ledger_test.go`
  - `test/live/pipeline_e2e_test.go`

| Input | Consumed by | Type | Required locally | Required when hosted | Notes |
| --- | --- | --- | --- | --- | --- |
| `LEDGER_GRPC_ADDR` | app | internal | yes | yes | App dials this gRPC address. |
| `ledger.tenant_id` | app + Ledger | internal | yes | yes | Must match the target Ledger tenant. |
| `ledger.ledger_id` | app + Ledger | internal | yes | yes | Must match the logical ledger bucket. |
| `/api/balance` | browser + app | browser-facing | yes | yes | Browser reads credits through the app, not from Ledger directly. |
| welcome-credit amount | app | internal policy | yes | yes | This repo uses `100` welcome credits. |

## Source Of Truth

- `.env.example`
- `docker-compose.yml`
- `configs/config.yaml`
- `configs/config.localhost.yaml`
- `cmd/server/main.go`
- `internal/config/config.go`
- `internal/clients/ledger.go`
- `internal/credits/service.go`
- `internal/api/balance_handler.go`
- `internal/api/onboarding.go`
- `cmd/grant-credits/main.go`
- `cmd/mint-token/main.go`
- `test/live/ledger_test.go`
- `test/live/pipeline_e2e_test.go`

## Decision Procedure

1. Add `LEDGER_GRPC_ADDR`, `ledger.grpc_addr`, `ledger.tenant_id`, and `ledger.ledger_id` to the app config contract.
2. If the app runs inside local Docker, use `ledger:50051` for the app container.
3. Else if the verification command runs from the host, use `localhost:50051`.
4. In app startup, create one Ledger gRPC connection and one app-local `LedgerClient`.
5. Wrap raw Ledger RPCs in one app-local credits service instead of scattering them through handlers.
6. Expose an authenticated `/api/balance` route if the UI shows credits.
7. If the product grants welcome credits, do it once through onboarding with an idempotent `welcome-` key.
8. Use deterministic reservation and idempotency keys for reserve, capture, and release flows.

## Minimal Code Or Config Example

```yaml
ledger:
  grpc_addr: "${LEDGER_GRPC_ADDR}"
  tenant_id: "trademark"
  ledger_id: "default"
```

```go
ledgerGRPCConnection, _ := grpc.NewClient(
    applicationConfig.Ledger.GRPCAddr,
    grpc.WithTransportCredentials(insecure.NewCredentials()),
)

ledgerClient := clients.NewLedgerClient(
    creditv1.NewCreditServiceClient(ledgerGRPCConnection),
    ledgerGRPCConnection,
    applicationConfig.Ledger.TenantID,
    applicationConfig.Ledger.LedgerID,
    logger,
)

creditsService := credits.NewService(ledgerClient, logger)
```

## Expected Result

- The app reaches Ledger successfully in both local Docker and host-run verification.
- Unauthenticated `GET /api/balance` returns `401`.
- Authenticated `GET /api/balance` returns JSON with `total` and `available`.
- Reserve and release restore available balance.
- Reserve and capture reduce total balance permanently.

## Verification

```bash
# bring up the local stack
./scripts/up.sh

# unauthenticated balance must be rejected
curl -i http://localhost:8080/api/balance

# mint an authenticated session cookie and seed credits for the test user
TAUTH_JWT_SIGNING_KEY="$TAUTH_JWT_SIGNING_KEY" \
LEDGER_GRPC_ADDR=localhost:50051 \
go run ./cmd/mint-token > /tmp/trademark-session.txt

# authenticated balance must return total and available
curl -sS \
  -H "Cookie: app_session=$(cat /tmp/trademark-session.txt)" \
  http://localhost:8080/api/balance

# verify Ledger live behavior directly
LEDGER_GRPC_ADDR=localhost:50051 \
go test -tags=live ./test/live -run 'TestLedger_(GetBalance|ReserveAndRelease|ReserveAndCapture)' -count=1 -v

# verify the app-facing balance API contract
TRADEMARK_BASE_URL=http://localhost:8080 \
TRADEMARK_SESSION_COOKIE="$(cat /tmp/trademark-session.txt)" \
LEDGER_GRPC_ADDR=localhost:50051 \
go test -tags=live ./test/live -run 'TestPipeline_E2E_(GetBalance|UnauthenticatedRequestRejected)' -count=1 -v
```

## Failure Map

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| App container cannot reach Ledger | app uses `localhost:50051` from inside Docker | Use `ledger:50051` for the app container. |
| Balance stays zero or appears in the wrong namespace | tenant id or ledger id does not match the target Ledger namespace | Align `ledger.tenant_id` and `ledger.ledger_id` on both sides. |
| New users do not get default credits | onboarding is not wired to the credits service | Route welcome grants through onboarding with an idempotent `welcome-` key. |
| Reserve/capture/release semantics differ by handler | app code bypasses the shared credits service | Centralize Ledger semantics in one app-local credits service. |

## Stop Rules

- Stop if the tenant id or ledger id for the deployment is unknown.
- Stop if the app wants to call raw Ledger RPCs directly from multiple handlers.
- Stop if the browser is expected to talk to Ledger directly instead of using app APIs.

## Change Checklist

- [ ] App config requires `ledger.grpc_addr`, `ledger.tenant_id`, and `ledger.ledger_id`.
- [ ] Local Docker uses `ledger:50051` inside the app container.
- [ ] Host-run verification uses `localhost:50051`.
- [ ] App startup creates one Ledger client and one app-local credits service.
- [ ] `/api/balance` is authenticated and returns `total` plus `available`.
- [ ] Reserve, release, and capture flows use deterministic keys.
