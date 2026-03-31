#!/usr/bin/env bash
set -euo pipefail

workdir="${MPR_INTEGRATION_WORKDIR:?MPR_INTEGRATION_WORKDIR is required}"

rg -n '^tauthUrl: http://localhost:8080$' "$workdir/config-ui.yaml"
rg -n '^tenantId: trademark$' "$workdir/config-ui.yaml"
rg -n '^loginPath: /auth/google$' "$workdir/config-ui.yaml"
rg -n '^logoutPath: /auth/logout$' "$workdir/config-ui.yaml"
rg -n '^noncePath: /auth/nonce$' "$workdir/config-ui.yaml"

if rg -n 'tauth:8443' "$workdir"; then
  echo "found container-internal hostname in browser-facing files" >&2
  exit 1
fi

rg -n 'data-config-url="/config-ui.yaml"' "$workdir/index.html"
rg -n 'src="/tauth.js"' "$workdir/index.html"
