"""Exercise the museum skill through public installation and CLI boundaries."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_public_install import install, public_export

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["museum-catalog", "plugins/tyemirov/skills/museum-catalog"]
CLI_RUNNER = """
import runpy
import sys
import tempfile
from unittest.mock import patch

platform, helper, *arguments = sys.argv[1:]
sys.platform = platform
sys.argv = [helper, *arguments]
with patch('subprocess.run', side_effect=AssertionError('Native tools must not run in this test')):
    runpy.run_path(helper, run_name='__main__')
"""


def run_helper(helper: Path, arguments: list[str], platform: str, directory: Path) -> subprocess.CompletedProcess[str]:
    """Inject the operating system into the real CLI without permitting native tools."""
    return subprocess.run(
        [sys.executable, "-c", CLI_RUNNER, platform, str(helper), *arguments],
        cwd=directory, capture_output=True, text=True,
    )


@pytest.mark.parametrize("package", PACKAGES)
@pytest.mark.parametrize("platform", ["linux", "win32"])
@pytest.mark.parametrize("arguments", [
    ["sources", "--out", "output.json"],
    ["previews", "--snapshot", "missing.json", "--out", "previews"],
    ["plan", "--snapshot", "missing.json", "--manifest", "missing.json", "--out", "plan.json"],
    ["apply", "--plan", "missing.json", "--apply", "--log", "apply.json"],
])
def test_unsupported_platform_stops_before_io(
    tmp_path: Path, package: str, platform: str, arguments: list[str],
) -> None:
    result = run_helper(ROOT / package / "scripts/museum_catalog.py", arguments, platform, tmp_path)
    assert result.returncode == 2, result.stderr
    assert "requires macOS" in result.stderr
    assert "Traceback" not in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("package", PACKAGES)
def test_help_is_available_on_unsupported_platform(tmp_path: Path, package: str) -> None:
    result = run_helper(ROOT / package / "scripts/museum_catalog.py", ["--help"], "linux", tmp_path)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("package", PACKAGES)
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
    result = run_helper(
        helper, ["plan", "--snapshot", str(snapshot_path), "--manifest", str(manifest_path), "--out", str(plan_path)],
        "darwin", tmp_path,
    )
    assert result.returncode == 0, result.stderr
    plan = json.loads(plan_path.read_text())
    assert plan["changes"][0]["set"] == {"title": "Example artwork"}
    assert plan["changes"][0]["preserved"] == ["caption"]
    preview = run_helper(helper, ["apply", "--plan", str(plan_path)], "darwin", tmp_path)
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
