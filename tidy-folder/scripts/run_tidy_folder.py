#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
SCANNER = ROOT / "semantic_scan.py"
SNAPSHOT_DIRNAME = ".tidy-folder-snapshots"
SNAPSHOT_PRUNE = {".git", SNAPSHOT_DIRNAME}
ACTIVE_RUN_LOCK_FILENAME = "active-run.lock.json"
DEFAULT_LEASE_SECONDS = int(os.environ.get("TIDY_FOLDER_RUN_LEASE_SECONDS", "900"))


def resolve_uv_binary() -> str | None:
    for candidate in (os.environ.get("UV"), "/opt/homebrew/bin/uv", shutil.which("uv")):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def display_path(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    if rel == Path("."):
        return "."
    return f"./{rel.as_posix()}"


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_timestamp(value: datetime | None = None) -> str:
    current = value or utc_now()
    return current.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        return None


def default_run_owner() -> str:
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    host = socket.gethostname() or "localhost"
    return f"{user}@{host}:{os.getpid()}"


def snapshot_inventory(
    root: Path,
    snapshot_dir: Path,
    *,
    heartbeat: Callable[[], None] | None = None,
) -> dict[str, str]:
    tree_lines = ["."]
    file_lines: list[str] = []
    metadata_lines: list[str] = []
    item_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if d not in SNAPSHOT_PRUNE)
        filenames = sorted(filenames)
        item_count += 1
        if heartbeat is not None and item_count % 200 == 0:
            heartbeat()

        if current != root:
            tree_lines.append(display_path(current, root))

        for filename in filenames:
            file_path = current / filename
            rel = display_path(file_path, root)
            tree_lines.append(rel)
            file_lines.append(rel)
            stat_result = file_path.stat()
            metadata_lines.append(
                f"{rel}|{stat_result.st_size}|{int(stat_result.st_mtime)}|{int(stat_result.st_atime)}"
            )
            item_count += 1
            if heartbeat is not None and item_count % 200 == 0:
                heartbeat()

    tree_lines = sorted(set(tree_lines))
    file_lines = sorted(file_lines)
    metadata_lines = sorted(metadata_lines)

    tree_path = snapshot_dir / "tree.txt"
    files_path = snapshot_dir / "files.txt"
    metadata_path = snapshot_dir / "file-metadata.tsv"
    write_lines(tree_path, tree_lines)
    write_lines(files_path, file_lines)
    write_lines(metadata_path, metadata_lines)
    write_lines(snapshot_dir / ".tidy-folder-pre-run-files.txt", file_lines)
    write_lines(snapshot_dir / ".tidy-folder-pre-run-metadata.tsv", metadata_lines)

    return {
        "tree_path": str(tree_path),
        "files_path": str(files_path),
        "metadata_path": str(metadata_path),
    }


def run_manifest(
    target: Path,
    *,
    uv_binary: str,
    cache_file: Path | None,
    include_ignored: bool,
    vision: bool,
    vision_provider: str,
    vision_model: str,
    heartbeat: Callable[[], None] | None = None,
    heartbeat_interval_seconds: float = 30.0,
) -> dict[str, Any]:
    args = [
        uv_binary,
        "run",
        str(SCANNER),
        str(target),
        "--manifest",
        "--autopilot",
    ]
    if cache_file is not None:
        args.extend(["--cache-file", str(cache_file)])
    if include_ignored:
        args.append("--include-ignored")
    if vision:
        args.extend(["--vision", "--vision-provider", vision_provider])
        if vision_model:
            args.extend(["--vision-model", vision_model])

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        if heartbeat is None:
            stdout, stderr = proc.communicate()
        else:
            while True:
                try:
                    stdout, stderr = proc.communicate(timeout=heartbeat_interval_seconds)
                    break
                except subprocess.TimeoutExpired:
                    heartbeat()
    except Exception:
        proc.kill()
        proc.communicate()
        raise
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, args, output=stdout, stderr=stderr)
    return json.loads(stdout)


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def preserved_relative_suffix(entry: dict[str, Any], source: Path, root: Path) -> Path | None:
    attribution = entry.get("attribution", {})
    hints = attribution.get("taxonomy_hints", [])
    destination = entry.get("proposed_destination")
    if not isinstance(hints, list) or not destination:
        return None

    try:
        relative_source = source.relative_to(root)
    except ValueError:
        return None

    for hint in hints:
        if not isinstance(hint, dict):
            continue
        if hint.get("source") != "project_markers":
            continue
        if hint.get("home") != destination:
            continue
        scope = str(hint.get("scope") or "").strip()
        if not scope or scope == ".":
            return None
        scope_parts = tuple(part for part in Path(scope).parts if part not in {"."})
        if not scope_parts:
            return None
        if relative_source.parts[: len(scope_parts)] != scope_parts:
            continue
        suffix_parts = relative_source.parts[len(scope_parts) :]
        if not suffix_parts:
            return Path(source.name)
        return Path(*suffix_parts)
    return None


def draft_actions_from_manifest(manifest: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for entry in manifest.get("entries", []):
        if not entry.get("routable"):
            continue
        destination = entry.get("proposed_destination")
        if not destination:
            continue

        source = Path(entry["source_path"])
        destination_dir = root / destination
        relative_suffix = preserved_relative_suffix(entry, source, root)
        destination_path = destination_dir / (relative_suffix or Path(source.name))
        actions.append(
            {
                "source_path": str(source),
                "destination_dir": str(destination_dir),
                "destination_path": str(destination_path),
                "relative_suffix": str(relative_suffix) if relative_suffix is not None else "",
                "confidence_score": entry.get("confidence_score"),
                "rationale": entry.get("rationale"),
            }
        )
    return actions


def approved_actions(manifest: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    # Compatibility alias for older callers; draft_actions_from_manifest is the primary name now.
    return draft_actions_from_manifest(manifest, root)


def execute_actions(
    actions: list[dict[str, Any]],
    *,
    heartbeat: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    for action in actions:
        if heartbeat is not None:
            heartbeat()
        source = Path(action["source_path"])
        destination = Path(action["destination_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        final_destination = unique_destination(destination)
        if source.resolve() == final_destination.resolve():
            deltas.append(
                {
                    "source_path": str(source),
                    "destination_path": str(final_destination),
                    "status": "noop",
                }
            )
            continue
        shutil.move(str(source), str(final_destination))
        deltas.append(
            {
                "source_path": str(source),
                "destination_path": str(final_destination),
                "status": "moved",
            }
        )
    return deltas


def prune_empty_directories(
    root: Path,
    *,
    heartbeat: Callable[[], None] | None = None,
) -> list[str]:
    removed: list[str] = []
    visited = 0
    for dirpath, dirnames, _filenames in os.walk(root, topdown=False):
        visited += 1
        if heartbeat is not None and visited % 100 == 0:
            heartbeat()
        current = Path(dirpath)
        if current == root:
            continue
        dirnames[:] = [d for d in dirnames if d not in SNAPSHOT_PRUNE]
        if current.name in SNAPSHOT_PRUNE:
            continue
        try:
            entries = [entry for entry in current.iterdir() if entry.name not in SNAPSHOT_PRUNE]
        except FileNotFoundError:
            continue
        if entries:
            continue
        current.rmdir()
        removed.append(display_path(current, root))
    return sorted(removed)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_handoff(
    handoff_dir: Path,
    filename: str,
    payload: dict[str, Any],
) -> str:
    path = handoff_dir / filename
    write_json(path, payload)
    return str(path)


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def build_run_lock_payload(
    *,
    run_id: str,
    target: Path,
    snapshot_dir: Path,
    owner: str,
    phase: str,
    started_at: str | None = None,
    takeover_of: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "run_id": run_id,
        "target_folder": str(target),
        "snapshot_path": str(snapshot_dir),
        "owner": owner,
        "phase": phase,
        "started_at": started_at or utc_timestamp(),
        "updated_at": utc_timestamp(),
        "pid": os.getpid(),
    }
    if takeover_of:
        payload["takeover_of"] = {
            "run_id": takeover_of.get("run_id"),
            "owner": takeover_of.get("owner"),
            "updated_at": takeover_of.get("updated_at"),
            "phase": takeover_of.get("phase"),
        }
    return payload


def lock_is_owned_by(lock_path: Path, run_id: str, owner: str) -> bool:
    payload = load_json(lock_path)
    if not isinstance(payload, dict):
        return False
    return payload.get("run_id") == run_id and payload.get("owner") == owner


def acquire_run_lock(
    *,
    lock_path: Path,
    run_id: str,
    target: Path,
    snapshot_dir: Path,
    owner: str,
    lease_seconds: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    existing = load_json(lock_path)
    if not isinstance(existing, dict):
        payload = build_run_lock_payload(
            run_id=run_id,
            target=target,
            snapshot_dir=snapshot_dir,
            owner=owner,
            phase="preflight",
        )
        write_json(lock_path, payload)
        return payload, None, None

    updated_at = parse_utc_timestamp(str(existing.get("updated_at") or ""))
    age_seconds = None
    if updated_at is not None:
        age_seconds = max((utc_now() - updated_at).total_seconds(), 0.0)
    stale = updated_at is None or age_seconds is None or age_seconds > lease_seconds

    if not stale:
        failure = {
            "code": "preflight_conflicting_run_lock",
            "message": "Another tidy-folder run lock is currently active for this target.",
            "run_lock_path": str(lock_path),
            "existing_run_id": existing.get("run_id"),
            "existing_owner": existing.get("owner"),
            "existing_phase": existing.get("phase"),
            "updated_at": existing.get("updated_at"),
            "lease_seconds": lease_seconds,
        }
        if age_seconds is not None:
            failure["age_seconds"] = round(age_seconds, 2)
        return None, failure, None

    takeover_path = snapshot_dir / "lock-takeover.json"
    payload = build_run_lock_payload(
        run_id=run_id,
        target=target,
        snapshot_dir=snapshot_dir,
        owner=owner,
        phase="preflight",
        takeover_of=existing,
    )
    write_json(
        takeover_path,
        {
            "code": "stale_run_lock_takeover",
            "message": "A stale tidy-folder run lock was replaced by the current run.",
            "previous_lock": existing,
            "new_lock": payload,
            "lease_seconds": lease_seconds,
        },
    )
    write_json(lock_path, payload)
    return payload, None, str(takeover_path)


def refresh_run_lock(
    *,
    lock_path: Path,
    run_id: str,
    owner: str,
    phase: str,
) -> dict[str, Any] | None:
    existing = load_json(lock_path)
    if not isinstance(existing, dict):
        return None
    if existing.get("run_id") != run_id or existing.get("owner") != owner:
        return None
    payload = dict(existing)
    payload["phase"] = phase
    payload["updated_at"] = utc_timestamp()
    write_json(lock_path, payload)
    return payload


def release_run_lock(
    *,
    lock_path: Path,
    run_id: str,
    owner: str,
    snapshot_dir: Path,
    final_status: str,
) -> bool:
    existing = load_json(lock_path)
    if not isinstance(existing, dict):
        return False
    if existing.get("run_id") != run_id or existing.get("owner") != owner:
        return False
    write_json(
        snapshot_dir / "run-lock-final.json",
        {
            "released_at": utc_timestamp(),
            "final_status": final_status,
            "lock": existing,
        },
    )
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build tidy-folder draft artifacts, run lock/lease state, and optional draft execution utilities.")
    parser.add_argument("target", help="Folder to organize")
    parser.add_argument("--include-ignored", action="store_true", help="Pass --include-ignored through to semantic_scan.py")
    parser.add_argument("--vision", action="store_true", help="Enable vision mode when building the manifest")
    parser.add_argument("--vision-provider", default="hf", choices=("hf", "openai"))
    parser.add_argument("--vision-model", default="")
    parser.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS, help="Stale-lease threshold for the active run lock")
    parser.add_argument("--run-owner", default="", help="Optional explicit owner identifier for the active run lock")
    parser.add_argument("--execute", action="store_true", help="Apply the current snapshot's draft actions under the caller's authority after helper blockers clear")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    target = Path(args.target).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print(f"error: target folder does not exist: {target}", file=sys.stderr)
        return 2

    snapshot_id = utc_now().strftime("%Y%m%d_%H%M%S_%f")
    snapshot_dir = target / SNAPSHOT_DIRNAME / snapshot_id
    handoff_dir = snapshot_dir / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    cache_file = target / SNAPSHOT_DIRNAME / "semantic-evidence-cache.json"
    lock_path = target / SNAPSHOT_DIRNAME / ACTIVE_RUN_LOCK_FILENAME
    run_owner = args.run_owner.strip() or default_run_owner()
    uv_binary = resolve_uv_binary()
    report_path = snapshot_dir / "run-report.json"
    draft_actions_path = snapshot_dir / "draft-actions.json"
    legacy_actions_path = snapshot_dir / "approved-actions.json"
    supervisor_path = write_handoff(
        handoff_dir,
        "00-supervisor.json",
        {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "snapshot_path": str(snapshot_dir),
            "run_lock_path": str(lock_path),
            "lock_owner": run_owner,
            "phase_history": [],
        },
    )
    handoff_paths = {
        "supervisor": supervisor_path,
    }
    phase_history: list[dict[str, Any]] = []
    inventory: dict[str, str] = {}
    lock_payload: dict[str, Any] | None = None
    lock_takeover_path: str | None = None
    lock_acquired = False
    last_heartbeat_at: str | None = None
    heartbeat_phase: str | None = None
    heartbeat_interval_seconds = max(1.0, min(30.0, args.lease_seconds / 3 if args.lease_seconds > 0 else 30.0))

    def write_supervisor_state() -> None:
        write_json(
            Path(supervisor_path),
            {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "snapshot_path": str(snapshot_dir),
                "run_lock_path": str(lock_path),
                "lock_owner": run_owner,
                "lock_takeover_artifact": lock_takeover_path,
                "last_heartbeat_at": last_heartbeat_at,
                "heartbeat_phase": heartbeat_phase,
                "phase_history": phase_history,
            },
        )

    def heartbeat_run_lock(phase: str) -> None:
        nonlocal lock_payload, last_heartbeat_at, heartbeat_phase
        if not lock_acquired:
            return
        refreshed = refresh_run_lock(
            lock_path=lock_path,
            run_id=snapshot_id,
            owner=run_owner,
            phase=phase,
        )
        if refreshed is None:
            return
        lock_payload = refreshed
        heartbeat_phase = phase
        last_heartbeat_at = refreshed.get("updated_at")
        write_supervisor_state()

    def write_action_artifacts(draft_actions: list[dict[str, Any]], helper_ready: bool) -> None:
        write_json(
            draft_actions_path,
            {
                "draft_actions": draft_actions,
                "requires_agent_review": True,
                "helper_ready_for_agent_review": helper_ready,
            },
        )
        write_json(
            legacy_actions_path,
            {
                "approved_actions": draft_actions if helper_ready else [],
                "deprecated": True,
                "replacement_artifact": str(draft_actions_path),
            },
        )

    def finalize_report(report: dict[str, Any], return_code: int) -> int:
        nonlocal lock_acquired
        final_status = str(report.get("helper_execution_status") or report.get("executor_status") or "completed")
        report["run_lock_path"] = str(lock_path)
        report["run_lock_owner"] = run_owner
        report["lock_takeover_artifact"] = lock_takeover_path
        report["lease_seconds"] = args.lease_seconds
        if lock_acquired:
            report["run_lock_released"] = release_run_lock(
                lock_path=lock_path,
                run_id=snapshot_id,
                owner=run_owner,
                snapshot_dir=snapshot_dir,
                final_status=final_status,
            )
            lock_acquired = False
        else:
            report["run_lock_released"] = False
        write_json(report_path, report)
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return return_code

    def record_phase(phase: str, status: str, **details: Any) -> None:
        nonlocal lock_payload, last_heartbeat_at, heartbeat_phase
        phase_history.append({"phase": phase, "status": status, **details})
        if lock_acquired:
            refreshed = refresh_run_lock(
                lock_path=lock_path,
                run_id=snapshot_id,
                owner=run_owner,
                phase=phase,
            )
            if refreshed is not None:
                lock_payload = refreshed
        last_heartbeat_at = lock_payload.get("updated_at") if lock_payload else last_heartbeat_at
        heartbeat_phase = phase
        write_supervisor_state()
    try:
        lock_payload, lock_failure, lock_takeover_path = acquire_run_lock(
            lock_path=lock_path,
            run_id=snapshot_id,
            target=target,
            snapshot_dir=snapshot_dir,
            owner=run_owner,
            lease_seconds=args.lease_seconds,
        )
        lock_acquired = lock_payload is not None and lock_failure is None
        if lock_payload is not None:
            last_heartbeat_at = lock_payload.get("updated_at")
            heartbeat_phase = lock_payload.get("phase")
            write_supervisor_state()

        preflight = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "snapshot_path": str(snapshot_dir),
            "manifest_path": None,
            "pass": 0,
            "low_confidence_count": None,
            "active_gate_failures": [],
            "draft_actions": [],
            "checklist": {
                "target_exists": True,
                "uv_available": bool(uv_binary),
                "scanner_available": SCANNER.exists(),
                "snapshot_created": True,
                "evidence_cache_path": str(cache_file),
                "run_lock_path": str(lock_path),
                "run_lock_owner": run_owner,
                "run_lock_acquired": lock_acquired,
                "lease_seconds": args.lease_seconds,
                "lock_takeover_artifact": lock_takeover_path,
            },
        }
        handoff_paths["preflight"] = write_handoff(handoff_dir, "01-preflight.json", preflight)

        if lock_failure is not None:
            preflight["active_gate_failures"] = [lock_failure]
            write_json(Path(handoff_paths["preflight"]), preflight)
            record_phase("preflight", "blocked", active_gate_failures=[lock_failure])
            write_action_artifacts([], False)
            report = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "snapshot_path": str(snapshot_dir),
                "inventory": inventory,
                "manifest_path": None,
                "draft_manifest_path": None,
                "handoff_paths": handoff_paths,
                "draft_actions_path": str(draft_actions_path),
                "approved_actions_path": str(legacy_actions_path),
                "low_confidence_count": None,
                "active_gate_failures": [lock_failure],
                "draft_review_state": "blocked_by_run_lock",
                "helper_ready_for_agent_review": False,
                "requires_agent_review": True,
                "execution_ready": False,
                "executor_status": "blocked",
                "helper_execution_status": "blocked",
                "cache_stats": {},
                "phase_history": phase_history,
                "post_move_manifest_path": None,
                "post_move_summary": None,
                "empty_dirs_removed": [],
            }
            return finalize_report(report, 2)

        inventory = snapshot_inventory(target, snapshot_dir, heartbeat=lambda: heartbeat_run_lock("preflight"))

        preflight_failures: list[dict[str, Any]] = []
        if uv_binary is None:
            preflight_failures.append(
                {
                    "code": "preflight_missing_uv",
                    "message": "uv is required to run semantic_scan.py.",
                }
            )
        if not SCANNER.exists():
            preflight_failures.append(
                {
                    "code": "preflight_missing_scanner",
                    "message": "semantic_scan.py is missing from the tidy-folder skill.",
                }
            )
        if preflight_failures:
            preflight["active_gate_failures"] = preflight_failures
            write_json(Path(handoff_paths["preflight"]), preflight)
            record_phase("preflight", "blocked", active_gate_failures=preflight_failures)
            write_action_artifacts([], False)
            report = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "snapshot_path": str(snapshot_dir),
                "inventory": inventory,
                "manifest_path": None,
                "draft_manifest_path": None,
                "handoff_paths": handoff_paths,
                "draft_actions_path": str(draft_actions_path),
                "approved_actions_path": str(legacy_actions_path),
                "low_confidence_count": None,
                "active_gate_failures": preflight_failures,
                "draft_review_state": "blocked_preflight",
                "helper_ready_for_agent_review": False,
                "requires_agent_review": True,
                "execution_ready": False,
                "executor_status": "blocked",
                "helper_execution_status": "blocked",
                "cache_stats": {},
                "phase_history": phase_history,
                "post_move_manifest_path": None,
                "post_move_summary": None,
                "empty_dirs_removed": [],
            }
            return finalize_report(report, 2)
        record_phase("preflight", "completed", checklist=preflight["checklist"])

        manifest = run_manifest(
            target,
            uv_binary=uv_binary,
            cache_file=cache_file,
            include_ignored=args.include_ignored,
            vision=args.vision,
            vision_provider=args.vision_provider,
            vision_model=args.vision_model,
            heartbeat=lambda: heartbeat_run_lock("scout"),
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
        manifest_path = snapshot_dir / "manifest.json"
        write_json(manifest_path, manifest)

        helper_ready_for_agent_review = bool(
            manifest.get("helper_ready_for_agent_review", manifest.get("next_actions", {}).get("execution_ready"))
        )
        draft_review_state = str(
            manifest.get("draft_review_state")
            or ("ready_for_agent_review" if helper_ready_for_agent_review else "needs_agent_reconciliation")
        )
        draft_actions = draft_actions_from_manifest(manifest, target)
        write_action_artifacts(draft_actions, helper_ready_for_agent_review)

        scout = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "manifest_path": str(manifest_path),
            "pass": len(manifest.get("manifest_iterations", [])),
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": manifest.get("active_gate_failures", []),
            "draft_actions": [],
            "file_count": manifest.get("file_count"),
            "cache_stats": manifest.get("cache_stats", {}),
            "draft_review_state": draft_review_state,
        }
        handoff_paths["scout"] = write_handoff(handoff_dir, "02-scout.json", scout)
        record_phase(
            "scout",
            "completed",
            manifest_path=str(manifest_path),
            pass_count=scout["pass"],
            low_confidence_count=scout["low_confidence_count"],
        )

        router = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "manifest_path": str(manifest_path),
            "pass": len(manifest.get("manifest_iterations", [])),
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": manifest.get("active_gate_failures", []),
            "routable_entries_count": sum(1 for entry in manifest.get("entries", []) if entry.get("routable")),
            "blocked_entries_count": sum(1 for entry in manifest.get("entries", []) if not entry.get("routable")),
            "draft_actions_preview": draft_actions[:25],
            "low_confidence_preview": manifest.get("low_confidence", [])[:25],
            "draft_review_state": draft_review_state,
        }
        handoff_paths["router"] = write_handoff(handoff_dir, "03-router.json", router)
        record_phase(
            "router",
            "completed",
            routable_entries_count=router["routable_entries_count"],
            blocked_entries_count=router["blocked_entries_count"],
        )

        active_gate_failures = manifest.get("active_gate_failures", [])
        gatekeeper = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "manifest_path": str(manifest_path),
            "pass": len(manifest.get("manifest_iterations", [])),
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": active_gate_failures,
            "draft_actions": draft_actions,
            "helper_ready_for_agent_review": helper_ready_for_agent_review,
            "requires_agent_review": True,
            "draft_review_state": draft_review_state,
        }
        handoff_paths["gatekeeper"] = write_handoff(handoff_dir, "04-gatekeeper.json", gatekeeper)
        record_phase(
            "gatekeeper",
            "ready_for_agent_review" if helper_ready_for_agent_review else "blocked",
            active_gate_failures=active_gate_failures,
            draft_actions=len(draft_actions),
        )

        action_deltas: list[dict[str, Any]] = []
        empty_dirs_removed: list[str] = []
        post_move_manifest_path: str | None = None
        post_move_summary: dict[str, Any] | None = None
        executor_status = "blocked"
        helper_execution_status = "blocked"

        if helper_ready_for_agent_review and args.execute:
            if not lock_is_owned_by(lock_path, snapshot_id, run_owner):
                active_gate_failures = list(active_gate_failures) + [
                    {
                        "code": "run_lock_lost",
                        "message": "The active run lock is no longer owned by this run; draft execution was refused.",
                        "run_lock_path": str(lock_path),
                    }
                ]
                helper_ready_for_agent_review = False
            else:
                action_deltas = execute_actions(draft_actions, heartbeat=lambda: heartbeat_run_lock("executor"))
                empty_dirs_removed = prune_empty_directories(
                    target,
                    heartbeat=lambda: heartbeat_run_lock("executor"),
                )
                executor_status = "executed"
                helper_execution_status = "executed"
        elif helper_ready_for_agent_review:
            executor_status = "ready_not_executed"
            helper_execution_status = "draft_ready_not_applied"

        if not helper_ready_for_agent_review and draft_review_state == "ready_for_agent_review":
            draft_review_state = "needs_agent_reconciliation"

        if executor_status == "executed":
            post_move_manifest = run_manifest(
                target,
                uv_binary=uv_binary,
                cache_file=cache_file,
                include_ignored=args.include_ignored,
                vision=args.vision,
                vision_provider=args.vision_provider,
                vision_model=args.vision_model,
                heartbeat=lambda: heartbeat_run_lock("audit"),
                heartbeat_interval_seconds=heartbeat_interval_seconds,
            )
            post_move_manifest_file = snapshot_dir / "post-move-manifest.json"
            write_json(post_move_manifest_file, post_move_manifest)
            post_move_manifest_path = str(post_move_manifest_file)
            post_move_summary = {
                "file_count": post_move_manifest.get("file_count"),
                "low_confidence_count": post_move_manifest.get("low_confidence_count"),
                "active_gate_failures": post_move_manifest.get("active_gate_failures", []),
                "cache_stats": post_move_manifest.get("cache_stats", {}),
            }

        executor = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "manifest_path": str(manifest_path),
            "pass": len(manifest.get("manifest_iterations", [])),
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": active_gate_failures,
            "draft_actions": draft_actions,
            "action_deltas": action_deltas,
            "empty_dirs_removed": empty_dirs_removed,
            "post_move_manifest_path": post_move_manifest_path,
            "post_move_summary": post_move_summary,
            "status": executor_status,
            "helper_execution_status": helper_execution_status,
        }
        handoff_paths["executor"] = write_handoff(handoff_dir, "05-executor.json", executor)
        record_phase(
            "executor",
            executor_status,
            moved_count=sum(1 for delta in action_deltas if delta.get("status") == "moved"),
            empty_dirs_removed=len(empty_dirs_removed),
        )

        audit = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "manifest_path": str(manifest_path),
            "pass": len(manifest.get("manifest_iterations", [])),
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": active_gate_failures,
            "draft_actions": draft_actions,
            "action_deltas": action_deltas,
            "status": executor_status,
            "helper_execution_status": helper_execution_status,
            "file_count": manifest.get("file_count"),
            "cache_stats": manifest.get("cache_stats", {}),
            "phase_history": phase_history,
            "empty_dirs_removed": empty_dirs_removed,
            "post_move_manifest_path": post_move_manifest_path,
            "post_move_summary": post_move_summary,
        }
        handoff_paths["audit"] = write_handoff(handoff_dir, "06-audit.json", audit)
        record_phase("audit", "completed", post_move_audited=bool(post_move_summary))

        report = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "snapshot_path": str(snapshot_dir),
            "inventory": inventory,
            "manifest_path": str(manifest_path),
            "draft_manifest_path": str(manifest_path),
            "handoff_paths": handoff_paths,
            "draft_actions_path": str(draft_actions_path),
            "approved_actions_path": str(legacy_actions_path),
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": active_gate_failures,
            "draft_review_state": draft_review_state,
            "helper_ready_for_agent_review": helper_ready_for_agent_review,
            "requires_agent_review": True,
            "helper_blockers_present": bool(manifest.get("low_confidence_count") or active_gate_failures),
            "execution_ready": helper_ready_for_agent_review,
            "executor_status": executor_status,
            "helper_execution_status": helper_execution_status,
            "cache_stats": manifest.get("cache_stats", {}),
            "phase_history": phase_history,
            "post_move_manifest_path": post_move_manifest_path,
            "post_move_summary": post_move_summary,
            "empty_dirs_removed": empty_dirs_removed,
        }
        return finalize_report(report, 0)
    finally:
        if lock_acquired:
            release_run_lock(
                lock_path=lock_path,
                run_id=snapshot_id,
                owner=run_owner,
                snapshot_dir=snapshot_dir,
                final_status="aborted",
            )


if __name__ == "__main__":
    raise SystemExit(main())
