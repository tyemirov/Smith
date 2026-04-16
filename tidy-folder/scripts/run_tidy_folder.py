#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
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
MOVE_LEDGER_FILENAME = "move-ledger.json"
RESTORE_REPORT_FILENAME = "restore-report.json"
HELPER_MANIFEST_FILENAME = "helper-manifest.json"
DEFAULT_LEASE_SECONDS = int(os.environ.get("TIDY_FOLDER_RUN_LEASE_SECONDS", "900"))
ROUTER_OVERRIDE_FALLBACK_HOMES = {"Photos", "Screen-Captures", "Projects/Code"}
SENSITIVE_GATE_FLAGS = {"sensitive", "identity", "finance", "credential"}
DIRECT_EVIDENCE_PREFIXES = ("text:", "ocr:", "metadata:", "vision:")


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
            try:
                stat_result = file_path.stat()
            except FileNotFoundError:
                # Preserve dangling symlinks in the inventory instead of aborting the run.
                stat_result = file_path.lstat()
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


def taxonomy_hints_for_entry(entry: dict[str, Any]) -> list[dict[str, Any]]:
    attribution = entry.get("attribution", {})
    hints = attribution.get("taxonomy_hints", [])
    return hints if isinstance(hints, list) else []


def strongest_project_marker_hint(entry: dict[str, Any]) -> dict[str, Any] | None:
    project_hints = [
        hint
        for hint in taxonomy_hints_for_entry(entry)
        if isinstance(hint, dict) and hint.get("source") == "project_markers" and hint.get("home")
    ]
    if not project_hints:
        return None
    project_hints.sort(key=lambda hint: float(hint.get("weight", 0.0)), reverse=True)
    return project_hints[0]


def evidence_prefixes(entry: dict[str, Any]) -> set[str]:
    prefixes: set[str] = set()
    for item in entry.get("evidence", []):
        if not isinstance(item, str) or ":" not in item:
            continue
        prefixes.add(item.split(":", 1)[0])
    return prefixes


def has_direct_evidence(entry: dict[str, Any]) -> bool:
    evidence = entry.get("evidence", [])
    if any(isinstance(item, str) and item.startswith(DIRECT_EVIDENCE_PREFIXES) for item in evidence):
        return True
    if evidence_prefixes(entry).intersection({"text", "ocr", "metadata", "vision"}):
        return True
    return False


def apply_entry_failure(entry: dict[str, Any], failure: dict[str, Any], *, stage: str, rationale: str) -> None:
    failures = entry.setdefault("gate_failures", [])
    if isinstance(failures, list):
        failures.append(failure)
    entry["proposed_destination"] = None
    entry["routable"] = False
    entry["placement_mode"] = "gatekeeper_blocked"
    entry["rationale"] = rationale
    review = entry.setdefault("controller_review", {})
    if isinstance(review, dict):
        review["decision"] = "block"
        review["final_destination"] = None
        review["stage"] = stage
        review["rationale"] = rationale


def summarize_gate_failures(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for failure in failures:
        code = str(failure.get("code") or "controller_gate_failure")
        bucket = grouped.setdefault(
            code,
            {
                "code": code,
                "message": failure.get("message"),
                "count": 0,
                "samples": [],
            },
        )
        bucket["count"] += 1
        sample = {key: value for key, value in failure.items() if key != "message"}
        if len(bucket["samples"]) < 5:
            bucket["samples"].append(sample)
    return list(grouped.values())


def build_controller_review_manifest(helper_manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    reviewed_manifest = copy.deepcopy(helper_manifest)
    reviewed_entries = reviewed_manifest.get("entries", [])
    if not isinstance(reviewed_entries, list):
        reviewed_entries = []
        reviewed_manifest["entries"] = reviewed_entries

    router_decisions = {"accepted": 0, "overridden": 0, "blocked": 0}
    for entry in reviewed_entries:
        if not isinstance(entry, dict):
            continue
        helper_destination = entry.get("proposed_destination")
        project_hint = strongest_project_marker_hint(entry)
        decision = "accept"
        rationale = "Accepted helper destination after controller review of raw evidence, hints, and alternatives."
        final_destination = helper_destination

        if not helper_destination or entry.get("needs_refinement") or entry.get("gate_failures"):
            decision = "block"
            rationale = "Blocked for controller review because the helper draft still has unresolved blockers."
            final_destination = None
            entry["proposed_destination"] = None
            entry["routable"] = False
            entry["rationale"] = rationale
        elif (
            project_hint is not None
            and project_hint.get("home") != helper_destination
            and helper_destination in ROUTER_OVERRIDE_FALLBACK_HOMES
        ):
            decision = "override"
            final_destination = project_hint.get("home")
            entry["proposed_destination"] = final_destination
            entry["routable"] = bool(final_destination)
            rationale = (
                f"Project marker scope '{project_hint.get('scope')}' outranks fallback helper home "
                f"'{helper_destination}'."
            )
            entry["rationale"] = rationale

        entry["controller_review"] = {
            "stage": "router",
            "decision": decision,
            "helper_destination": helper_destination,
            "final_destination": final_destination,
            "project_marker_home": project_hint.get("home") if project_hint else None,
            "rationale": rationale,
        }
        if decision == "accept":
            router_decisions["accepted"] += 1
        elif decision == "override":
            router_decisions["overridden"] += 1
        else:
            router_decisions["blocked"] += 1

    independent_failures: list[dict[str, Any]] = []
    for entry in reviewed_entries:
        if not isinstance(entry, dict) or not entry.get("proposed_destination"):
            continue
        flags = {str(flag) for flag in entry.get("flags", [])}
        if flags.intersection(SENSITIVE_GATE_FLAGS) and not has_direct_evidence(entry):
            failure = {
                "code": "controller_sensitive_requires_direct_evidence",
                "message": "Sensitive destinations require direct content evidence before execution.",
                "source_path": entry.get("source_path"),
                "destination": entry.get("proposed_destination"),
                "flags": sorted(flags.intersection(SENSITIVE_GATE_FLAGS)),
            }
            independent_failures.append(failure)
            apply_entry_failure(
                entry,
                failure,
                stage="gatekeeper",
                rationale="Blocked by gatekeeper because the route is sensitive but only weak/path-based evidence is present.",
            )
            continue
        if not entry.get("evidence") and strongest_project_marker_hint(entry) is None:
            failure = {
                "code": "controller_missing_review_evidence",
                "message": "Controller review requires raw evidence or a strong taxonomy anchor before execution.",
                "source_path": entry.get("source_path"),
                "destination": entry.get("proposed_destination"),
            }
            independent_failures.append(failure)
            apply_entry_failure(
                entry,
                failure,
                stage="gatekeeper",
                rationale="Blocked by gatekeeper because the route has no raw evidence or project anchor to justify execution.",
            )

    active_gate_failures = list(reviewed_manifest.get("active_gate_failures", []))
    active_gate_failures.extend(summarize_gate_failures(independent_failures))
    reviewed_manifest["active_gate_failures"] = active_gate_failures
    reviewed_manifest["decision_authority"] = "controller_reviewed"
    reviewed_manifest["controller_review_summary"] = {
        "router": router_decisions,
        "gatekeeper_blocks": len(independent_failures),
    }
    reviewed_manifest["controller_ready_for_execution"] = not active_gate_failures
    reviewed_manifest["execution_blocked"] = bool(active_gate_failures)
    reviewed_manifest["execution_ready"] = not active_gate_failures
    reviewed_manifest["draft_status"] = "ready_for_execution" if not active_gate_failures else "needs_reconciliation"
    next_actions = reviewed_manifest.get("next_actions")
    if isinstance(next_actions, dict):
        next_actions["requires_reconciliation"] = bool(active_gate_failures)
        next_actions["requires_refinement_pass"] = bool(active_gate_failures)
        next_actions["execution_ready"] = not active_gate_failures
        next_actions["description"] = (
            "Controller-reviewed routes are ready to execute."
            if not active_gate_failures
            else "Controller review found blockers; refine the manifest before execution."
        )

    router_summary = {
        "accepted": router_decisions["accepted"],
        "overridden": router_decisions["overridden"],
        "blocked": router_decisions["blocked"],
    }
    gatekeeper_summary = {
        "independent_blocks": len(independent_failures),
        "active_gate_failures": active_gate_failures,
    }
    return reviewed_manifest, router_summary, gatekeeper_summary


def list_snapshot_dirs(target: Path) -> list[Path]:
    snapshot_root = target / SNAPSHOT_DIRNAME
    if not snapshot_root.exists():
        return []
    return sorted(path for path in snapshot_root.iterdir() if path.is_dir())


def resolve_restore_snapshot_dir(target: Path, snapshot_id: str) -> tuple[Path | None, dict[str, Any] | None]:
    restore_snapshot_dir = target / SNAPSHOT_DIRNAME / snapshot_id
    if restore_snapshot_dir.exists() and restore_snapshot_dir.is_dir():
        return restore_snapshot_dir, None
    return None, {
        "code": "restore_snapshot_not_found",
        "message": "The requested snapshot id was not found under .tidy-folder-snapshots.",
        "restore_snapshot_id": snapshot_id,
        "restore_snapshot_path": str(restore_snapshot_dir),
    }


def path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def build_router_decision_log(manifest: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for entry in manifest.get("entries", []):
        if len(decisions) >= limit:
            break
        controller_review = entry.get("controller_review", {})
        decisions.append(
            {
                "source_path": entry.get("source_path"),
                "decision": controller_review.get("decision") or ("route" if entry.get("routable") else "block"),
                "helper_destination": controller_review.get("helper_destination"),
                "destination": controller_review.get("final_destination", entry.get("proposed_destination")),
                "rationale": controller_review.get("rationale") or entry.get("rationale"),
                "confidence_score": entry.get("confidence_score"),
                "gate_failures": entry.get("gate_failures", []),
            }
        )
    return decisions


def build_gatekeeper_sample_log(manifest: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    entries = list(manifest.get("entries", []))
    samples: list[dict[str, Any]] = []
    sampled_sources: set[str] = set()

    def add_sample(entry: dict[str, Any], scope: str) -> None:
        source_path = str(entry.get("source_path") or "")
        if not source_path or source_path in sampled_sources or len(samples) >= limit:
            return
        sampled_sources.add(source_path)
        samples.append(
            {
                "scope": scope,
                "source_path": source_path,
                "destination": entry.get("proposed_destination"),
                "controller_decision": entry.get("controller_review", {}).get("decision"),
                "confidence_score": entry.get("confidence_score"),
                "evidence": entry.get("evidence", [])[:4],
                "flags": entry.get("flags", []),
                "rationale": entry.get("rationale"),
            }
        )

    for entry in entries:
        flags = set(entry.get("flags", []))
        if flags.intersection({"sensitive", "identity", "finance", "credential"}):
            add_sample(entry, "sensitive_bucket")

    for entry in entries:
        if entry.get("needs_refinement") or not entry.get("routable"):
            add_sample(entry, "weak_signal")

    homes_seen: set[str] = set()
    for entry in entries:
        destination = str(entry.get("proposed_destination") or "")
        if not destination or destination in homes_seen:
            continue
        homes_seen.add(destination)
        add_sample(entry, "major_home")
        if len(samples) >= limit:
            break

    return samples


def write_move_ledger(
    *,
    move_ledger_path: Path,
    snapshot_id: str,
    target: Path,
    action_deltas: list[dict[str, Any]],
    empty_dirs_removed: list[str],
) -> None:
    write_json(
        move_ledger_path,
        {
            "snapshot_id": snapshot_id,
            "target_folder": str(target),
            "created_at": utc_timestamp(),
            "action_deltas": action_deltas,
            "empty_dirs_removed": empty_dirs_removed,
        },
    )


def restore_from_snapshot(
    *,
    target: Path,
    restore_snapshot_dir: Path,
    restore_report_path: Path,
    heartbeat: Callable[[], None] | None = None,
) -> dict[str, Any]:
    move_ledger = load_json(restore_snapshot_dir / MOVE_LEDGER_FILENAME)
    if not isinstance(move_ledger, dict):
        restore_report = {
            "status": "blocked",
            "code": "restore_missing_move_ledger",
            "message": "The requested snapshot does not contain a move ledger for restoration.",
            "restore_snapshot_id": restore_snapshot_dir.name,
            "restore_snapshot_path": str(restore_snapshot_dir),
            "restored_moves": 0,
            "failures": [],
            "recreated_directories": [],
        }
        write_json(restore_report_path, restore_report)
        return restore_report

    action_deltas = move_ledger.get("action_deltas", [])
    if not isinstance(action_deltas, list):
        action_deltas = []

    restored_moves = 0
    failures: list[dict[str, Any]] = []
    restored_paths: list[dict[str, Any]] = []
    restore_scope = target.parent
    for delta in reversed(action_deltas):
        if heartbeat is not None:
            heartbeat()
        move_status = str(delta.get("status") or "") if isinstance(delta, dict) else ""
        if not isinstance(delta, dict) or move_status not in {"moved", "moved_to_snapshot_trash"}:
            continue
        source = Path(str(delta.get("source_path") or "")).expanduser().resolve()
        destination = Path(str(delta.get("destination_path") or "")).expanduser().resolve()
        if (
            not path_within(source, restore_scope)
            or not path_within(destination, restore_scope)
            or not (path_within(source, target) or path_within(destination, target))
        ):
            failures.append(
                {
                    "code": "restore_outside_scope",
                    "source_path": str(source),
                    "destination_path": str(destination),
                }
            )
            continue
        if not destination.exists():
            failures.append(
                {
                    "code": "restore_missing_destination",
                    "source_path": str(source),
                    "destination_path": str(destination),
                }
            )
            continue
        if source.exists():
            failures.append(
                {
                    "code": "restore_source_conflict",
                    "source_path": str(source),
                    "destination_path": str(destination),
                }
            )
            continue
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination), str(source))
        restored_moves += 1
        restored_paths.append({"from": str(destination), "to": str(source)})

    removed_after_restore = prune_empty_directories(target, heartbeat=heartbeat)

    recreated_directories: list[str] = []
    files_path = restore_snapshot_dir / "files.txt"
    tree_path = restore_snapshot_dir / "tree.txt"
    files_lines = set()
    try:
        files_lines = {
            line.strip()
            for line in files_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    except FileNotFoundError:
        files_lines = set()

    try:
        for raw in tree_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line == "." or line in files_lines:
                continue
            directory = target / line.removeprefix("./")
            if directory.exists():
                continue
            directory.mkdir(parents=True, exist_ok=True)
            recreated_directories.append(display_path(directory, target))
    except FileNotFoundError:
        pass

    restore_report = {
        "status": "restored" if not failures else "restored_with_warnings",
        "restore_snapshot_id": restore_snapshot_dir.name,
        "restore_snapshot_path": str(restore_snapshot_dir),
        "restored_moves": restored_moves,
        "restored_paths": restored_paths,
        "removed_after_restore": removed_after_restore,
        "recreated_directories": sorted(set(recreated_directories)),
        "failures": failures,
    }
    write_json(restore_report_path, restore_report)
    return restore_report


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
    parser = argparse.ArgumentParser(
        description="Create a tidy-folder snapshot, scan for draft actions, optionally execute them, or restore a previous snapshot."
    )
    parser.add_argument("target", metavar="folder", help="Folder to organize (required)")
    parser.add_argument("--include-ignored", action="store_true", help="Pass --include-ignored through to semantic_scan.py")
    parser.add_argument("--vision", action="store_true", help="Enable vision mode when building the manifest")
    parser.add_argument("--vision-provider", default="hf", choices=("hf", "openai"))
    parser.add_argument("--vision-model", default="")
    parser.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS, help="Stale-lease threshold for the active run lock")
    parser.add_argument("--run-owner", default="", help="Optional explicit owner identifier for the active run lock")
    parser.add_argument("--execute", action="store_true", help="Apply the current run's draft actions when the scan reports no blockers")
    parser.add_argument("--restore-snapshot", default="", help="Restore file placement from a previous snapshot id using its move ledger")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    target = Path(args.target).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print(f"error: target folder does not exist: {target}", file=sys.stderr)
        return 2
    if args.execute and args.restore_snapshot:
        print("error: --execute and --restore-snapshot cannot be used together", file=sys.stderr)
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
    move_ledger_path = snapshot_dir / MOVE_LEDGER_FILENAME
    restore_report_path = snapshot_dir / RESTORE_REPORT_FILENAME
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

    def write_action_artifacts(
        *,
        draft_actions: list[dict[str, Any]],
        execution_ready: bool,
        draft_status: str,
        helper_ready_for_execution: bool,
        helper_blockers_present: bool,
    ) -> None:
        write_json(
            draft_actions_path,
            {
                "snapshot_id": snapshot_id,
                "mode": "restore" if args.restore_snapshot else "scan",
                "draft_actions": draft_actions,
                "draft_status": draft_status,
                "execution_ready": execution_ready,
                "helper_ready_for_execution": helper_ready_for_execution,
                "helper_blockers_present": helper_blockers_present,
                "move_ledger_path": str(move_ledger_path),
                "restore_report_path": str(restore_report_path),
            },
        )

    def finalize_report(report: dict[str, Any], return_code: int) -> int:
        nonlocal lock_acquired
        final_status = str(report.get("executor_status") or report.get("restore_status") or "completed")
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
            write_action_artifacts(
                draft_actions=[],
                execution_ready=False,
                draft_status="blocked_by_run_lock",
                helper_ready_for_execution=False,
                helper_blockers_present=True,
            )
            report = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "snapshot_path": str(snapshot_dir),
                "inventory": inventory,
                "helper_manifest_path": None,
                "manifest_path": None,
                "draft_manifest_path": None,
                "handoff_paths": handoff_paths,
                "draft_actions_path": str(draft_actions_path),
                "move_ledger_path": None,
                "restore_report_path": None,
                "low_confidence_count": None,
                "active_gate_failures": [lock_failure],
                "helper_blockers_present": True,
                "helper_ready_for_execution": False,
                "draft_status": "blocked_by_run_lock",
                "execution_ready": False,
                "executor_status": "blocked",
                "helper_execution_status": "blocked",
                "cache_stats": {},
                "phase_history": phase_history,
                "post_move_manifest_path": None,
                "post_move_summary": None,
                "restore_snapshot_id": args.restore_snapshot or None,
                "restore_status": None,
                "empty_dirs_removed": [],
            }
            return finalize_report(report, 2)

        inventory = snapshot_inventory(target, snapshot_dir, heartbeat=lambda: heartbeat_run_lock("preflight"))

        preflight_failures: list[dict[str, Any]] = []
        if not args.restore_snapshot and uv_binary is None:
            preflight_failures.append(
                {
                    "code": "preflight_missing_uv",
                    "message": "uv is required to run semantic_scan.py.",
                }
            )
        if not args.restore_snapshot and not SCANNER.exists():
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
            write_action_artifacts(
                draft_actions=[],
                execution_ready=False,
                draft_status="blocked_preflight",
                helper_ready_for_execution=False,
                helper_blockers_present=True,
            )
            report = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "snapshot_path": str(snapshot_dir),
                "inventory": inventory,
                "helper_manifest_path": None,
                "manifest_path": None,
                "draft_manifest_path": None,
                "handoff_paths": handoff_paths,
                "draft_actions_path": str(draft_actions_path),
                "move_ledger_path": None,
                "restore_report_path": None,
                "low_confidence_count": None,
                "active_gate_failures": preflight_failures,
                "helper_blockers_present": True,
                "helper_ready_for_execution": False,
                "draft_status": "blocked_preflight",
                "execution_ready": False,
                "executor_status": "blocked",
                "helper_execution_status": "blocked",
                "cache_stats": {},
                "phase_history": phase_history,
                "post_move_manifest_path": None,
                "post_move_summary": None,
                "restore_snapshot_id": args.restore_snapshot or None,
                "restore_status": None,
                "empty_dirs_removed": [],
            }
            return finalize_report(report, 2)
        record_phase("preflight", "completed", checklist=preflight["checklist"])

        if args.restore_snapshot:
            restore_snapshot_dir, restore_failure = resolve_restore_snapshot_dir(target, args.restore_snapshot)
            if restore_failure is not None:
                preflight["active_gate_failures"] = [restore_failure]
                write_json(Path(handoff_paths["preflight"]), preflight)
                record_phase("preflight", "blocked", active_gate_failures=[restore_failure])
                write_action_artifacts(
                    draft_actions=[],
                    execution_ready=False,
                    draft_status="restore_snapshot_not_found",
                    helper_ready_for_execution=False,
                    helper_blockers_present=True,
                )
                report = {
                    "target_folder": str(target),
                    "snapshot_id": snapshot_id,
                    "snapshot_path": str(snapshot_dir),
                    "inventory": inventory,
                    "helper_manifest_path": None,
                    "manifest_path": None,
                    "draft_manifest_path": None,
                    "handoff_paths": handoff_paths,
                    "draft_actions_path": str(draft_actions_path),
                    "move_ledger_path": None,
                    "restore_report_path": None,
                    "low_confidence_count": None,
                    "active_gate_failures": [restore_failure],
                    "helper_blockers_present": True,
                    "helper_ready_for_execution": False,
                    "draft_status": "restore_snapshot_not_found",
                    "execution_ready": False,
                    "executor_status": "blocked",
                    "helper_execution_status": "blocked",
                    "cache_stats": {},
                    "phase_history": phase_history,
                    "post_move_manifest_path": None,
                    "post_move_summary": None,
                    "restore_snapshot_id": args.restore_snapshot,
                    "restore_status": None,
                    "empty_dirs_removed": [],
                }
                return finalize_report(report, 2)

            write_action_artifacts(
                draft_actions=[],
                execution_ready=False,
                draft_status="restore_mode",
                helper_ready_for_execution=False,
                helper_blockers_present=True,
            )

            restore_snapshot_path = str(restore_snapshot_dir)
            restore_scout = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "mode": "restore",
                "restore_snapshot_id": args.restore_snapshot,
                "restore_snapshot_path": restore_snapshot_path,
                "status": "skipped_restore_only",
            }
            handoff_paths["scout"] = write_handoff(handoff_dir, "02-scout.json", restore_scout)
            record_phase("scout", "skipped_restore_only", restore_snapshot_id=args.restore_snapshot)

            restore_router = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "mode": "restore",
                "restore_snapshot_id": args.restore_snapshot,
                "restore_snapshot_path": restore_snapshot_path,
                "status": "skipped_restore_only",
                "decision_log": [],
            }
            handoff_paths["router"] = write_handoff(handoff_dir, "03-router.json", restore_router)
            record_phase("router", "skipped_restore_only", restore_snapshot_id=args.restore_snapshot)

            restore_gatekeeper = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "mode": "restore",
                "restore_snapshot_id": args.restore_snapshot,
                "restore_snapshot_path": restore_snapshot_path,
                "status": "skipped_restore_only",
                "sample_review_log": [],
                "active_gate_failures": [],
            }
            handoff_paths["gatekeeper"] = write_handoff(handoff_dir, "04-gatekeeper.json", restore_gatekeeper)
            record_phase("gatekeeper", "skipped_restore_only", restore_snapshot_id=args.restore_snapshot)

            restore_result = restore_from_snapshot(
                target=target,
                restore_snapshot_dir=restore_snapshot_dir,
                restore_report_path=restore_report_path,
                heartbeat=lambda: heartbeat_run_lock("executor"),
            )
            restore_gate_failures = []
            if restore_result.get("status") == "blocked":
                restore_gate_failures = [
                    {
                        "code": restore_result.get("code"),
                        "message": restore_result.get("message"),
                        "restore_snapshot_id": args.restore_snapshot,
                        "restore_snapshot_path": restore_snapshot_path,
                    }
                ]
            executor_status = "restored" if str(restore_result.get("status", "")).startswith("restored") else "blocked"
            executor = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "mode": "restore",
                "restore_snapshot_id": args.restore_snapshot,
                "restore_snapshot_path": restore_snapshot_path,
                "status": executor_status,
                "restore_status": restore_result.get("status"),
                "restore_report_path": str(restore_report_path),
                "restored_moves": restore_result.get("restored_moves", 0),
                "restored_paths": restore_result.get("restored_paths", []),
                "active_gate_failures": restore_gate_failures,
            }
            handoff_paths["executor"] = write_handoff(handoff_dir, "05-executor.json", executor)
            record_phase(
                "executor",
                executor_status,
                restored_moves=restore_result.get("restored_moves", 0),
                failures=len(restore_result.get("failures", [])),
            )

            audit = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "mode": "restore",
                "restore_snapshot_id": args.restore_snapshot,
                "restore_snapshot_path": restore_snapshot_path,
                "status": executor_status,
                "restore_status": restore_result.get("status"),
                "restore_report_path": str(restore_report_path),
                "restore_failures": restore_result.get("failures", []),
                "phase_history": phase_history,
            }
            handoff_paths["audit"] = write_handoff(handoff_dir, "06-audit.json", audit)
            record_phase("audit", "completed", restore_status=restore_result.get("status"))

            report = {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "snapshot_path": str(snapshot_dir),
                "inventory": inventory,
                "helper_manifest_path": None,
                "manifest_path": None,
                "draft_manifest_path": None,
                "handoff_paths": handoff_paths,
                "draft_actions_path": str(draft_actions_path),
                "move_ledger_path": None,
                "restore_report_path": str(restore_report_path),
                "low_confidence_count": None,
                "active_gate_failures": restore_gate_failures,
                "helper_blockers_present": bool(restore_gate_failures),
                "helper_ready_for_execution": False,
                "draft_status": "restore_mode",
                "execution_ready": False,
                "executor_status": executor_status,
                "helper_execution_status": executor_status,
                "cache_stats": {},
                "phase_history": phase_history,
                "post_move_manifest_path": None,
                "post_move_summary": None,
                "restore_snapshot_id": args.restore_snapshot,
                "restore_status": restore_result.get("status"),
                "empty_dirs_removed": restore_result.get("removed_after_restore", []),
            }
            return finalize_report(report, 0 if executor_status == "restored" else 2)

        helper_manifest = run_manifest(
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
        helper_manifest_path = snapshot_dir / HELPER_MANIFEST_FILENAME
        write_json(helper_manifest_path, helper_manifest)
        manifest, router_review_summary, gatekeeper_review_summary = build_controller_review_manifest(
            helper_manifest
        )
        manifest_path = snapshot_dir / "manifest.json"
        write_json(manifest_path, manifest)

        helper_ready_for_execution = bool(
            helper_manifest.get("helper_ready_for_execution", helper_manifest.get("execution_ready"))
        )
        draft_status = str(
            manifest.get("draft_status")
            or ("ready_for_execution" if helper_ready_for_execution else "needs_reconciliation")
        )
        helper_blockers_present = bool(
            helper_manifest.get(
                "helper_blockers_present",
                bool(helper_manifest.get("low_confidence_count") or helper_manifest.get("active_gate_failures", [])),
            )
        )
        active_gate_failures = list(manifest.get("active_gate_failures", []))
        execution_ready = bool(manifest.get("execution_ready")) and not active_gate_failures
        draft_actions = draft_actions_from_manifest(manifest, target)
        write_action_artifacts(
            draft_actions=draft_actions,
            execution_ready=execution_ready,
            draft_status=draft_status,
            helper_ready_for_execution=helper_ready_for_execution,
            helper_blockers_present=helper_blockers_present,
        )

        scout = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "manifest_path": str(manifest_path),
            "helper_manifest_path": str(helper_manifest_path),
            "scout_evidence_paths": [str(helper_manifest_path)],
            "pass": len(helper_manifest.get("manifest_iterations", [])),
            "low_confidence_count": helper_manifest.get("low_confidence_count"),
            "active_gate_failures": helper_manifest.get("active_gate_failures", []),
            "draft_actions_count": len(draft_actions),
            "file_count": helper_manifest.get("file_count"),
            "cache_stats": helper_manifest.get("cache_stats", {}),
            "draft_status": draft_status,
            "execution_ready": execution_ready,
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
            "helper_manifest_path": str(helper_manifest_path),
            "scout_evidence_paths": [str(helper_manifest_path)],
            "pass": len(manifest.get("manifest_iterations", [])),
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": active_gate_failures,
            "routable_entries_count": sum(1 for entry in manifest.get("entries", []) if entry.get("routable")),
            "blocked_entries_count": sum(1 for entry in manifest.get("entries", []) if not entry.get("routable")),
            "draft_actions_count": len(draft_actions),
            "low_confidence_preview": manifest.get("low_confidence", [])[:25],
            "draft_status": draft_status,
            "status": draft_status,
            "decision_basis": "controller_review",
            "helper_findings": {
                "helper_ready_for_execution": helper_ready_for_execution,
                "helper_blockers_present": helper_blockers_present,
                "active_gate_failures": helper_manifest.get("active_gate_failures", []),
            },
            "decision_rationale": "Controller router accepted, overrode, or blocked helper routes using raw entry evidence and project-marker hints.",
            "controller_review_summary": router_review_summary,
            "decision_log": build_router_decision_log(manifest),
        }
        handoff_paths["router"] = write_handoff(handoff_dir, "03-router.json", router)
        record_phase(
            "router",
            router["status"],
            routable_entries_count=router["routable_entries_count"],
            blocked_entries_count=router["blocked_entries_count"],
        )

        gatekeeper = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "manifest_path": str(manifest_path),
            "helper_manifest_path": str(helper_manifest_path),
            "scout_evidence_paths": [str(helper_manifest_path)],
            "pass": len(manifest.get("manifest_iterations", [])),
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": active_gate_failures,
            "draft_actions_count": len(draft_actions),
            "helper_blockers_present": helper_blockers_present,
            "helper_ready_for_execution": helper_ready_for_execution,
            "status": "cleared_for_execution" if execution_ready else "blocked",
            "helper_findings": {
                "helper_ready_for_execution": helper_ready_for_execution,
                "helper_blockers_present": helper_blockers_present,
            },
            "decision_rationale": "Gatekeeper independently reviewed raw entry evidence, sensitive flags, and project-marker hints before clearing execution.",
            "controller_review_summary": gatekeeper_review_summary,
            "sample_review_log": build_gatekeeper_sample_log(manifest),
        }
        handoff_paths["gatekeeper"] = write_handoff(handoff_dir, "04-gatekeeper.json", gatekeeper)
        record_phase(
            "gatekeeper",
            gatekeeper["status"],
            active_gate_failures=active_gate_failures,
            draft_actions=len(draft_actions),
        )

        action_deltas: list[dict[str, Any]] = []
        empty_dirs_removed: list[str] = []
        post_move_manifest_path: str | None = None
        post_move_summary: dict[str, Any] | None = None
        executor_status = "ready_not_executed" if execution_ready else "blocked"
        helper_execution_status = "draft_ready" if helper_ready_for_execution else "blocked_by_helper"
        if not execution_ready and helper_ready_for_execution:
            helper_execution_status = "blocked_by_controller_review"

        if args.execute:
            if not execution_ready:
                executor_status = "blocked"
                helper_execution_status = (
                    "blocked_by_controller_review" if helper_ready_for_execution else "blocked_by_helper"
                )
            elif not lock_is_owned_by(lock_path, snapshot_id, run_owner):
                active_gate_failures = [
                    {
                        "code": "run_lock_lost",
                        "message": "The active run lock is no longer owned by this run; execution was refused.",
                        "run_lock_path": str(lock_path),
                    }
                ]
                execution_ready = False
                executor_status = "blocked"
                helper_execution_status = "blocked"
            else:
                action_deltas = execute_actions(
                    draft_actions,
                    heartbeat=lambda: heartbeat_run_lock("executor"),
                )
                empty_dirs_removed = prune_empty_directories(
                    target,
                    heartbeat=lambda: heartbeat_run_lock("executor"),
                )
                write_move_ledger(
                    move_ledger_path=move_ledger_path,
                    snapshot_id=snapshot_id,
                    target=target,
                    action_deltas=action_deltas,
                    empty_dirs_removed=empty_dirs_removed,
                )
                executor_status = "executed"
                helper_execution_status = "executed"

        if executor_status == "executed":
            post_move_helper_manifest = run_manifest(
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
            post_move_manifest, _post_router_summary, _post_gatekeeper_summary = build_controller_review_manifest(
                post_move_helper_manifest
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
            "move_ledger_path": str(move_ledger_path) if executor_status == "executed" else None,
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
            "helper_manifest_path": str(helper_manifest_path),
            "manifest_path": str(manifest_path),
            "draft_manifest_path": str(manifest_path),
            "handoff_paths": handoff_paths,
            "draft_actions_path": str(draft_actions_path),
            "move_ledger_path": str(move_ledger_path) if executor_status == "executed" else None,
            "restore_report_path": None,
            "low_confidence_count": manifest.get("low_confidence_count"),
            "active_gate_failures": active_gate_failures,
            "helper_blockers_present": helper_blockers_present,
            "helper_ready_for_execution": helper_ready_for_execution,
            "draft_status": draft_status,
            "execution_ready": execution_ready,
            "executor_status": executor_status,
            "helper_execution_status": helper_execution_status,
            "cache_stats": manifest.get("cache_stats", {}),
            "phase_history": phase_history,
            "post_move_manifest_path": post_move_manifest_path,
            "post_move_summary": post_move_summary,
            "restore_snapshot_id": None,
            "restore_status": None,
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
