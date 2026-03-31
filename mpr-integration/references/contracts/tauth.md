# TAuth Integration

`TAuth` owns Google sign-in and the session cookie. The app owns local cookie validation, protected routes, and the browser config that points `mpr-ui` at the auth endpoints.

## Purpose

- `TAuth` owns login, logout, nonce, and session-cookie issuance.
- The app owns local validation of `app_session`.
- The app owns `/config-ui.yaml` and route protection.

## Inputs

- Exact literals:
  - cookie name: `app_session`
  - JWT issuer: `tauth`
  - browser-loaded script: `{{.TAuthURL}}/tauth.js`
  - browser-facing config endpoint: `/config-ui.yaml`
  - auth paths: `/auth/google`, `/auth/logout`, `/auth/nonce`
  - same-origin local proxy paths: `/tauth.js`, `/auth`, `/me`, `/api/me`
- Files to touch:
  - `.env.example`
  - `docker-compose.yml`
  - `configs/tauth-config.yaml`
  - `configs/config.yaml`
  - `configs/config.localhost.yaml`
  - `cmd/server/main.go`
  - `internal/api/routes.go`
  - `internal/web/templates/layout.html`
  - `test/web/e2e/global-setup.ts`
  - `test/web/e2e/app.spec.ts`

| Input | Consumed by | Type | Required locally | Required when hosted | Notes |
| --- | --- | --- | --- | --- | --- |
| `PUBLIC_ORIGIN` | app + TAuth | browser-facing | yes | yes | Canonical browser origin for the app. |
| `PUBLIC_HOST` | supporting services | browser-facing | yes | yes | Host-only value for allowlists and callbacks. |
| `TAUTH_URL` | app + browser | browser-facing | yes | yes | Must be reachable by the browser. |
| `TAUTH_TENANT_ID` | app + `mpr-ui` config | browser-facing | yes | yes | Must match the tenant id in TAuth config. |
| `TAUTH_JWT_SIGNING_KEY` | app + TAuth | internal secret | yes | yes | Used by TAuth to sign and by the app to validate. |
| `GOOGLE_CLIENT_ID` | app + TAuth + `mpr-ui` | browser-facing | yes | yes | Shared Google OAuth client id. |
| `TAUTH_COOKIE_DOMAIN` | TAuth | browser-facing | yes | yes | Must fit the deployed hostname. |
| `TAUTH_ALLOW_INSECURE_HTTP` | TAuth | browser-facing policy | yes | maybe | `true` for localhost HTTP, `false` for hosted HTTPS. |

## Source Of Truth

- `.env.example`
- `docker-compose.yml`
- `configs/tauth-config.yaml`
- `configs/config.yaml`
- `configs/config.localhost.yaml`
- `cmd/server/main.go`
- `internal/api/routes.go`
- `internal/web/templates/layout.html`
- `cmd/server/main_test.go`
- `test/web/e2e/global-setup.ts`
- `test/web/e2e/app.spec.ts`
- `cmd/mint-token/main.go`

## Decision Procedure

1. If local Docker is used, keep the browser on `http://localhost:8080` and proxy `TAuth` through the front door on the same origin.
2. Else if hosted deployment is used, set `PUBLIC_ORIGIN`, `PUBLIC_HOST`, `TAUTH_URL`, `TAUTH_COOKIE_DOMAIN`, and `TAUTH_ALLOW_INSECURE_HTTP` for the real browser origin and TLS mode.
3. Add a tenant entry to `configs/tauth-config.yaml` before wiring the app.
4. In app config, require `TAUTH_URL`, `TAUTH_TENANT_ID`, `TAUTH_JWT_SIGNING_KEY`, `GOOGLE_CLIENT_ID`, issuer `tauth`, and cookie name `app_session`.
5. In app startup, create one session validator with signing key `TAUTH_JWT_SIGNING_KEY`, issuer `tauth`, and cookie name `app_session`.
6. Mount auth middleware on protected app routes so unauthenticated requests return `401`.
7. Serve `/config-ui.yaml` with `tauthUrl`, `googleClientId`, `tenantId`, `loginPath`, `logoutPath`, and `noncePath`.
8. Load `{{.TAuthURL}}/tauth.js` in the page template after `TAUTH_URL` is known to be browser-facing.
9. Add authenticated browser tests using a minted `app_session` token.

## Minimal Code Or Config Example

```yaml
auth:
  jwt_signing_key: "${TAUTH_JWT_SIGNING_KEY}"
  jwt_issuer: "tauth"
  cookie_name: "app_session"
  tauth_url: "${TAUTH_URL}"
  tauth_tenant_id: "${TAUTH_TENANT_ID}"
  google_client_id: "${GOOGLE_CLIENT_ID}"
```

```go
sessionValidator, err := sessionvalidator.New(sessionvalidator.Config{
    SigningKey: []byte(applicationConfig.Auth.JWTSigningKey),
    Issuer:     applicationConfig.Auth.JWTIssuer,
    CookieName: applicationConfig.Auth.CookieName,
})
```

## Expected Result

- Browser auth traffic stays on the app origin instead of pointing at a Docker-only hostname.
- `/config-ui.yaml` exposes browser-reachable auth config.
- Unauthenticated protected API requests return `401`.
- A valid `app_session` cookie unlocks protected routes and authenticated UI tests.

## Verification

```bash
# bring up the local stack
./scripts/up.sh

# verify the browser-facing config is exposed
curl -fsS http://localhost:8080/config-ui.yaml

# verify protected routes reject unauthenticated requests
curl -i http://localhost:8080/api/jobs

# mint an authenticated session cookie for local checks
TAUTH_JWT_SIGNING_KEY="$TAUTH_JWT_SIGNING_KEY" \
LEDGER_GRPC_ADDR=localhost:50051 \
go run ./cmd/mint-token > /tmp/trademark-session.txt

# verify the same route succeeds with a valid cookie
curl -sS \
  -H "Cookie: app_session=$(cat /tmp/trademark-session.txt)" \
  http://localhost:8080/api/jobs

# verify the UI config builder contract
go test ./cmd/server -run TestBuildUIConfig_UsesConfiguredPublicOrigin -count=1

# verify browser auth and protected-route behavior
cd test/web && \
TRADEMARK_BASE_URL=http://localhost:8080 \
TAUTH_JWT_SIGNING_KEY="$TAUTH_JWT_SIGNING_KEY" \
LEDGER_GRPC_ADDR=localhost:50051 \
npx playwright test app.spec.ts
```

## Failure Map

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Browser login points at `http://tauth:8443` | `TAUTH_URL` was set to a container-internal hostname | Set `TAUTH_URL` to the browser-facing origin and keep same-origin proxying in place. |
| Valid-looking cookie still gets `401 session required` | signing key, issuer, or cookie name does not match TAuth | Align `TAUTH_JWT_SIGNING_KEY`, issuer `tauth`, and cookie name `app_session` on both sides. |
| Localhost works but hosted cookies fail | cookie domain or insecure-HTTP setting still assumes localhost | Set `TAUTH_COOKIE_DOMAIN` and `TAUTH_ALLOW_INSECURE_HTTP` for the real hostname and TLS mode. |
| `mpr-ui` shows auth controls but nothing happens | `/config-ui.yaml` is missing or the auth paths are wrong | Serve the YAML config and keep `loginPath`, `logoutPath`, and `noncePath` exact. |

## Stop Rules

- Stop if you do not know the real browser-facing origin for the deployment.
- Stop if the cookie domain or TLS mode is unknown for hosted deployment.
- Stop if the front door cannot proxy same-origin browser auth traffic.

## Change Checklist

- [ ] `TAUTH_URL` is browser-facing, not container-internal.
- [ ] Local Docker keeps browser auth on the same origin.
- [ ] The app validates `app_session` with issuer `tauth`.
- [ ] `/config-ui.yaml` exposes the exact auth keys required by `mpr-ui`.
- [ ] Protected app routes return `401` without a valid cookie.
- [ ] Authenticated browser tests can mint or inject a real `app_session`.
