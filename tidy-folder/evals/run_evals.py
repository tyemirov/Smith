#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCANNER = ROOT.parent / "scripts" / "semantic_scan.py"
FIXTURE_BUILDER = ROOT / "fixture_builder.py"
UV = Path("/opt/homebrew/bin/uv")


def build_fixtures() -> None:
    subprocess.run([sys.executable, str(FIXTURE_BUILDER)], check=True)


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


def assert_manifest_contract(payload: dict) -> None:
    assert payload["execution_blocked"] is (payload["low_confidence_count"] > 0)
    dumped = json.dumps(payload)
    assert "Documents-Unknown" not in dumped
    assert "Media-Unknown" not in dumped

    for entry in payload["entries"]:
        if entry["needs_refinement"]:
            assert entry["proposed_destination"] is None
            assert entry["routable"] is False
        else:
            assert entry["proposed_destination"]
            assert entry["routable"] is True

    for blocked in payload["low_confidence"]:
        assert blocked["proposed_destination"] is None


def assert_lightweight_dependencies() -> None:
    head = "\n".join(SCANNER.read_text(encoding="utf-8").splitlines()[:16])
    assert "--with torch" not in head
    assert "--with torchvision" not in head
    assert "transformers>=4.41" not in head


def load_scanner_module():
    spec = importlib.util.spec_from_file_location("tidy_folder_semantic_scan", SCANNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_cache_reuse(module, fixture: Path) -> None:
    paths = list(module.walk_files(fixture))
    taxonomy_hints = module.collect_existing_taxonomy_hints(paths, fixture)
    evidence_cache = {}
    calls = {"count": 0}
    original = module.build_file_evidence

    def wrapped(path, root, vision=False):
        calls["count"] += 1
        return original(path, root, vision=vision)

    module.build_file_evidence = wrapped
    try:
        module.scan_records_with_hints(
            paths,
            root=fixture,
            taxonomy_hints=taxonomy_hints,
            autopilot=True,
            vision=False,
            evidence_cache=evidence_cache,
        )
        first_pass_calls = calls["count"]
        module.scan_records_with_hints(
            paths,
            root=fixture,
            taxonomy_hints=taxonomy_hints,
            autopilot=True,
            vision=False,
            evidence_cache=evidence_cache,
        )
    finally:
        module.build_file_evidence = original

    file_count = sum(1 for path in paths if path.is_file())
    assert first_pass_calls == file_count
    assert calls["count"] == first_pass_calls
    assert len(evidence_cache) == file_count


def main() -> int:
    build_fixtures()
    assert_lightweight_dependencies()

    payloads = {
        "freelance-designer": run_manifest(ROOT / "fixtures" / "freelance-designer" / "test-folder"),
        "polluted-project": run_manifest(ROOT / "fixtures" / "polluted-project" / "test-folder"),
        "retiree-documents": run_manifest(ROOT / "fixtures" / "retiree-documents" / "test-folder"),
    }

    for payload in payloads.values():
        assert_manifest_contract(payload)

    freelance = entry_map(payloads["freelance-designer"])
    assert freelance["alice-report-card-q2.pdf"]["proposed_destination"] == "Kids/School"
    assert freelance["client-brief-rebrand.docx"]["proposed_destination"] == "Business/Client-Work"
    assert freelance["quarterly-client-roster.csv"]["kind"] == "csv"
    assert all(seed["home"] != "Sorted" for seed in payloads["freelance-designer"]["taxonomy_hints"])

    polluted = entry_map(payloads["polluted-project"])
    assert polluted["README.md"]["proposed_destination"] == "Projects/Code"
    assert polluted["package-lock.json"]["kind"] == "json"
    assert polluted["package-lock.json"]["proposed_destination"] == "Projects/Code"
    assert polluted["package.json"]["proposed_destination"] == "Projects/Code"
    assert polluted["random-invoice.pdf"]["proposed_destination"] == "Business/Client-Work"
    assert all("src/components" not in seed["home"] for seed in payloads["polluted-project"]["taxonomy_hints"])

    retiree = entry_map(payloads["retiree-documents"])
    assert retiree["blood-test-results-2024.pdf"]["proposed_destination"] == "Health/Medical"
    assert retiree["pension-statement-q4-2024.pdf"]["proposed_destination"] == "Finance/Investments"
    assert retiree["tax-return-2024.pdf"]["proposed_destination"] == "Finance/Taxes"
    assert all(
        not entry["proposed_destination"] or "Documents" not in entry["proposed_destination"]
        for entry in payloads["retiree-documents"]["entries"]
    )

    module = load_scanner_module()
    assert_cache_reuse(module, ROOT / "fixtures" / "polluted-project" / "test-folder")

    for name, payload in payloads.items():
        print(f"{name}: files={payload['file_count']} low_confidence={payload['low_confidence_count']}")
    print("cache_reuse: ok")
    print("dependency_profile: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
