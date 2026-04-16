#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCANNER = ROOT.parent / "scripts" / "semantic_scan.py"
CONTROLLER = ROOT.parent / "scripts" / "run_tidy_folder.py"
SETUP = ROOT / "setup_fixtures.sh"
UV = Path("/opt/homebrew/bin/uv")
BLANK_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p6k9n8AAAAASUVORK5CYII="
)


def build_fixtures() -> None:
    subprocess.run(["bash", str(SETUP)], check=True)


def run_manifest(fixture: Path) -> dict:
    proc = subprocess.run(
        [str(UV), "run", str(SCANNER), str(fixture), "--manifest", "--autopilot"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def run_temp_manifest(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_files(root, files)
        return run_manifest(root)


def seed_files(root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run_controller_command(root: Path, *extra_args: str, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict]:
    proc = subprocess.run(
        [sys.executable, str(CONTROLLER), str(root), *extra_args],
        check=check,
        capture_output=True,
        text=True,
    )
    report = json.loads(proc.stdout)
    return proc, report


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_snapshot_inventory(report: dict) -> None:
    inventory = report["inventory"]
    assert Path(inventory["tree_path"]).exists()
    assert Path(inventory["files_path"]).exists()
    assert Path(inventory["metadata_path"]).exists()


def assert_controller_artifacts(report: dict, *, expect_manifest: bool) -> None:
    assert Path(report["snapshot_path"]).exists()
    assert Path(report["draft_actions_path"]).exists()
    assert_snapshot_inventory(report)
    if expect_manifest:
        assert Path(report["helper_manifest_path"]).exists()
        assert Path(report["manifest_path"]).exists()
    else:
        assert report["helper_manifest_path"] is None
        assert report["manifest_path"] is None
    if report["move_ledger_path"] is not None:
        assert Path(report["move_ledger_path"]).exists()
    if report["restore_report_path"] is not None:
        assert Path(report["restore_report_path"]).exists()
    for handoff_path in report["handoff_paths"].values():
        assert Path(handoff_path).exists()


def entry_map(payload: dict) -> dict[str, dict]:
    return {Path(entry["source_path"]).name: entry for entry in payload["entries"]}


def find_entry_by_suffix(payload: dict, suffix: str) -> dict:
    normalized = suffix.replace("\\", "/")
    for entry in payload["entries"]:
        if Path(entry["source_path"]).as_posix().endswith(normalized):
            return entry
    raise KeyError(suffix)


def evidence_contains(entry: dict, prefix: str, token: str) -> bool:
    needle = f"{prefix}:{token}"
    return any(needle == item or needle in item for item in entry.get("evidence", []))


def assert_manifest_ready(payload: dict) -> None:
    assert payload["low_confidence_count"] == 0
    assert payload["active_gate_failures"] == []
    assert payload["helper_ready_for_execution"] is True
    assert payload["draft_status"] == "ready_for_execution"
    assert payload["execution_blocked"] is False
    assert payload["execution_ready"] is True
    assert payload["next_actions"]["execution_ready"] is True


def assert_manifest_needs_reconciliation(payload: dict) -> None:
    assert payload["low_confidence_count"] > 0
    assert payload["helper_ready_for_execution"] is False
    assert payload["draft_status"] == "needs_reconciliation"
    assert payload["execution_blocked"] is True
    assert payload["execution_ready"] is False
    assert payload["next_actions"]["execution_ready"] is False


def main() -> int:
    build_fixtures()

    missing_target = subprocess.run(
        [sys.executable, str(CONTROLLER)],
        capture_output=True,
        text=True,
    )
    assert missing_target.returncode == 2
    assert "folder" in missing_target.stderr.lower()

    payloads = {
        "freelance-designer": run_manifest(ROOT / "fixtures" / "freelance-designer" / "test-folder"),
        "polluted-project": run_manifest(ROOT / "fixtures" / "polluted-project" / "test-folder"),
        "retiree-documents": run_manifest(ROOT / "fixtures" / "retiree-documents" / "test-folder"),
    }

    freelance = entry_map(payloads["freelance-designer"])
    retiree = entry_map(payloads["retiree-documents"])
    polluted = entry_map(payloads["polluted-project"])

    assert_manifest_ready(payloads["freelance-designer"])
    assert_manifest_ready(payloads["polluted-project"])
    assert_manifest_needs_reconciliation(payloads["retiree-documents"])
    assert payloads["freelance-designer"]["scan_workers_used"] > 1
    assert payloads["polluted-project"]["scan_workers_used"] > 1

    assert freelance["alice-report-card-q2.pdf"]["proposed_destination"] == "Kids/School"
    assert freelance["client-brief-rebrand.docx"]["proposed_destination"] == "Business/Client-Work"
    assert freelance["recipe-sourdough.pdf"]["proposed_destination"] == "Home/Recipes"
    assert freelance["headshot-2024.jpg"]["proposed_destination"] == "Career/Headshots"
    assert freelance["screenshot-2024-03-15.png"]["proposed_destination"] == "Screen-Captures"
    assert freelance["screenshot-2024-03-18.png"]["proposed_destination"] == "Screen-Captures"
    assert freelance["worksheet-data.xlsx"]["kind"] == "xlsx"
    assert freelance["worksheet-data.xlsx"]["proposed_destination"] == "Business/Client-Work"
    assert evidence_contains(freelance["worksheet-data.xlsx"], "text", "client")
    assert freelance["track01.mp3"]["kind"] == "audio"
    assert freelance["track01.mp3"]["proposed_destination"] == "Music/AI-Songs"
    assert evidence_contains(freelance["track01.mp3"], "metadata", "suno")

    assert polluted["meeting-notes-standup.docx"]["proposed_destination"] == "Projects/Code"
    assert polluted["package.json"]["proposed_destination"] == "Projects/Code"
    assert polluted["screenshot 2024-01-15 at 3.45.12 PM.png"]["proposed_destination"] == "Projects/Code"

    assert retiree["statement.xlsx"]["kind"] == "xlsx"
    assert retiree["statement.xlsx"]["proposed_destination"] == "Finance/Investments"
    assert evidence_contains(retiree["statement.xlsx"], "text", "portfolio")
    assert retiree["will-and-testament-2022.pdf"]["proposed_destination"] == "Legal/Estate-Planning"
    assert retiree["power-of-attorney.pdf"]["proposed_destination"] == "Legal/Estate-Planning"
    assert retiree["auto-insurance-renewal.pdf"]["proposed_destination"] == "Auto/Insurance"
    assert retiree["garden-layout-2024.pdf"]["proposed_destination"] == "Home/Garden"
    assert retiree["woodworking-plans-bookshelf.pdf"]["proposed_destination"] == "Hobbies/Woodworking"
    assert retiree["grandkids-birthday-2024.heic"]["proposed_destination"] == "Family/Memories"
    assert retiree["grandkids-recital-video.mp4"]["proposed_destination"] == "Family/Memories"
    assert retiree["resume-1998.docx"]["proposed_destination"] == "Career/Engineering"
    assert retiree["unknown.dat"]["proposed_destination"] is None
    assert retiree["unknown.dat"]["attribution"]["primary_signal"] == "Recovery/Unknown-Text"

    if shutil.which("tesseract"):
        assert retiree["scan-001.png"]["proposed_destination"] == "Identity/Passport"
        assert evidence_contains(retiree["scan-001.png"], "ocr", "passport")

    hidden_marker_payload = run_temp_manifest(
        {
            ".gitignore": "node_modules/\ndist/\n",
            "notes.txt": "prototype walkthrough for demo recording\n",
        }
    )
    hidden_marker_entries = entry_map(hidden_marker_payload)
    assert hidden_marker_entries[".gitignore"]["proposed_destination"] == "Projects/Code"
    assert any(
        hint.get("source") == "project_markers"
        for hint in hidden_marker_entries["notes.txt"]["attribution"].get("taxonomy_hints", [])
    )
    assert hidden_marker_entries["notes.txt"]["proposed_destination"] == "Projects/Code"
    assert hidden_marker_payload["execution_blocked"] is False
    assert hidden_marker_payload["helper_ready_for_execution"] is True

    hidden_project_files_payload = run_temp_manifest(
        {
            "demo/package.json": '{"name":"demo"}\n',
            "demo/.env": "API_KEY=demo\n",
            "demo/.editorconfig": "root = true\n",
        }
    )
    hidden_env = find_entry_by_suffix(hidden_project_files_payload, "demo/.env")
    hidden_editorconfig = find_entry_by_suffix(hidden_project_files_payload, "demo/.editorconfig")
    assert hidden_env["proposed_destination"] == "Projects/Demo"
    assert hidden_editorconfig["proposed_destination"] == "Projects/Demo"

    multi_project_payload = run_temp_manifest(
        {
            "moving_map/package.json": '{"name":"moving_map"}\n',
            "moving_map/README.md": "# moving_map\ninteractive map prototype\n",
            "moving_map/src/index.ts": "export const app = 'moving_map';\n",
            "chess-p2p/package.json": '{"name":"chess-p2p"}\n',
            "chess-p2p/README.md": "# chess-p2p\npeer to peer chess demo\n",
            "chess-p2p/src/index.ts": "export const app = 'chess-p2p';\n",
        }
    )
    moving_map_package = find_entry_by_suffix(multi_project_payload, "moving_map/package.json")
    chess_package = find_entry_by_suffix(multi_project_payload, "chess-p2p/package.json")
    moving_map_readme = find_entry_by_suffix(multi_project_payload, "moving_map/README.md")
    chess_readme = find_entry_by_suffix(multi_project_payload, "chess-p2p/README.md")
    assert moving_map_package["proposed_destination"] == "Projects/Moving-Map"
    assert chess_package["proposed_destination"] == "Projects/Chess-P2P"
    assert moving_map_readme["proposed_destination"] == "Projects/Moving-Map"
    assert chess_readme["proposed_destination"] == "Projects/Chess-P2P"

    same_leaf_project_payload = run_temp_manifest(
        {
            "alpha/site/package.json": '{"name":"alpha-site"}\n',
            "alpha/site/src/index.ts": "export const alpha = 'site';\n",
            "beta/site/package.json": '{"name":"beta-site"}\n',
            "beta/site/src/index.ts": "export const beta = 'site';\n",
        }
    )
    alpha_site_package = find_entry_by_suffix(same_leaf_project_payload, "alpha/site/package.json")
    beta_site_package = find_entry_by_suffix(same_leaf_project_payload, "beta/site/package.json")
    assert alpha_site_package["proposed_destination"] == "Projects/Alpha-Site"
    assert beta_site_package["proposed_destination"] == "Projects/Beta-Site"
    assert alpha_site_package["proposed_destination"] != beta_site_package["proposed_destination"]

    nested_generic_payload = run_temp_manifest(
        {"Work/Projects/demo-notes.txt": "prototype walkthrough for demo recording\n"}
    )
    nested_generic_entry = entry_map(nested_generic_payload)["demo-notes.txt"]
    assert_manifest_needs_reconciliation(nested_generic_payload)
    assert nested_generic_entry["proposed_destination"] is None
    assert nested_generic_entry["attribution"]["primary_signal"] == "Recovery/Unknown-Text"

    generic_projects_payload = run_temp_manifest(
        {"demo-notes.txt": "prototype walkthrough for demo recording\n"}
    )
    generic_projects_entry = entry_map(generic_projects_payload)["demo-notes.txt"]
    assert_manifest_needs_reconciliation(generic_projects_payload)
    assert generic_projects_entry["proposed_destination"] is None
    assert generic_projects_entry["attribution"]["primary_signal"] == "Recovery/Unknown-Text"

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_files(
            root,
            {
                "inbox/tax-return.txt": "IRS tax return 2024\n",
                "inbox/portfolio-summary.txt": "portfolio positions brokerage balance\n",
            },
        )
        _draft_proc, controller_report = run_controller_command(root)
        assert_controller_artifacts(controller_report, expect_manifest=True)
        assert controller_report["execution_ready"] is True
        assert controller_report["helper_ready_for_execution"] is True
        assert controller_report["draft_status"] == "ready_for_execution"
        assert controller_report["active_gate_failures"] == []
        assert set(controller_report["handoff_paths"]) == {
            "supervisor",
            "preflight",
            "scout",
            "router",
            "gatekeeper",
            "executor",
            "audit",
        }
        router_handoff = load_json(controller_report["handoff_paths"]["router"])
        gatekeeper_handoff = load_json(controller_report["handoff_paths"]["gatekeeper"])
        draft_actions = load_json(controller_report["draft_actions_path"])
        assert router_handoff["status"] == "ready_for_execution"
        assert gatekeeper_handoff["status"] == "cleared_for_execution"
        assert draft_actions["execution_ready"] is True
        assert len(draft_actions["draft_actions"]) == 2

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_files(
            root,
            {
                "inbox/tax-return.txt": "IRS tax return 2024\n",
                "inbox/portfolio-summary.txt": "portfolio positions brokerage balance\n",
            },
        )
        _execute_proc, controller_execute_report = run_controller_command(root, "--execute")
        assert_controller_artifacts(controller_execute_report, expect_manifest=True)
        assert controller_execute_report["execution_ready"] is True
        assert controller_execute_report["executor_status"] == "executed"
        assert controller_execute_report["helper_execution_status"] == "executed"
        assert controller_execute_report["post_move_summary"]["low_confidence_count"] == 0
        assert controller_execute_report["post_move_summary"]["active_gate_failures"] == []
        assert "./inbox" in controller_execute_report["empty_dirs_removed"]

        move_ledger = load_json(controller_execute_report["move_ledger_path"])
        moved_destinations = [
            Path(delta["destination_path"])
            for delta in move_ledger["action_deltas"]
            if delta["status"] == "moved"
        ]
        assert moved_destinations

        _restore_proc, restore_report = run_controller_command(
            root,
            "--restore-snapshot",
            controller_execute_report["snapshot_id"],
        )
        assert_controller_artifacts(restore_report, expect_manifest=False)
        assert restore_report["executor_status"] == "restored"
        assert restore_report["restore_status"] in {"restored", "restored_with_warnings"}
        assert restore_report["restore_snapshot_id"] == controller_execute_report["snapshot_id"]
        assert (root / "inbox/tax-return.txt").exists()
        assert (root / "inbox/portfolio-summary.txt").exists()
        assert all(not path.exists() for path in moved_destinations)
        restore_artifact = load_json(restore_report["restore_report_path"])
        assert restore_artifact["restore_snapshot_id"] == controller_execute_report["snapshot_id"]
        assert restore_artifact["restored_moves"] == len(moved_destinations)

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "inbox").mkdir(parents=True, exist_ok=True)
        (root / "inbox/tax-return.txt").write_text("IRS tax return 2024\n", encoding="utf-8")
        (root / "inbox/portfolio-summary.txt").write_text("portfolio positions brokerage balance\n", encoding="utf-8")
        first = json.loads(
            subprocess.run(
                [sys.executable, str(CONTROLLER), str(root)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        second = json.loads(
            subprocess.run(
                [sys.executable, str(CONTROLLER), str(root)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        assert first["cache_stats"]["misses"] > 0
        assert second["cache_stats"]["hits"] > 0

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        cache_path = root / "semantic-cache.json"
        (root / "tax-return.txt").write_text("IRS tax return 2024\n", encoding="utf-8")
        first = json.loads(
            subprocess.run(
                [
                    str(UV),
                    "run",
                    str(SCANNER),
                    str(root),
                    "--manifest",
                    "--autopilot",
                    "--cache-file",
                    str(cache_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        second = json.loads(
            subprocess.run(
                [
                    str(UV),
                    "run",
                    str(SCANNER),
                    str(root),
                    "--manifest",
                    "--autopilot",
                    "--cache-file",
                    str(cache_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        (root / "Finance").mkdir(parents=True, exist_ok=True)
        shutil.move(str(root / "tax-return.txt"), str(root / "Finance/tax-return.txt"))
        third = json.loads(
            subprocess.run(
                [
                    str(UV),
                    "run",
                    str(SCANNER),
                    str(root),
                    "--manifest",
                    "--autopilot",
                    "--cache-file",
                    str(cache_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        assert first["cache_stats"]["misses"] > 0
        assert second["cache_stats"]["hits"] > 0
        assert third["cache_stats"]["hits"] > 0

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "demo-notes.txt").write_text("prototype walkthrough for demo recording\n", encoding="utf-8")
        lock_dir = root / ".tidy-folder-snapshots"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / "active-run.lock.json"
        fresh_lock = {
            "run_id": "existing-run",
            "target_folder": str(root),
            "snapshot_path": str(lock_dir / "existing-run"),
            "owner": "other@host:999",
            "phase": "router",
            "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "pid": 999,
        }
        lock_path.write_text(json.dumps(fresh_lock, indent=2) + "\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(CONTROLLER), str(root)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 2
        report = json.loads(proc.stdout)
        assert report["draft_status"] == "blocked_by_run_lock"
        assert report["helper_ready_for_execution"] is False
        assert report["run_lock_released"] is False
        assert Path(report["draft_actions_path"]).exists()
        assert any(
            failure["code"] == "preflight_conflicting_run_lock"
            for failure in report["active_gate_failures"]
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "demo-notes.txt").write_text("prototype walkthrough for demo recording\n", encoding="utf-8")
        lock_dir = root / ".tidy-folder-snapshots"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / "active-run.lock.json"
        stale_lock = {
            "run_id": "stale-run",
            "target_folder": str(root),
            "snapshot_path": str(lock_dir / "stale-run"),
            "owner": "other@host:998",
            "phase": "scout",
            "started_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
            "pid": 998,
        }
        lock_path.write_text(json.dumps(stale_lock, indent=2) + "\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(CONTROLLER), str(root), "--lease-seconds", "1"],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(proc.stdout)
        assert report["lock_takeover_artifact"]
        takeover_artifact = Path(report["lock_takeover_artifact"])
        assert takeover_artifact.exists()
        takeover = json.loads(takeover_artifact.read_text(encoding="utf-8"))
        assert takeover["code"] == "stale_run_lock_takeover"
        assert report["run_lock_released"] is True
        assert not Path(report["run_lock_path"]).exists()

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "passport.png").write_bytes(BLANK_PNG_BYTES)
        helper_payload = run_manifest(root)
        helper_passport = entry_map(helper_payload)["passport.png"]
        assert helper_payload["execution_ready"] is True
        assert helper_passport["proposed_destination"] == "Identity/Passport"

        _controller_proc, controller_report = run_controller_command(root)
        assert_controller_artifacts(controller_report, expect_manifest=True)
        assert controller_report["helper_ready_for_execution"] is True
        assert controller_report["execution_ready"] is False
        assert controller_report["helper_execution_status"] == "blocked_by_controller_review"
        assert any(
            failure["code"] == "controller_sensitive_requires_direct_evidence"
            for failure in controller_report["active_gate_failures"]
        )
        reviewed_manifest = load_json(controller_report["manifest_path"])
        reviewed_passport = entry_map(reviewed_manifest)["passport.png"]
        assert reviewed_passport["proposed_destination"] is None
        assert reviewed_passport["controller_review"]["decision"] == "block"

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "moving_map/src").mkdir(parents=True, exist_ok=True)
        (root / "moving_map/package.json").write_text('{"name":"moving_map"}\n', encoding="utf-8")
        (root / "moving_map/README.md").write_text("# moving_map\ninteractive map prototype\n", encoding="utf-8")
        (root / "moving_map/src/index.ts").write_text("export const app = 'moving_map';\n", encoding="utf-8")
        _execute_proc, report = run_controller_command(root, "--execute")
        assert report["executor_status"] == "executed"
        assert (root / "Projects/Moving-Map/package.json").exists()
        assert (root / "Projects/Moving-Map/README.md").exists()
        assert (root / "Projects/Moving-Map/src/index.ts").exists()
        assert not (root / "Projects/Moving-Map/index.ts").exists()

    print(
        "freelance-designer:",
        f"files={payloads['freelance-designer']['file_count']}",
        f"low_confidence={payloads['freelance-designer']['low_confidence_count']}",
    )
    print(
        "polluted-project:",
        f"files={payloads['polluted-project']['file_count']}",
        f"low_confidence={payloads['polluted-project']['low_confidence_count']}",
    )
    print(
        "retiree-documents:",
        f"files={payloads['retiree-documents']['file_count']}",
        f"low_confidence={payloads['retiree-documents']['low_confidence_count']}",
    )
    print("semantic-extraction-evals: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
