#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${script_dir}/.." && pwd)"
bundled_bin="${skill_root}/.cache/bin/mediaops"
default_repo="${HOME}/Development/MarcoPoloResearchLab/Sheet2Tube"
force_build="${MEDIAOPS_FORCE_BUILD:-0}"
prefer_repo="${MEDIAOPS_PREFER_REPO:-0}"
build_output="${MEDIAOPS_BUILD_OUTPUT:-}"
print_repo="${MEDIAOPS_PRINT_REPO:-0}"

resolve_repo_root() {
  declare -a candidates=()

  if [[ -n "${MEDIAOPS_REPO:-}" ]]; then
    candidates+=("${MEDIAOPS_REPO}")
  fi

  if [[ -n "${PWD:-}" ]]; then
    candidates+=("${PWD}")
  fi

  candidates+=("$(cd "${script_dir}/../../.." && pwd)")
  candidates+=("${default_repo}")

  local repo_candidate=""
  for repo_candidate in "${candidates[@]}"; do
    if [[ -f "${repo_candidate}/go.mod" && -f "${repo_candidate}/main.go" && -f "${repo_candidate}/cmd/root.go" ]]; then
      printf '%s\n' "${repo_candidate}"
      return 0
    fi
  done

  return 1
}

if [[ -n "${MEDIAOPS_REPO:-}" ]]; then
  prefer_repo=1
fi

if [[ "${print_repo}" != "1" && "${prefer_repo}" != "1" && -z "${build_output}" && -x "${bundled_bin}" ]]; then
  printf '%s\n' "${bundled_bin}"
  exit 0
fi

repo=""
if repo="$(resolve_repo_root 2>/dev/null)"; then
  :
else
  repo=""
fi

if [[ "${print_repo}" == "1" ]]; then
  if [[ -n "${repo}" ]]; then
    printf '%s\n' "${repo}"
    exit 0
  fi
  echo "mediaops repo not found. Set MEDIAOPS_REPO to the repo root containing go.mod, main.go, and cmd/root.go." >&2
  exit 1
fi

if [[ -z "${repo}" ]]; then
  if [[ -x "${bundled_bin}" ]]; then
    printf '%s\n' "${bundled_bin}"
    exit 0
  fi
  echo "mediaops binary not found. Install a bundled skill binary with scripts/install_skill.sh, or set MEDIAOPS_REPO to the repo root containing go.mod, main.go, and cmd/root.go." >&2
  exit 1
fi

bin=""
if [[ -n "${build_output}" ]]; then
  bin="${build_output}"
  mkdir -p "$(dirname "${bin}")"
else
  runtime_build_dir="$(mktemp -d "${TMPDIR:-/tmp}/mediaops-runtime.XXXXXX")"
  bin="${runtime_build_dir}/mediaops"
fi

needs_build=0

if [[ "${force_build}" == "1" ]]; then
  needs_build=1
elif [[ ! -x "${bin}" ]]; then
  needs_build=1
else
  if find "${repo}/cmd" "${repo}/pkg" "${repo}/internal" -type f -name '*.go' -newer "${bin}" -print -quit 2>/dev/null | grep -q .; then
    needs_build=1
  fi
  if [[ -f "${repo}/main.go" && "${repo}/main.go" -nt "${bin}" ]]; then
    needs_build=1
  fi
  if [[ -f "${repo}/go.mod" && "${repo}/go.mod" -nt "${bin}" ]]; then
    needs_build=1
  fi
  if [[ -f "${repo}/go.sum" && "${repo}/go.sum" -nt "${bin}" ]]; then
    needs_build=1
  fi
fi

if [[ "${needs_build}" == "1" ]]; then
  echo "Building mediaops binary..." >&2
  (cd "${repo}" && go build -o "${bin}" .)
fi

printf '%s\n' "${bin}"
