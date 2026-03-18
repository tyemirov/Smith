#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
config_dir="${HOME}/.config/mediaops"
target="${config_dir}/.env"
template="${script_dir}/../assets/mediaops.env.example"

mkdir -p "${config_dir}"

if [[ -e "${target}" ]]; then
  echo "Refusing to overwrite existing file: ${target}" >&2
  exit 1
fi

cp "${template}" "${target}"
chmod 600 "${target}"

printf 'Installed mediaops dotenv template at %s\n' "${target}"
