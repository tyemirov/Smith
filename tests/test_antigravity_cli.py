from __future__ import annotations

from pathlib import Path

import pytest

from test_installer_affinity import INSTALLER, environment, invoke


def test_agy_detects_all_public_skills_and_preserves_desktop_skills(tmp_path: Path) -> None:
    source = INSTALLER.parent
    expected = {path.name for path in source.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()}
    profile = tmp_path / "antigravity"
    desktop = profile / "config/skills"
    desktop.mkdir(parents=True)
    for name in expected:
        (desktop / name).symlink_to(source / name, target_is_directory=True)
    settings = profile / "settings.json"
    original = '{"model": "personal-model", "theme": "personal-theme"}\n'
    settings.write_text(original)
    env = environment(tmp_path, ("agy",))
    check = invoke(tmp_path, env, "--source", str(source), "--target", "antigravity", "--check")
    assert check.returncode == 1, check.stdout + check.stderr
    assert "antigravity-cli/skills" in check.stdout
    assert not (profile / "antigravity-cli").exists()
    for extra in ((), (), ("--check",)):
        result = invoke(tmp_path, env, "--source", str(source), *extra)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Targets: antigravity" in result.stdout
        cli = profile / "antigravity-cli/skills"
        assert {path.name for path in cli.iterdir()} == expected
        assert all((cli / name).resolve() == (source / name).resolve() for name in expected)
        assert (profile / "config/agents/mpr-architect.md").is_file()
        assert (profile / "GEMINI.md").is_file()
        assert settings.read_text() == original
        assert {path.name for path in desktop.iterdir()} == expected
        assert all((desktop / name).is_symlink() and (desktop / name).resolve() == source / name for name in expected)
    for name in ("codex", "claude", "opencode", "config", "bin"):
        assert not (tmp_path / name).exists()


@pytest.mark.parametrize("desktop_command", ["antigravity", "gemini"])
def test_desktop_commands_do_not_satisfy_cli_target(tmp_path: Path, desktop_command: str) -> None:
    env = environment(tmp_path, (desktop_command,))
    source = INSTALLER.parent
    detected = invoke(tmp_path, env, "--source", str(source))
    assert detected.returncode == 0, detected.stdout + detected.stderr
    assert "No supported agents installed" in detected.stdout
    explicit = invoke(tmp_path, env, "--source", str(source), "--target", "antigravity")
    assert explicit.returncode == 1
    assert "agy" in explicit.stderr
    assert not (tmp_path / "antigravity").exists()
