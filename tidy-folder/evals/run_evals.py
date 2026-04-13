#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
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

    assert freelance["alice-report-card-q2.pdf"]["proposed_destination"] == "Kids/School"
    assert freelance["client-brief-rebrand.docx"]["proposed_destination"] == "Business/Client-Work"
    assert freelance["worksheet-data.xlsx"]["kind"] == "xlsx"
    assert freelance["worksheet-data.xlsx"]["proposed_destination"] == "Business/Client-Work"
    assert evidence_contains(freelance["worksheet-data.xlsx"], "text", "client")
    assert freelance["track01.mp3"]["kind"] == "audio"
    assert freelance["track01.mp3"]["proposed_destination"] == "Music/AI-Songs"
    assert evidence_contains(freelance["track01.mp3"], "metadata", "suno")

    assert polluted["meeting-notes-standup.docx"]["proposed_destination"] == "Projects/Code"
    assert polluted["package.json"]["proposed_destination"] == "Projects/Code"
    assert payloads["polluted-project"]["cache_stats"]["hits"] > 0

    assert retiree["statement.xlsx"]["kind"] == "xlsx"
    assert retiree["statement.xlsx"]["proposed_destination"] == "Finance/Investments"
    assert evidence_contains(retiree["statement.xlsx"], "text", "portfolio")

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
    assert any(
        "project_markers:Projects/Code" in alternative.get("evidence", [])
        for alternative in hidden_marker_entries["notes.txt"].get("alternatives", [])
    )
    assert hidden_marker_entries["notes.txt"]["proposed_destination"] is None
    assert hidden_marker_payload["execution_blocked"] is True

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
    assert nested_generic_entry["proposed_destination"] is None
    assert {
        failure["code"] for failure in nested_generic_payload["active_gate_failures"]
    } >= {"low_confidence_remaining", "specificity_required"}

    generic_projects_payload = run_temp_manifest(
        {"demo-notes.txt": "prototype walkthrough for demo recording\n"}
    )
    generic_projects_entry = entry_map(generic_projects_payload)["demo-notes.txt"]
    assert generic_projects_payload["execution_blocked"] is True
    assert generic_projects_payload["next_actions"]["execution_ready"] is False
    assert generic_projects_entry["proposed_destination"] is None
    assert {
        failure["code"] for failure in generic_projects_payload["active_gate_failures"]
    } >= {"low_confidence_remaining", "specificity_required"}

    controller_report = run_controller(
        {"demo-notes.txt": "prototype walkthrough for demo recording\n"}
    )
    assert controller_report["execution_ready"] is False
    assert controller_report["active_gate_failures"]
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
    assert controller_execute_report["post_move_summary"]["low_confidence_count"] == 0
    assert controller_execute_report["post_move_summary"]["active_gate_failures"] == []
    assert "./inbox" in controller_execute_report["empty_dirs_removed"]

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
