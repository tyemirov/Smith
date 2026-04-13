#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCANNER = ROOT.parent / "scripts" / "semantic_scan.py"
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


def entry_map(payload: dict) -> dict[str, dict]:
    return {Path(entry["source_path"]).name: entry for entry in payload["entries"]}


def find_entry(payload: dict, filename: str) -> dict:
    for entry in payload["entries"]:
        if Path(entry["source_path"]).name == filename:
            return entry
    raise KeyError(filename)


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

    assert retiree["statement.xlsx"]["kind"] == "xlsx"
    assert retiree["statement.xlsx"]["proposed_destination"] == "Finance/Investments"
    assert evidence_contains(retiree["statement.xlsx"], "text", "portfolio")

    if shutil.which("tesseract"):
        assert retiree["scan-001.png"]["proposed_destination"] == "Identity/Passport"
        assert evidence_contains(retiree["scan-001.png"], "ocr", "passport")

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
