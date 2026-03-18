#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin="$("${script_dir}/ensure_mediaops.sh")"
runtime_root="$(cd "$(dirname "${bin}")/.." && pwd)"

if [[ -z "${MEDIAOPS_REPO:-}" && -f "${runtime_root}/go.mod" && -f "${runtime_root}/main.go" && -f "${runtime_root}/cmd/root.go" ]]; then
  export MEDIAOPS_REPO="${runtime_root}"
fi

if [[ "${bin}" == "${TMPDIR:-/tmp}"/mediaops-runtime.*/* ]]; then
  "${bin}" "$@"
  exit_code=$?
  rm -f "${bin}"
  rmdir "$(dirname "${bin}")" 2>/dev/null || true
  exit "${exit_code}"
fi

exec "${bin}" "$@"
