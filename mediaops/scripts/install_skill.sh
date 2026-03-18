#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${script_dir}/.." && pwd)"
default_dest="${CODEX_HOME:-${HOME}/.codex}/skills/mediaops"
dest="${1:-${default_dest}}"

repo_root="$(MEDIAOPS_PRINT_REPO=1 MEDIAOPS_PREFER_REPO=1 "${script_dir}/ensure_mediaops.sh")"

mkdir -p "${dest}"

source_root="$(cd "${skill_root}" && pwd)"
dest_root="$(cd "${dest}" && pwd)"

if [[ "${source_root}" != "${dest_root}" ]]; then
  rsync -a --delete --exclude '.cache/' "${skill_root}/" "${dest}/"
fi

mkdir -p "${dest}/.cache/bin"
MEDIAOPS_REPO="${repo_root}" \
MEDIAOPS_PREFER_REPO=1 \
MEDIAOPS_FORCE_BUILD=1 \
MEDIAOPS_BUILD_OUTPUT="${dest}/.cache/bin/mediaops" \
  "${script_dir}/ensure_mediaops.sh" >/dev/null
chmod 755 "${dest}/.cache/bin/mediaops"
rm -f "${repo_root}/bin/mediaops"
rmdir "${repo_root}/bin" 2>/dev/null || true

env_source=""
if [[ -n "${MEDIAOPS_ENV_FILE:-}" && -f "${MEDIAOPS_ENV_FILE}" ]]; then
  env_source="${MEDIAOPS_ENV_FILE}"
elif [[ -f "${repo_root}/.env" ]]; then
  env_source="${repo_root}/.env"
elif [[ -f "${HOME}/.config/mediaops/.env" ]]; then
  env_source="${HOME}/.config/mediaops/.env"
fi

if [[ -n "${env_source}" ]]; then
  cp "${env_source}" "${dest}/.env"
  chmod 600 "${dest}/.env"
fi

printf 'Installed mediaops skill to %s\n' "${dest}"
printf 'Runtime entrypoint: %s\n' "${dest}/bin/mediaops"
printf 'Cached binary path: %s\n' "${dest}/.cache/bin/mediaops"
if [[ -n "${env_source}" ]]; then
  printf 'Bundled env file: %s/.env\n' "${dest}"
fi
