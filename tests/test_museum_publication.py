"""Exercise the museum skill through public installation and CLI boundaries."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_public_install import install, public_export

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("package", ["museum-catalog", "plugins/tyemirov/skills/museum-catalog"])
def test_plan_and_preview_preserve_personal_metadata(tmp_path: Path, package: str) -> None:
    helper = ROOT / package / "scripts/museum_catalog.py"
    snapshot = {
        "source": {"album_id": "synthetic-album"},
        "photos": [{
            "id": "synthetic-photo", "title": "", "caption": "My personal comment",
            "keywords": ["keep"], "filename": "synthetic.jpg", "width": 20,
            "height": 30, "capturedate": "2000-01-01T00:00:00Z", "favorite": True,
            "album_membership": ["synthetic-album"],
        }],
    }
    manifest = {
        "works": {"work-1": {
            "title": "Example artwork", "artist": "Example artist", "identification": "label",
            "evidence": {field: [{"label_photo_id": "synthetic-label"}] for field in ("title", "artist")},
        }},
        "photos": [{"id": "synthetic-photo", "category": "artwork", "work_id": "work-1"}],
    }
    snapshot_path, manifest_path, plan_path = [tmp_path / name for name in ("inventory.json", "manifest.json", "plan.json")]
    snapshot_path.write_text(json.dumps(snapshot))
    manifest_path.write_text(json.dumps(manifest))
    original = snapshot_path.read_bytes()
    result = subprocess.run(
        [sys.executable, str(helper), "plan", "--snapshot", str(snapshot_path),
         "--manifest", str(manifest_path), "--out", str(plan_path)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    plan = json.loads(plan_path.read_text())
    assert plan["changes"][0]["set"] == {"title": "Example artwork"}
    assert plan["changes"][0]["preserved"] == ["caption"]
    preview = subprocess.run(
        [sys.executable, str(helper), "apply", "--plan", str(plan_path)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert preview.returncode == 0, preview.stderr
    assert json.loads(preview.stdout) == plan["changes"]
    assert snapshot_path.read_bytes() == original
    assert {path.name for path in tmp_path.iterdir()} == {"inventory.json", "manifest.json", "plan.json"}


def test_public_museum_install_contains_only_reusable_resources(tmp_path: Path, public_export: Path) -> None:
    result = install(tmp_path, public_export, "--skill", "museum-catalog")
    assert result.returncode == 0, result.stdout + result.stderr
    skill = tmp_path / "profile/skills/museum-catalog"
    assert skill.resolve() == public_export / "museum-catalog"
    assert (skill / "scripts/museum_catalog.py").is_file()
    assert (skill / "scripts/ocr_labels.swift").is_file()
    assert (skill / "references/manifest.md").is_file()
    assert not (skill / "visits").exists()
    assert not (skill / "CONTEXT.md").exists()
    check = install(tmp_path, public_export, "--skill", "museum-catalog", "--check")
    assert check.returncode == 0, check.stdout + check.stderr
