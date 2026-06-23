#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin_parent="${PLUGIN_PARENT:-$repo_root/plugins}"
marketplace_path="${MARKETPLACE_PATH:-$repo_root/.agents/plugins/marketplace.json}"
marketplace_name="${MARKETPLACE_NAME:-agent-skills}"
marketplace_display_name="${MARKETPLACE_DISPLAY_NAME:-Agent Skills}"
plugin_name="${PLUGIN_NAME:-tyemirov}"
plugin_display_name="${PLUGIN_DISPLAY_NAME:-Tyemirov}"
plugin_category="${PLUGIN_CATEGORY:-Productivity}"
codex_home="${CODEX_HOME:-$HOME/.codex}"
codex_skills_dir="$codex_home/skills"
python_cmd="${PYTHON:-python3}"
dry_run=0
install_local=0
remove_direct_skills=0

usage() {
  cat <<'EOF'
Usage: sync-plugins.sh [--plugin-parent PATH] [--plugin-name NAME] [--plugin-display-name NAME] [--marketplace-path PATH] [--marketplace-name NAME] [--marketplace-display-name NAME] [--codex-home PATH] [--dry-run] [--install-local] [--remove-direct-skills]

Regenerate this repository's checked-in Codex plugin bundle and marketplace.

Defaults:
  plugin parent:      ./plugins
  plugin name:        tyemirov
  marketplace JSON:   ./.agents/plugins/marketplace.json
  marketplace name:   agent-skills
  Codex home:         $CODEX_HOME or ~/.codex

Options:
  --plugin-parent PATH      Parent directory for plugin packages.
  --plugin-name NAME        Plugin identifier and namespace prefix.
  --plugin-display-name NAME
                            Plugin display name written to plugin.json.
  --marketplace-path PATH   Marketplace JSON to create or update.
  --marketplace-name NAME   Marketplace identifier written to marketplace.json.
  --marketplace-display-name NAME
                            Marketplace display name written to marketplace.json.
  --codex-home PATH         Codex home used when removing old direct skill links.
  --dry-run                 Show planned filesystem and Codex operations.
  --install-local           Register this local checkout as a marketplace and install plugins.
  --remove-direct-skills    Remove old ~/.codex/skills symlinks that point at this repo.
  -h, --help                Show this help.
EOF
}

log() {
  printf '%s\n' "$*"
}

run() {
  if [[ "$dry_run" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
  else
    "$@"
  fi
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin-parent)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --plugin-parent"
        exit 1
      fi
      plugin_parent="$2"
      shift 2
      ;;
    --plugin-name)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --plugin-name"
        exit 1
      fi
      plugin_name="$2"
      shift 2
      ;;
    --plugin-display-name)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --plugin-display-name"
        exit 1
      fi
      plugin_display_name="$2"
      shift 2
      ;;
    --marketplace-path)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --marketplace-path"
        exit 1
      fi
      marketplace_path="$2"
      shift 2
      ;;
    --marketplace-name)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --marketplace-name"
        exit 1
      fi
      marketplace_name="$2"
      shift 2
      ;;
    --marketplace-display-name)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --marketplace-display-name"
        exit 1
      fi
      marketplace_display_name="$2"
      shift 2
      ;;
    --codex-home)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --codex-home"
        exit 1
      fi
      codex_home="$2"
      codex_skills_dir="$codex_home/skills"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --install-local)
      install_local=1
      shift
      ;;
    --remove-direct-skills)
      remove_direct_skills=1
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

skill_specs="$(cat <<'EOF'
email-cleanup
gitcommit
gitrelease
tidy-folder
EOF
)"

legacy_plugin_names=(email-cleanup git-commit git-release tidy-folder)

log "Repo root: $repo_root"
log "Plugin parent: $plugin_parent"
log "Plugin: $plugin_name"
log "Marketplace: $marketplace_path"
log "Marketplace name: $marketplace_name"

if [[ ! "$plugin_name" =~ ^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$ ]]; then
  log "Invalid plugin name: $plugin_name"
  log "Plugin names must be lower-case kebab-case and at most 64 characters."
  exit 1
fi

while IFS= read -r skill_dir; do
  [[ -z "$skill_dir" ]] && continue

  source_dir="$repo_root/$skill_dir"
  if [[ ! -d "$source_dir" || ! -f "$source_dir/SKILL.md" ]]; then
    log "Missing skill directory: $source_dir"
    exit 1
  fi
done <<< "$skill_specs"

plugin_root="$plugin_parent/$plugin_name"
skill_parent="$plugin_root/skills"
manifest_path="$plugin_root/.codex-plugin/plugin.json"

log "Syncing plugin bundle: $plugin_name"
run mkdir -p "$plugin_root/.codex-plugin" "$skill_parent"

if [[ "$dry_run" -eq 1 ]]; then
  while IFS= read -r skill_dir; do
    [[ -z "$skill_dir" ]] && continue
    log "[dry-run] sync $repo_root/$skill_dir to $skill_parent/$skill_dir"
  done <<< "$skill_specs"
  if [[ "$plugin_parent" == "$repo_root/plugins" ]]; then
    for stale_plugin_name in "${legacy_plugin_names[@]}"; do
      [[ "$stale_plugin_name" == "$plugin_name" ]] && continue
      log "[dry-run] remove stale plugin package $plugin_parent/$stale_plugin_name"
    done
  fi
  log "[dry-run] write $manifest_path"
else
  rm -rf "$skill_parent"
  mkdir -p "$plugin_root/.codex-plugin" "$skill_parent"
  while IFS= read -r skill_dir; do
    [[ -z "$skill_dir" ]] && continue
    source_dir="$repo_root/$skill_dir"
    skill_target="$skill_parent/$skill_dir"
    cp -a "$source_dir" "$skill_parent/"
    find "$skill_target" -type d -name __pycache__ -prune -exec rm -rf {} +
    find "$skill_target" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
    rm -rf "$skill_target/evals/fixtures"
  done <<< "$skill_specs"

  if [[ "$plugin_parent" == "$repo_root/plugins" ]]; then
    for stale_plugin_name in "${legacy_plugin_names[@]}"; do
      [[ "$stale_plugin_name" == "$plugin_name" ]] && continue
      rm -rf "$plugin_parent/$stale_plugin_name"
    done
  fi

  "$python_cmd" - "$manifest_path" "$plugin_name" "$plugin_display_name" "$plugin_category" <<'PY'
import json
import sys
from pathlib import Path

manifest_path, plugin_name, plugin_display_name, category = sys.argv[1:]

payload = {
    "name": plugin_name,
    "version": "0.1.0",
    "description": "Personal Codex skill bundle for Tyemirov workflows.",
    "author": {
        "name": "Tyemirov",
    },
    "skills": "./skills/",
    "interface": {
        "displayName": plugin_display_name,
        "shortDescription": "Personal Codex skill bundle",
        "longDescription": (
            "A personal Codex plugin bundle containing Email Cleanup, "
            "Git Commit, Git Release, and Tidy Folder skills."
        ),
        "developerName": "Tyemirov",
        "category": category,
        "capabilities": [
            "Interactive",
            "Write",
        ],
        "defaultPrompt": [
            "Use Tyemirov skills to commit current repo changes.",
            "Use Tyemirov skills to clean up Gmail safely.",
            "Use Tyemirov skills to organize a folder.",
        ],
    },
}

path = Path(manifest_path)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
fi

if [[ "$dry_run" -eq 1 ]]; then
  log "[dry-run] write marketplace entry for $plugin_name"
else
  "$python_cmd" - "$marketplace_path" "$marketplace_name" "$marketplace_display_name" "$plugin_name" "$plugin_category" <<'PY'
import json
import sys
from pathlib import Path

marketplace_path, marketplace_name, marketplace_display_name, plugin_name, category = sys.argv[1:]
path = Path(marketplace_path).expanduser()

entry = {
    "name": plugin_name,
    "source": {
        "source": "local",
        "path": f"./plugins/{plugin_name}",
    },
    "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    },
    "category": category,
}

payload = {
    "name": marketplace_name,
    "interface": {
        "displayName": marketplace_display_name,
    },
    "plugins": [
        entry,
    ],
}

path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
fi

if [[ "$remove_direct_skills" -eq 1 ]]; then
  log "Removing direct Codex skill symlinks that point at this repo"
  while IFS= read -r skill_dir; do
    [[ -z "$skill_dir" ]] && continue
    link_path="$codex_skills_dir/$skill_dir"
    source_path="$repo_root/$skill_dir"
    if [[ -L "$link_path" ]]; then
      current_target="$(resolve_link_target "$link_path")"
      if [[ -e "$current_target" ]]; then
        current_target="$(canonical_path "$current_target")"
      fi
      source_path="$(canonical_path "$source_path")"
      if [[ "$current_target" == "$source_path" ]]; then
        run unlink "$link_path"
      else
        log "Skipped unrelated skill link: $link_path -> $current_target"
      fi
    fi
  done <<< "$skill_specs"
fi

if [[ "$install_local" -eq 1 ]]; then
  if [[ "$dry_run" -eq 1 ]]; then
    for stale_plugin_name in "${legacy_plugin_names[@]}"; do
      [[ "$stale_plugin_name" == "$plugin_name" ]] && continue
      log "[dry-run] remove stale local plugin install $stale_plugin_name@$marketplace_name"
    done
    log "[dry-run] replace local marketplace source for $marketplace_name"
    log "[dry-run] install plugin with codex plugin add $plugin_name@$marketplace_name"
  else
    marketplace_name="$("$python_cmd" - "$marketplace_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
payload = json.loads(path.read_text(encoding="utf-8"))
print(payload["name"])
PY
)"
    marketplace_dir="$(cd -- "$(dirname -- "$marketplace_path")" && pwd)"
    marketplace_root="$(cd -- "$marketplace_dir/../.." && pwd)"
    for stale_plugin_name in "${legacy_plugin_names[@]}"; do
      [[ "$stale_plugin_name" == "$plugin_name" ]] && continue
      codex plugin remove "$stale_plugin_name@$marketplace_name" >/dev/null 2>&1 || true
    done
    codex plugin remove "$plugin_name@$marketplace_name" >/dev/null 2>&1 || true
    codex plugin marketplace remove "$marketplace_name" >/dev/null 2>&1 || true
    run codex plugin marketplace add "$marketplace_root"
    run codex plugin add "$plugin_name@$marketplace_name"
  fi
fi

log "Done."
