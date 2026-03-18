#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${script_dir}/.." && pwd)"
repo_root=""
if repo_root="$(MEDIAOPS_PRINT_REPO=1 MEDIAOPS_PREFER_REPO=1 "${script_dir}/ensure_mediaops.sh" 2>/dev/null)"; then
  :
else
  repo_root=""
fi
repo_skill_root=""

if [[ -n "${repo_root}" && -d "${repo_root}/skills/mediaops" ]]; then
  repo_skill_root="$(cd "${repo_root}/skills/mediaops" && pwd)"
fi

if [[ -n "${repo_skill_root}" && "${skill_root}" == "${repo_skill_root}" ]]; then
  "${script_dir}/install_skill.sh" >/dev/null
  printf 'mediaops installed skill refreshed successfully at %s\n' "${CODEX_HOME:-${HOME}/.codex}/skills/mediaops/bin/mediaops"
  exit 0
fi

if [[ -n "${repo_root}" ]]; then
  mkdir -p "${skill_root}/.cache/bin"
  MEDIAOPS_REPO="${repo_root}" \
  MEDIAOPS_PREFER_REPO=1 \
  MEDIAOPS_FORCE_BUILD=1 \
  MEDIAOPS_BUILD_OUTPUT="${skill_root}/.cache/bin/mediaops" \
    "${script_dir}/ensure_mediaops.sh" >/dev/null
  chmod 755 "${skill_root}/.cache/bin/mediaops"
  rm -f "${repo_root}/bin/mediaops"
  rmdir "${repo_root}/bin" 2>/dev/null || true
  printf 'mediaops runtime refreshed successfully for %s using cache %s\n' "${skill_root}/bin/mediaops" "${skill_root}/.cache/bin/mediaops"
  exit 0
fi

if [[ -x "${skill_root}/.cache/bin/mediaops" ]]; then
  printf 'mediaops cached runtime already available at %s\n' "${skill_root}/.cache/bin/mediaops"
  exit 0
fi

echo "mediaops binary not found. Install a bundled skill binary with scripts/install_skill.sh, or set MEDIAOPS_REPO to the repo root containing go.mod, main.go, and cmd/root.go." >&2
exit 1
