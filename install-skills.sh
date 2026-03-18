#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_dir="$codex_home/skills"
dry_run=0
force=0

usage() {
  cat <<'EOF'
Usage: install-skills.sh [--codex-home PATH] [--dry-run] [--force]

Symlink the custom skills in this repository into the Codex skills directory.

Options:
  --codex-home PATH  Override the Codex home directory. Defaults to $CODEX_HOME or ~/.codex.
  --dry-run          Show what would change without modifying the filesystem.
  --force            Replace existing skill paths after moving them into a backup directory.
  -h, --help         Show this help.
EOF
}

log() {
  printf '%s\n' "$*"
}

status_text() {
  if [[ "$dry_run" -eq 1 ]]; then
    printf '%s' "$2"
  else
    printf '%s' "$1"
  fi
}

run() {
  if [[ "$dry_run" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

backup_root=""

ensure_backup_root() {
  if [[ -n "$backup_root" ]]; then
    return 0
  fi

  backup_root="$skills_dir/.custom-skills-backup-$(date +%Y%m%d-%H%M%S)"
  run mkdir -p "$backup_root"
}

backup_path() {
  local path_name="$1"
  ensure_backup_root
  run mv "$path_name" "$backup_root/"
  log "$(status_text "Moved existing path" "Would move existing path") to $backup_root/$(basename "$path_name")"
}

canonical_path() {
  local path_name="$1"
  if command -v realpath >/dev/null 2>&1; then
    realpath "$path_name"
  else
    readlink -f "$path_name"
  fi
}

resolve_link_target() {
  local link_path="$1"
  local raw_target
  local link_dir

  raw_target="$(readlink "$link_path")"
  if [[ "$raw_target" == /* ]]; then
    printf '%s\n' "$raw_target"
    return 0
  fi

  link_dir="$(cd -- "$(dirname -- "$link_path")" && pwd)"
  printf '%s/%s\n' "$link_dir" "$raw_target"
}

skill_dirs=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --codex-home)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --codex-home"
        exit 1
      fi
      codex_home="$2"
      skills_dir="$codex_home/skills"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --force)
      force=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

while IFS= read -r -d '' skill_dir; do
  skill_dirs+=("$skill_dir")
done < <(find "$repo_root" -mindepth 1 -maxdepth 1 -type d ! -name '.*' -exec test -f '{}/SKILL.md' ';' -print0 | sort -z)

if [[ "${#skill_dirs[@]}" -eq 0 ]]; then
  log "No skill directories found under $repo_root"
  exit 1
fi

run mkdir -p "$skills_dir"

log "Repo root: $repo_root"
log "Codex home: $codex_home"
log "Skills dir: $skills_dir"

linked_count=0
skipped_count=0

for source_dir in "${skill_dirs[@]}"; do
  skill_name="$(basename "$source_dir")"
  target_path="$skills_dir/$skill_name"
  source_path="$(canonical_path "$source_dir")"

  if [[ -L "$target_path" ]]; then
    current_target="$(resolve_link_target "$target_path")"
    if [[ -e "$current_target" ]]; then
      current_target="$(canonical_path "$current_target")"
    fi
    if [[ "$current_target" == "$source_path" ]]; then
      log "Already linked: $skill_name"
      skipped_count=$((skipped_count + 1))
      continue
    fi

    if [[ "$force" -ne 1 ]]; then
      log "Conflict: $target_path points to $current_target"
      log "Re-run with --force to replace it."
      exit 1
    fi

    backup_path "$target_path"
  elif [[ -e "$target_path" ]]; then
    if [[ "$force" -ne 1 ]]; then
      log "Conflict: $target_path already exists"
      log "Re-run with --force to move it aside into a backup directory."
      exit 1
    fi

    backup_path "$target_path"
  fi

  run ln -s "$source_path" "$target_path"
  log "$(status_text "Linked" "Would link"): $target_path -> $source_path"
  linked_count=$((linked_count + 1))
done

log "Done. $(status_text "Linked" "Would link") $linked_count skill(s); skipped $skipped_count already-correct link(s)."

if [[ -n "$backup_root" ]]; then
  log "$(status_text "Backup directory" "Would use backup directory"): $backup_root"
fi

if [[ -d "$repo_root/mediaops" ]]; then
  log "Note: mediaops builds its runtime from MEDIAOPS_REPO when no cached binary is present."
fi
