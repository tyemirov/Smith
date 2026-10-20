from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
UV = shutil.which("uv")


@pytest.fixture
def public_export(tmp_path: Path) -> Path:
    exported = tmp_path / "public-export"
    exported.mkdir()
    shutil.copyfile(ROOT / "install-skills", exported / "install-skills")
    for source in ROOT.iterdir():
        if source.is_dir() and (source / "SKILL.md").is_file():
            shutil.copytree(source, exported / source.name)
    return exported


def install(tmp_path: Path, exported: Path, *options: str) -> subprocess.CompletedProcess[str]:
    commands = tmp_path / "commands"
    commands.mkdir(exist_ok=True)
    codex = commands / "codex"
    if not codex.exists():
        codex.symlink_to("/usr/bin/true")
    return subprocess.run(
        [UV, "run", "--script", str(exported / "install-skills"),
         "--target", "codex", "--target", "bin", "--codex-home", str(tmp_path / "profile"),
         "--bin-dir", str(tmp_path / "bin"), *options],
        env={**os.environ, "PATH": str(commands) + os.pathsep + os.environ["PATH"]},
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("selected", [(), ("--skill", "gitcommit")])
def test_public_export_installs_workflows_with_runtime(tmp_path: Path, public_export: Path, selected: tuple[str, ...]) -> None:
    profile = tmp_path / "profile"
    existing = profile / "skills/unrelated/SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("Keep unrelated skill.")
    config = profile / "config.toml"
    original = '# Personal settings\nmodel = "chosen"\nmodel_reasoning_effort = "low"\n'
    config.write_text(original)
    for extra in ((), (), ("--check",)):
        result = install(tmp_path, public_export, *selected, *extra)
        assert result.returncode == 0, result.stdout + result.stderr
        assert config.read_text() == original
        assert existing.read_text() == "Keep unrelated skill."
        expected_skills = {"gitcommit", "agent-runtime"} if selected else {
            source.name for source in public_export.iterdir()
            if source.is_dir() and (source / "SKILL.md").is_file()
        }
        assert {path.name for path in (profile / "skills").iterdir()} == expected_skills | {"unrelated"}
        assert all((profile / "skills" / name).is_symlink() for name in expected_skills)
        assert (profile / "skills/gitcommit").is_symlink()
        assert (profile / "skills/agent-runtime").is_symlink()
        assert (profile / "agents/mpr-architect.toml").is_file()
        assert "Smith" not in result.stdout + result.stderr
        assert "Warning: tool" not in result.stdout
        assert not (tmp_path / "bin").exists()
    if not selected:
        assert (profile / "agents/whip_reviewer.toml").is_file()


def test_duplicate_runtime_provider_rejected_before_writes(tmp_path: Path, public_export: Path) -> None:
    shutil.copytree(public_export / "agent-runtime", public_export / "other-runtime")
    result = install(tmp_path, public_export, "--skill", "gitcommit")
    assert result.returncode == 1
    assert "Conflicting governance sources" in result.stderr
    assert not (tmp_path / "profile").exists()
    assert not (tmp_path / "bin").exists()


def test_public_runtime_replaces_old_receipt_source(tmp_path: Path, public_export: Path) -> None:
    import json
    import yaml

    old_sources = tmp_path / "old-collection"
    old = old_sources / "mprlab-governor"
    shutil.copytree(public_export / "agent-runtime", old)
    contract = old / "agents/runtime.yaml"
    data = yaml.safe_load(contract.read_text())
    data["instructions"].append("Preserve the old runtime evidence.")
    contract.write_text(yaml.safe_dump(data, sort_keys=False))
    profile = tmp_path / "profile"
    profile.mkdir()
    config = profile / "config.toml"
    original = '# Custom controller\nmodel = "personal-model"\nmodel_reasoning_effort = "low"\n'
    config.write_text(original)
    first = install(tmp_path, public_export, "--source", str(old_sources))
    assert first.returncode == 0, first.stdout + first.stderr
    receipt = profile / ".governance/mprlab-governor.json"
    assert json.loads(receipt.read_text())["source"] == str(old)
    assert "Preserve the old runtime evidence." in (profile / "AGENTS.md").read_text()
    for extra in ((), (), ("--check",)):
        result = install(tmp_path, public_export, "--skill", "gitcommit", *extra)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(receipt.read_text())["source"] == str(public_export / "agent-runtime")
        assert config.read_text() == original
        assert "Preserve the old runtime evidence." not in (profile / "AGENTS.md").read_text()
