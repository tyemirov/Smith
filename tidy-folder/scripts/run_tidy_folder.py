#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SCANNER = ROOT / "semantic_scan.py"
SNAPSHOT_DIRNAME = ".tidy-folder-snapshots"
SNAPSHOT_PRUNE = {".git", SNAPSHOT_DIRNAME}


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


def snapshot_inventory(root: Path, snapshot_dir: Path) -> dict[str, str]:
    tree_lines = ["."]
    file_lines: list[str] = []
    metadata_lines: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if d not in SNAPSHOT_PRUNE)
        filenames = sorted(filenames)

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
    include_ignored: bool,
    vision: bool,
    vision_provider: str,
    vision_model: str,
) -> dict[str, Any]:
    args = [
        uv_binary,
        "run",
        str(SCANNER),
        str(target),
        "--manifest",
        "--autopilot",
    ]
    if include_ignored:
        args.append("--include-ignored")
    if vision:
        args.extend(["--vision", "--vision-provider", vision_provider])
        if vision_model:
            args.extend(["--vision-model", vision_model])

    proc = subprocess.run(args, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


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


def approved_actions(manifest: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for entry in manifest.get("entries", []):
        if not entry.get("routable"):
            continue
        destination = entry.get("proposed_destination")
        if not destination:
            continue

        source = Path(entry["source_path"])
        destination_dir = root / destination
        destination_path = destination_dir / source.name
        actions.append(
            {
                "source_path": str(source),
                "destination_dir": str(destination_dir),
                "destination_path": str(destination_path),
                "confidence_score": entry.get("confidence_score"),
                "rationale": entry.get("rationale"),
            }
        )
    return actions


def execute_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    for action in actions:
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


def prune_empty_directories(root: Path) -> list[str]:
    removed: list[str] = []
    for dirpath, dirnames, _filenames in os.walk(root, topdown=False):
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run tidy-folder with snapshot, manifest, gatekeeper, and optional execution artifacts.")
    parser.add_argument("target", help="Folder to organize")
    parser.add_argument("--include-ignored", action="store_true", help="Pass --include-ignored through to semantic_scan.py")
    parser.add_argument("--vision", action="store_true", help="Enable vision mode when building the manifest")
    parser.add_argument("--vision-provider", default="hf", choices=("hf", "openai"))
    parser.add_argument("--vision-model", default="")
    parser.add_argument("--execute", action="store_true", help="Execute approved actions after the manifest passes all gates")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    target = Path(args.target).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print(f"error: target folder does not exist: {target}", file=sys.stderr)
        return 2

    snapshot_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = target / SNAPSHOT_DIRNAME / snapshot_id
    handoff_dir = snapshot_dir / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    uv_binary = resolve_uv_binary()

    inventory = snapshot_inventory(target, snapshot_dir)
    supervisor_path = write_handoff(
        handoff_dir,
        "00-supervisor.json",
        {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "snapshot_path": str(snapshot_dir),
            "phase_history": [],
        },
    )
    handoff_paths = {
        "supervisor": supervisor_path,
    }
    phase_history: list[dict[str, Any]] = []

    def record_phase(phase: str, status: str, **details: Any) -> None:
        phase_history.append({"phase": phase, "status": status, **details})
        write_json(
            Path(supervisor_path),
            {
                "target_folder": str(target),
                "snapshot_id": snapshot_id,
                "snapshot_path": str(snapshot_dir),
                "phase_history": phase_history,
            },
        )

    preflight = {
        "target_folder": str(target),
        "snapshot_id": snapshot_id,
        "snapshot_path": str(snapshot_dir),
        "manifest_path": None,
        "pass": 0,
        "low_confidence_count": None,
        "active_gate_failures": [],
        "approved_actions": [],
        "checklist": {
            "target_exists": True,
            "uv_available": bool(uv_binary),
            "scanner_available": SCANNER.exists(),
            "snapshot_created": True,
        },
    }
    handoff_paths["preflight"] = write_handoff(handoff_dir, "01-preflight.json", preflight)
    record_phase("preflight", "completed", checklist=preflight["checklist"])

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
        action_path = snapshot_dir / "approved-actions.json"
        write_json(action_path, {"approved_actions": []})
        report = {
            "target_folder": str(target),
            "snapshot_id": snapshot_id,
            "snapshot_path": str(snapshot_dir),
            "inventory": inventory,
            "manifest_path": None,
            "handoff_paths": handoff_paths,
            "approved_actions_path": str(action_path),
            "low_confidence_count": None,
            "active_gate_failures": preflight_failures,
            "execution_ready": False,
            "executor_status": "blocked",
            "cache_stats": {},
            "phase_history": phase_history,
            "post_move_manifest_path": None,
            "post_move_summary": None,
            "empty_dirs_removed": [],
        }
        report_path = snapshot_dir / "run-report.json"
        write_json(report_path, report)
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 2

    manifest = run_manifest(
        target,
        uv_binary=uv_binary,
        include_ignored=args.include_ignored,
        vision=args.vision,
        vision_provider=args.vision_provider,
        vision_model=args.vision_model,
    )
    manifest_path = snapshot_dir / "manifest.json"
    write_json(manifest_path, manifest)

    scout = {
        "target_folder": str(target),
        "snapshot_id": snapshot_id,
        "manifest_path": str(manifest_path),
        "pass": len(manifest.get("manifest_iterations", [])),
        "low_confidence_count": manifest.get("low_confidence_count"),
        "active_gate_failures": manifest.get("active_gate_failures", []),
        "approved_actions": [],
        "file_count": manifest.get("file_count"),
        "cache_stats": manifest.get("cache_stats", {}),
    }
    handoff_paths["scout"] = write_handoff(handoff_dir, "02-scout.json", scout)
    record_phase(
        "scout",
        "completed",
        manifest_path=str(manifest_path),
        pass_count=scout["pass"],
        low_confidence_count=scout["low_confidence_count"],
    )

    actions = approved_actions(manifest, target)
    router = {
        "target_folder": str(target),
        "snapshot_id": snapshot_id,
        "manifest_path": str(manifest_path),
        "pass": len(manifest.get("manifest_iterations", [])),
        "low_confidence_count": manifest.get("low_confidence_count"),
        "active_gate_failures": manifest.get("active_gate_failures", []),
        "routable_entries_count": sum(1 for entry in manifest.get("entries", []) if entry.get("routable")),
        "blocked_entries_count": sum(1 for entry in manifest.get("entries", []) if not entry.get("routable")),
        "approved_actions_preview": actions[:25],
        "low_confidence_preview": manifest.get("low_confidence", [])[:25],
    }
    handoff_paths["router"] = write_handoff(handoff_dir, "03-router.json", router)
    record_phase(
        "router",
        "completed",
        routable_entries_count=router["routable_entries_count"],
        blocked_entries_count=router["blocked_entries_count"],
    )

    active_gate_failures = manifest.get("active_gate_failures", [])
    execution_ready = bool(manifest.get("next_actions", {}).get("execution_ready"))
    gatekeeper = {
        "target_folder": str(target),
        "snapshot_id": snapshot_id,
        "manifest_path": str(manifest_path),
        "pass": len(manifest.get("manifest_iterations", [])),
        "low_confidence_count": manifest.get("low_confidence_count"),
        "active_gate_failures": active_gate_failures,
        "approved_actions": actions if execution_ready else [],
        "execution_ready": execution_ready,
    }
    handoff_paths["gatekeeper"] = write_handoff(handoff_dir, "04-gatekeeper.json", gatekeeper)
    record_phase(
        "gatekeeper",
        "approved" if execution_ready else "blocked",
        active_gate_failures=active_gate_failures,
        approved_actions=len(actions if execution_ready else []),
    )

    action_path = snapshot_dir / "approved-actions.json"
    write_json(action_path, {"approved_actions": actions if execution_ready else []})

    action_deltas: list[dict[str, Any]] = []
    empty_dirs_removed: list[str] = []
    post_move_manifest_path: str | None = None
    post_move_summary: dict[str, Any] | None = None
    executor_status = "blocked"
    if execution_ready and args.execute:
        action_deltas = execute_actions(actions)
        empty_dirs_removed = prune_empty_directories(target)
        executor_status = "executed"
    elif execution_ready:
        executor_status = "ready_not_executed"

    if executor_status == "executed":
        post_move_manifest = run_manifest(
            target,
            uv_binary=uv_binary,
            include_ignored=args.include_ignored,
            vision=args.vision,
            vision_provider=args.vision_provider,
            vision_model=args.vision_model,
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
        "approved_actions": actions if execution_ready else [],
        "action_deltas": action_deltas,
        "empty_dirs_removed": empty_dirs_removed,
        "post_move_manifest_path": post_move_manifest_path,
        "post_move_summary": post_move_summary,
        "status": executor_status,
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
        "approved_actions": actions if execution_ready else [],
        "action_deltas": action_deltas,
        "status": executor_status,
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
        "handoff_paths": handoff_paths,
        "approved_actions_path": str(action_path),
        "low_confidence_count": manifest.get("low_confidence_count"),
        "active_gate_failures": active_gate_failures,
        "execution_ready": execution_ready,
        "executor_status": executor_status,
        "cache_stats": manifest.get("cache_stats", {}),
        "phase_history": phase_history,
        "post_move_manifest_path": post_move_manifest_path,
        "post_move_summary": post_move_summary,
        "empty_dirs_removed": empty_dirs_removed,
    }
    report_path = snapshot_dir / "run-report.json"
    write_json(report_path, report)

    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
