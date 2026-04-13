#!/usr/bin/env python3
from __future__ import annotations

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
        for relative_path, content in files.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return run_manifest(root)


def run_controller(files: dict[str, str], *, execute: bool = False) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        for relative_path, content in files.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        command = [sys.executable, str(CONTROLLER), str(root)]
        if execute:
            command.append("--execute")
        proc = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(proc.stdout)
        assert Path(report["snapshot_path"]).exists()
        assert Path(report["manifest_path"]).exists()
        assert Path(report["draft_actions_path"]).exists()
        assert Path(report["approved_actions_path"]).exists()
        for handoff_path in report["handoff_paths"].values():
            assert Path(handoff_path).exists()
        if execute:
            assert report["executor_status"] == "executed"
            assert report["post_move_manifest_path"]
            assert Path(report["post_move_manifest_path"]).exists()
        return report


def entry_map(payload: dict) -> dict[str, dict]:
    return {Path(entry["source_path"]).name: entry for entry in payload["entries"]}


def find_entry(payload: dict, filename: str) -> dict:
    for entry in payload["entries"]:
        if Path(entry["source_path"]).name == filename:
            return entry
    raise KeyError(filename)


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
    assert payload["helper_ready_for_agent_review"] is True
    assert payload["draft_review_state"] == "ready_for_agent_review"
    assert payload["requires_agent_review"] is True
    assert payload["execution_blocked"] is False
    assert payload["next_actions"]["execution_ready"] is True


def main() -> int:
    build_fixtures()

    payloads = {
        "freelance-designer": run_manifest(ROOT / "fixtures" / "freelance-designer" / "test-folder"),
        "polluted-project": run_manifest(ROOT / "fixtures" / "polluted-project" / "test-folder"),
        "retiree-documents": run_manifest(ROOT / "fixtures" / "retiree-documents" / "test-folder"),
    }

    freelance = entry_map(payloads["freelance-designer"])
    retiree = entry_map(payloads["retiree-documents"])
    polluted = entry_map(payloads["polluted-project"])

    for payload in payloads.values():
        assert_manifest_ready(payload)

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
    assert retiree["unknown.dat"]["proposed_destination"] == "Recovery/Unknown-Text"

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

    nested_generic_payload = run_temp_manifest(
        {"Work/Projects/demo-notes.txt": "prototype walkthrough for demo recording\n"}
    )
    nested_generic_entry = entry_map(nested_generic_payload)["demo-notes.txt"]
    assert nested_generic_entry["proposed_destination"] == "Recovery/Unknown-Text"
    assert nested_generic_payload["active_gate_failures"] == []

    generic_projects_payload = run_temp_manifest(
        {"demo-notes.txt": "prototype walkthrough for demo recording\n"}
    )
    generic_projects_entry = entry_map(generic_projects_payload)["demo-notes.txt"]
    assert generic_projects_payload["execution_blocked"] is False
    assert generic_projects_payload["next_actions"]["execution_ready"] is True
    assert generic_projects_entry["proposed_destination"] == "Recovery/Unknown-Text"
    assert generic_projects_payload["active_gate_failures"] == []

    controller_report = run_controller(
        {"demo-notes.txt": "prototype walkthrough for demo recording\n"}
    )
    assert controller_report["execution_ready"] is True
    assert controller_report["helper_ready_for_agent_review"] is True
    assert controller_report["requires_agent_review"] is True
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

    controller_execute_report = run_controller(
        {
            "inbox/tax-return.txt": "IRS tax return 2024\n",
            "inbox/portfolio-summary.txt": "portfolio positions brokerage balance\n",
        },
        execute=True,
    )
    assert controller_execute_report["execution_ready"] is True
    assert controller_execute_report["helper_execution_status"] == "executed"
    assert controller_execute_report["post_move_summary"]["low_confidence_count"] == 0
    assert controller_execute_report["post_move_summary"]["active_gate_failures"] == []
    assert "./inbox" in controller_execute_report["empty_dirs_removed"]

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
        assert report["draft_review_state"] == "blocked_by_run_lock"
        assert report["helper_ready_for_agent_review"] is False
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
        (root / "moving_map/src").mkdir(parents=True, exist_ok=True)
        (root / "moving_map/package.json").write_text('{"name":"moving_map"}\n', encoding="utf-8")
        (root / "moving_map/README.md").write_text("# moving_map\ninteractive map prototype\n", encoding="utf-8")
        (root / "moving_map/src/index.ts").write_text("export const app = 'moving_map';\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(CONTROLLER), str(root), "--execute"],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(proc.stdout)
        assert report["execution_ready"] is True
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
