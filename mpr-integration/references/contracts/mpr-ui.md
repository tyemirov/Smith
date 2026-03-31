# `mpr-ui` Integration

`mpr-ui` is the shared browser shell. It owns the CDN-loaded shell components, YAML bootstrap, and auth lifecycle events. The app owns `/config-ui.yaml`, the script load order, and the app-specific reactions to auth state.

## Purpose

- `mpr-ui` owns the shared header, footer, user control, and bootstrap contract.
- The app owns `/config-ui.yaml`.
- The app owns event handling after auth state changes.

## Inputs

- Exact literals:
  - CSS: `https://cdn.jsdelivr.net/gh/MarcoPoloResearchLab/mpr-ui@latest/mpr-ui.css`
  - bootstrap script: `https://cdn.jsdelivr.net/gh/MarcoPoloResearchLab/mpr-ui@latest/mpr-ui-config.js`
  - runtime script: `https://cdn.jsdelivr.net/gh/MarcoPoloResearchLab/mpr-ui@latest/mpr-ui.js`
  - YAML bootstrap call: `MPRUI.applyYamlConfig({ configUrl: '/config-ui.yaml' })`
  - required header attribute: `data-config-url="/config-ui.yaml"`
  - auth events: `mpr-ui:auth:authenticated`, `mpr-ui:auth:unauthenticated`
  - known bad pin: `mpr-ui@2.0.2` because `mpr-ui-config.js` is missing there
- Files to touch:
  - `internal/web/templates/layout.html`
  - `internal/web/static/app.js`
  - `cmd/server/main.go`
  - `internal/web/templates_test.go`
  - `test/web/e2e/app.spec.ts`

| Input | Consumed by | Type | Required locally | Required when hosted | Notes |
| --- | --- | --- | --- | --- | --- |
| `/config-ui.yaml` | browser + `mpr-ui` | browser-facing | yes | yes | Served by the app. |
| `tauthUrl` | `mpr-ui` | browser-facing | yes | yes | Must be reachable by the browser. |
| `googleClientId` | `mpr-ui` | browser-facing | yes | yes | Shared with TAuth. |
| `tenantId` | `mpr-ui` | browser-facing | yes | yes | Must match the TAuth tenant. |
| `loginPath` / `logoutPath` / `noncePath` | `mpr-ui` | browser-facing | yes | yes | Route names are explicit, not inferred. |

## Source Of Truth

- `internal/web/templates/layout.html`
- `internal/web/static/app.js`
- `cmd/server/main.go`
- `cmd/server/main_test.go`
- `internal/web/templates_test.go`
- `test/web/e2e/app.spec.ts`

## Decision Procedure

1. Serve `/config-ui.yaml` before integrating the shell, because `mpr-ui` depends on it.
2. Load `mpr-ui.css` in the page template.
3. Load `js-yaml` and `mpr-ui-config.js`.
4. Call `MPRUI.applyYamlConfig({ configUrl: '/config-ui.yaml' })`.
5. Only after that promise resolves, load `mpr-ui.js`.
6. Render `mpr-header` with `data-config-url="/config-ui.yaml"`.
7. Render `mpr-user` and `mpr-footer` if the page uses the shared shell.
8. In app JS, listen for `mpr-ui:auth:authenticated` and `mpr-ui:auth:unauthenticated`.
9. If the template is pinned to a version without `mpr-ui-config.js`, stop and move back to the validated CDN contract.

## Minimal Code Or Config Example

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/MarcoPoloResearchLab/mpr-ui@latest/mpr-ui.css">
<script src="https://cdn.jsdelivr.net/npm/js-yaml@4.1.0/dist/js-yaml.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/MarcoPoloResearchLab/mpr-ui@latest/mpr-ui-config.js"></script>
<script>
  MPRUI.applyYamlConfig({ configUrl: '/config-ui.yaml' }).then(function () {
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/gh/MarcoPoloResearchLab/mpr-ui@latest/mpr-ui.js';
    document.head.appendChild(script);
  });
</script>

<mpr-header data-config-url="/config-ui.yaml" brand-label="Trademark Generator" brand-href="/">
  <mpr-user slot="aux" display-mode="avatar" logout-url="/" logout-label="Sign out"></mpr-user>
</mpr-header>
<mpr-footer></mpr-footer>
```

```js
document.addEventListener('mpr-ui:auth:authenticated', function () {
  // fetch app data, show authenticated UI
});

document.addEventListener('mpr-ui:auth:unauthenticated', function () {
  // clear state, hide authenticated UI
});
```

## Expected Result

- `mpr-header` and `mpr-footer` render on page load.
- `/config-ui.yaml` loads before the runtime shell script.
- Auth-aware UI reacts only after the documented `mpr-ui:auth:*` events fire.
- The page does not depend on a broken pinned CDN version.

## Verification

```bash
# bring up the local stack
./scripts/up.sh

# inspect the page shell contract directly
curl -fsS http://localhost:8080/ | \
  rg 'mpr-header|mpr-footer|mpr-ui-config.js|mpr-ui.js|/config-ui.yaml'

# inspect the browser config used by mpr-ui
curl -fsS http://localhost:8080/config-ui.yaml

# verify template-level mpr-ui literals
go test ./internal/web -run 'TestTemplateRendering_(MprUiCDNReferences|MprUiComponents|NoInvalidMprUiAttributes)' -count=1

# verify shell rendering and auth-aware UI behavior
cd test/web && \
TRADEMARK_BASE_URL=http://localhost:8080 \
TAUTH_JWT_SIGNING_KEY="$TAUTH_JWT_SIGNING_KEY" \
LEDGER_GRPC_ADDR=localhost:50051 \
npx playwright test app.spec.ts
```

## Failure Map

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Custom elements never upgrade | `mpr-ui.js` loaded before `MPRUI.applyYamlConfig(...)` finished | Keep the documented boot order: config first, runtime second. |
| Header renders but auth controls do not work | `/config-ui.yaml` is missing or malformed | Serve the YAML config and keep the auth keys exact. |
| App never leaves unauthenticated state after login | app JS does not listen for `mpr-ui:auth:authenticated` | Add the documented event listeners and trigger authenticated data loading there. |
| Template points at a pinned version without `mpr-ui-config.js` | invalid CDN version drift | Use the validated CDN contract from the template tests. |

## Stop Rules

- Stop if `/config-ui.yaml` is not app-owned and cannot be changed.
- Stop if the page cannot load CDN assets from the documented source.
- Stop if the app wants to bypass the documented auth events and invent its own shell contract.

## Change Checklist

- [ ] `/config-ui.yaml` exists and is browser-reachable.
- [ ] `mpr-ui` scripts load in the documented order.
- [ ] `mpr-header` uses `data-config-url="/config-ui.yaml"`.
- [ ] App JS reacts to both `mpr-ui:auth:*` events.
- [ ] Template tests assert the CDN/bootstrap contract.
- [ ] Browser tests cover both shell rendering and auth-state transitions.
