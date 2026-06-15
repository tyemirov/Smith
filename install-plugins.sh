#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin_parent="${PLUGIN_PARENT:-$HOME/plugins}"
marketplace_path="${MARKETPLACE_PATH:-$HOME/.agents/plugins/marketplace.json}"
codex_home="${CODEX_HOME:-$HOME/.codex}"
codex_skills_dir="$codex_home/skills"
python_cmd="${PYTHON:-python3}"
dry_run=0
install_plugins=1
remove_direct_skills=1

usage() {
  cat <<'EOF'
Usage: install-plugins.sh [--plugin-parent PATH] [--marketplace-path PATH] [--codex-home PATH] [--dry-run] [--no-install] [--keep-direct-skills]

Sync this repository's skills into four separate Codex personal plugins.

Defaults:
  plugin parent:      ~/plugins
  marketplace JSON:   ~/.agents/plugins/marketplace.json
  Codex home:         $CODEX_HOME or ~/.codex

Options:
  --plugin-parent PATH      Parent directory for plugin packages.
  --marketplace-path PATH   Marketplace JSON to create or update.
  --codex-home PATH         Codex home used when removing old direct skill links.
  --dry-run                 Show planned filesystem and Codex operations.
  --no-install              Sync plugin packages and marketplace, but skip codex plugin add.
  --keep-direct-skills      Do not remove old ~/.codex/skills symlinks.
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
    --marketplace-path)
      if [[ $# -lt 2 ]]; then
        log "Missing value for --marketplace-path"
        exit 1
      fi
      marketplace_path="$2"
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
    --no-install)
      install_plugins=0
      shift
      ;;
    --keep-direct-skills)
      remove_direct_skills=0
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

plugin_specs="$(cat <<'EOF'
email-cleanup|email-cleanup|Email Cleanup|Communication|Policy-driven Gmail cleanup workflow for Codex.|Run policy-driven Gmail cleanup at scale|Email Cleanup audits crowded Gmail accounts, protects durable mail, builds conservative bulk-cleanup policies, and uses Gmail connector tools when available.|Use Email Cleanup to audit and clean Gmail safely.
git-commit|gitcommit|Git Commit|Developer Tools|Diff-aware Git commit workflow for Codex.|Draft, commit, and push Git changes|Git Commit inspects the current worktree, stages changes, drafts a commit message with gix, commits all tracked and untracked work, and pushes when the remote target is clear.|Use Git Commit to commit and push current changes.
git-release|gitrelease|Git Release|Developer Tools|Repository release workflow for Codex.|Prepare, publish, and verify releases|Git Release prepares releases from the default branch, checks release readiness, updates changelogs, publishes tags and GitHub Releases, and verifies configured release surfaces.|Use Git Release to prepare and publish a repo release.
tidy-folder|tidy-folder|Tidy Folder|Productivity|Snapshot-first folder organization workflow for Codex.|Snapshot-first organization for explicit folders|Tidy Folder reorganizes explicitly provided folders by meaning rather than file type, preserves rollback snapshots, records move ledgers, and verifies the final tree.|Use Tidy Folder to reorganize a specified folder safely.
EOF
)"

plugin_names=()

log "Repo root: $repo_root"
log "Plugin parent: $plugin_parent"
log "Marketplace: $marketplace_path"

while IFS='|' read -r plugin_name skill_dir display_name category description short_description long_description default_prompt; do
  [[ -z "$plugin_name" ]] && continue

  source_dir="$repo_root/$skill_dir"
  if [[ ! -d "$source_dir" || ! -f "$source_dir/SKILL.md" ]]; then
    log "Missing skill directory: $source_dir"
    exit 1
  fi

  plugin_root="$plugin_parent/$plugin_name"
  skill_parent="$plugin_root/skills"
  skill_target="$skill_parent/$skill_dir"
  manifest_path="$plugin_root/.codex-plugin/plugin.json"

  log "Syncing plugin: $plugin_name"
  run mkdir -p "$plugin_root/.codex-plugin" "$skill_parent"

  if [[ "$dry_run" -eq 1 ]]; then
    log "[dry-run] replace $skill_target with $source_dir"
    log "[dry-run] write $manifest_path"
  else
    rm -rf "$skill_target"
    cp -a "$source_dir" "$skill_parent/"
    "$python_cmd" - "$manifest_path" "$plugin_name" "$display_name" "$category" "$description" "$short_description" "$long_description" "$default_prompt" <<'PY'
import json
import sys
from pathlib import Path

(
    manifest_path,
    plugin_name,
    display_name,
    category,
    description,
    short_description,
    long_description,
    default_prompt,
) = sys.argv[1:]

payload = {
    "name": plugin_name,
    "version": "0.1.0",
    "description": description,
    "author": {
        "name": "Smith",
    },
    "skills": "./skills/",
    "interface": {
        "displayName": display_name,
        "shortDescription": short_description,
        "longDescription": long_description,
        "developerName": "Smith",
        "category": category,
        "capabilities": [
            "Interactive",
            "Write",
        ],
        "defaultPrompt": [
            default_prompt,
        ],
    },
}

path = Path(manifest_path)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  fi

  if [[ "$dry_run" -eq 1 ]]; then
    log "[dry-run] add or replace marketplace entry for $plugin_name"
  else
    "$python_cmd" - "$marketplace_path" "$plugin_name" "$category" <<'PY'
import json
import sys
from pathlib import Path

marketplace_path, plugin_name, category = sys.argv[1:]
path = Path(marketplace_path).expanduser()

if path.exists():
    payload = json.loads(path.read_text(encoding="utf-8"))
else:
    payload = {
        "name": "personal",
        "interface": {
            "displayName": "Personal",
        },
        "plugins": [],
    }

payload.setdefault("name", "personal")
interface = payload.setdefault("interface", {})
if isinstance(interface, dict):
    interface.setdefault("displayName", "Personal")
plugins = payload.setdefault("plugins", [])
if not isinstance(plugins, list):
    raise SystemExit(f"{path} field 'plugins' must be an array")

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

for index, existing in enumerate(plugins):
    if isinstance(existing, dict) and existing.get("name") == plugin_name:
        plugins[index] = entry
        break
else:
    plugins.append(entry)

path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  fi

  plugin_names+=("$plugin_name")
done <<< "$plugin_specs"

if [[ "$remove_direct_skills" -eq 1 ]]; then
  log "Removing direct Codex skill symlinks that point at this repo"
  while IFS='|' read -r _plugin_name skill_dir _rest; do
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
  done <<< "$plugin_specs"
fi

if [[ "$install_plugins" -eq 1 ]]; then
  if [[ "$dry_run" -eq 1 ]]; then
    log "[dry-run] install plugins with codex plugin add <plugin>@<marketplace>"
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
    for plugin_name in "${plugin_names[@]}"; do
      run codex plugin add "$plugin_name@$marketplace_name"
    done
  fi
fi

log "Done."
