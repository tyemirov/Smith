#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin_parent="${PLUGIN_PARENT:-$repo_root/plugins}"
marketplace_path="${MARKETPLACE_PATH:-$repo_root/.agents/plugins/marketplace.json}"
marketplace_name="${MARKETPLACE_NAME:-agent-skills}"
marketplace_display_name="${MARKETPLACE_DISPLAY_NAME:-Agent Skills}"
codex_home="${CODEX_HOME:-$HOME/.codex}"
codex_skills_dir="$codex_home/skills"
python_cmd="${PYTHON:-python3}"
dry_run=0
install_local=0
remove_direct_skills=0

usage() {
  cat <<'EOF'
Usage: sync-plugins.sh [--plugin-parent PATH] [--marketplace-path PATH] [--marketplace-name NAME] [--marketplace-display-name NAME] [--codex-home PATH] [--dry-run] [--install-local] [--remove-direct-skills]

Regenerate this repository's checked-in Codex plugin packages and marketplace.

Defaults:
  plugin parent:      ./plugins
  marketplace JSON:   ./.agents/plugins/marketplace.json
  marketplace name:   agent-skills
  Codex home:         $CODEX_HOME or ~/.codex

Options:
  --plugin-parent PATH      Parent directory for plugin packages.
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
log "Marketplace name: $marketplace_name"

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
    find "$skill_target" -type d -name __pycache__ -prune -exec rm -rf {} +
    find "$skill_target" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
    rm -rf "$skill_target/evals/fixtures"
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
    "$python_cmd" - "$marketplace_path" "$marketplace_name" "$marketplace_display_name" "$plugin_name" "$category" <<'PY'
import json
import sys
from pathlib import Path

marketplace_path, marketplace_name, marketplace_display_name, plugin_name, category = sys.argv[1:]
path = Path(marketplace_path).expanduser()

if path.exists():
    payload = json.loads(path.read_text(encoding="utf-8"))
else:
    payload = {
        "name": marketplace_name,
        "interface": {
            "displayName": marketplace_display_name,
        },
        "plugins": [],
    }

payload["name"] = marketplace_name
interface = payload.setdefault("interface", {})
if isinstance(interface, dict):
    interface["displayName"] = marketplace_display_name
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

if [[ "$install_local" -eq 1 ]]; then
  if [[ "$dry_run" -eq 1 ]]; then
    log "[dry-run] register marketplace root and install plugins with codex plugin add <plugin>@<marketplace>"
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
    if ! codex plugin marketplace list | awk '{print $1}' | grep -Fxq "$marketplace_name"; then
      run codex plugin marketplace add "$marketplace_root"
    fi
    for plugin_name in "${plugin_names[@]}"; do
      run codex plugin add "$plugin_name@$marketplace_name"
    done
  fi
fi

log "Done."
