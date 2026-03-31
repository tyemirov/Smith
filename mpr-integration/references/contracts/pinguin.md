# Pinguin Integration

Pinguin is the notification service. In this repo the app uses it for completion emails, but only when the app policy explicitly enables that behavior.

## Purpose

- Pinguin owns notification delivery, tenant email settings, and SMTP-backed sending.
- The app owns when to send notifications.
- The app owns the enable/disable policy flag and the app-local adapter boundary.

## Inputs

- Exact literals:
  - app config keys: `pinguin.grpc_addr`, `pinguin.auth_token`, `pinguin.tenant_id`, `pinguin.completion_emails_enabled`
  - host-run port: `localhost:50052`
  - app-container address in local Docker: `pinguin:50051`
  - notification type used by the app: `grpcapi.NotificationType_EMAIL`
- Files to touch:
  - `.env.example`
  - `docker-compose.yml`
  - `configs/config.yaml`
  - `configs/config.localhost.yaml`
  - `configs/pinguin-config.yaml`
  - `internal/config/config.go`
  - `cmd/server/main.go`
  - `internal/clients/pinguin_adapter.go`
  - `internal/jobs/runner.go`
  - `test/live/pinguin_test.go`

| Input | Consumed by | Type | Required locally | Required when hosted | Notes |
| --- | --- | --- | --- | --- | --- |
| `PINGUIN_GRPC_ADDR` | app | internal | yes | yes | App dials this gRPC address. |
| `PINGUIN_AUTH_TOKEN` | app + Pinguin | internal secret | yes | yes | Must match the server token. |
| `PINGUIN_TENANT_ID` | app + Pinguin | internal | yes | yes | Must match the configured tenant. |
| `PINGUIN_COMPLETION_EMAILS_ENABLED` | app | internal policy | yes | yes | Explicitly decides whether the app constructs a client. |
| `PINGUIN_MASTER_ENCRYPTION_KEY` | Pinguin | internal secret | yes | yes | Required by the service even when delivery is disabled. |
| `PINGUIN_SMTP_HOST` / `PINGUIN_SMTP_PORT` / `PINGUIN_SMTP_USERNAME` / `PINGUIN_SMTP_PASSWORD` | Pinguin | internal | no | yes | Required for real delivery. |
| `PINGUIN_FROM_EMAIL` / `PINGUIN_ADMIN_EMAIL` | Pinguin | browser-visible output | no | yes | Sender and support identity. |

## Source Of Truth

- `.env.example`
- `docker-compose.yml`
- `configs/config.yaml`
- `configs/config.localhost.yaml`
- `configs/pinguin-config.yaml`
- `internal/config/config.go`
- `cmd/server/main.go`
- `internal/clients/pinguin_adapter.go`
- `internal/jobs/runner.go`
- `test/live/pinguin_test.go`

## Decision Procedure

1. Add `pinguin.grpc_addr`, `pinguin.auth_token`, `pinguin.tenant_id`, and `pinguin.completion_emails_enabled` to app config validation.
2. If the app runs inside local Docker, use `pinguin:50051` for the app container.
3. Else if the verification command runs from the host, use `localhost:50052`.
4. Keep app config separate from Pinguin service config. Do not mix SMTP credentials into app-only config.
5. In app startup, only construct the Pinguin client if `completion_emails_enabled` is `true`.
6. Wrap the client in an app-local adapter before wiring it into jobs or workflows.
7. For localhost development, keep `PINGUIN_COMPLETION_EMAILS_ENABLED=false` unless you intentionally configured working SMTP-backed delivery.

## Minimal Code Or Config Example

```yaml
pinguin:
  grpc_addr: "${PINGUIN_GRPC_ADDR}"
  auth_token: "${PINGUIN_AUTH_TOKEN}"
  tenant_id: "${PINGUIN_TENANT_ID}"
  completion_emails_enabled: ${PINGUIN_COMPLETION_EMAILS_ENABLED}
```

```go
var notificationService jobs.NotificationService
if *applicationConfig.Pinguin.CompletionEmailsEnabled {
    settings, err := pinguinclient.NewSettings(
        applicationConfig.Pinguin.GRPCAddr,
        applicationConfig.Pinguin.AuthToken,
        applicationConfig.Pinguin.TenantID,
        10,
        30,
    )
    if err != nil {
        return err
    }

    client, err := pinguinclient.NewNotificationClient(slog.Default(), settings)
    if err != nil {
        return err
    }

    notificationService = clients.NewPinguinAdapter(client)
}
```

## Expected Result

- The app does not attempt notification delivery when `completion_emails_enabled` is `false`.
- The app reaches Pinguin successfully when the flag is `true`.
- The app and Pinguin agree on gRPC address, auth token, and tenant id.
- A real live email can be sent when SMTP-backed delivery is configured.

## Verification

```bash
# bring up the local stack
./scripts/up.sh

# inspect the compose-expanded notification config
docker compose config | rg 'PINGUIN_(GRPC_ADDR|AUTH_TOKEN|TENANT_ID|COMPLETION_EMAILS_ENABLED)'

# inspect the localhost policy flag
rg '^PINGUIN_COMPLETION_EMAILS_ENABLED=' .env

# verify live delivery when SMTP and recipient env vars are configured
PINGUIN_GRPC_ADDR=localhost:50052 \
PINGUIN_AUTH_TOKEN="$PINGUIN_AUTH_TOKEN" \
PINGUIN_TENANT_ID="$PINGUIN_TENANT_ID" \
PINGUIN_TEST_RECIPIENT="$PINGUIN_TEST_RECIPIENT" \
go test -tags=live ./test/live -run TestPinguin_SendEmail -count=1 -v
```

## Failure Map

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Local development shows SMTP or credential errors on normal startup | the app enabled completion emails in localhost without real delivery config | Set `PINGUIN_COMPLETION_EMAILS_ENABLED=false` for local development unless SMTP is intentionally configured. |
| App cannot connect to Pinguin in Docker | app uses `localhost:50052` from inside the container | Use `pinguin:50051` for the app container. |
| Pinguin rejects requests | auth token or tenant id mismatch | Align `PINGUIN_AUTH_TOKEN` and `PINGUIN_TENANT_ID` between app and service config. |
| Startup succeeds but no email is ever sent | the enable flag is false or unset, so the app never constructs the client | Make the flag explicit and validate it at startup. |

## Stop Rules

- Stop if the deployment policy does not say whether completion emails should be enabled.
- Stop if the tenant id or auth token for the Pinguin deployment is unknown.
- Stop if the app is expected to own SMTP settings directly instead of treating Pinguin as the notification boundary.

## Change Checklist

- [ ] App config requires `grpc_addr`, `auth_token`, `tenant_id`, and an explicit enable flag.
- [ ] Local Docker uses `pinguin:50051` inside the app container.
- [ ] Host-run verification uses `localhost:50052`.
- [ ] The app creates the client only when the enable flag is `true`.
- [ ] Pinguin service config remains separate from app config.
- [ ] A live notification test exists for the enabled path.
