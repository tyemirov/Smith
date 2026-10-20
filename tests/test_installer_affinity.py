from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


INSTALLER = Path(__file__).resolve().parents[1] / "install-skills"


def skill(root: Path, name: str, deployment: object) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    header = yaml.safe_dump({"name": name, "description": "Installation fixture.", "deployment": deployment}, sort_keys=False)
    (directory / "SKILL.md").write_text("---\n" + header + "---\n\nKeep the supplied input unchanged.\n")
    return directory


def environment(tmp_path: Path, commands: tuple[str, ...]) -> dict[str, str]:
    binaries = tmp_path / "commands"
    binaries.mkdir()
    for command in ("uv", "git", *commands):
        source = shutil.which(command) if command in ("uv", "git", "muse") else "/usr/bin/true"
        assert source
        (binaries / command).symlink_to(source)
    return {**os.environ, "PATH": str(binaries) + ":/usr/bin:/bin", "XDG_CONFIG_HOME": str(tmp_path / "config")}


def invoke(tmp_path: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALLER), "--codex-home", str(tmp_path / "codex"),
         "--claude-home", str(tmp_path / "claude"),
         "--opencode-config-dir", str(tmp_path / "opencode"),
         "--antigravity-home", str(tmp_path / "antigravity"),
         "--bin-dir", str(tmp_path / "bin"), *args],
        env=env, capture_output=True, text=True,
    )


def test_detects_agents_and_applies_affinity_across_sources(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    skill(first, "common", {"include": ["all"]})
    skill(first, "codex-only", {"include": ["openai"]})
    skill(second, "except-codex", {"exclude": ["openai"]})
    env = environment(tmp_path, ("codex", "claude"))
    for _ in range(2):
        result = invoke(tmp_path, env, "--source", str(first), "--source", str(second))
        assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in (tmp_path / "codex/skills").iterdir()) == ["codex-only", "common"]
    assert sorted(p.name for p in (tmp_path / "claude/commands").iterdir()) == ["common.md", "except-codex.md"]
    assert not (tmp_path / "opencode").exists()
    assert not (tmp_path / "antigravity").exists()
    assert not (tmp_path / "config/muse").exists()


def test_no_installed_agents_creates_no_targets(tmp_path: Path) -> None:
    source = tmp_path / "source"
    skill(source, "common", {"include": ["all"]})
    result = invoke(tmp_path, environment(tmp_path, ()), "--source", str(source))
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("codex", "claude", "opencode", "antigravity", "config", "bin"):
        assert not (tmp_path / name).exists()


@pytest.mark.parametrize("deployment", [
    None, {}, {"sometimes": ["openai"]}, {"include": []},
    {"exclude": ["codxe"]}, {"include": ["openai", "openai"]},
    {"include": "all"}, {"include": ["codex"]},
    {"exclude": ["all"]}, {"exclude": ["*"]},
    {"include": ["all", "openai"]}, {"include": ["*", "muse"]},
    {"include": ["openai"], "exclude": ["claude"]},
    {"include": [12]}, {"include": [["muse"]]},
])
def test_invalid_affinity_fails_before_mutation(tmp_path: Path, deployment: object) -> None:
    source = tmp_path / "source"
    skill(source, "a-valid", {"include": ["all"]})
    skill(source, "z-invalid", deployment)
    result = invoke(tmp_path, environment(tmp_path, ("codex",)), "--source", str(source))
    assert result.returncode != 0
    assert "Invalid deployment in" in result.stderr
    assert not (tmp_path / "codex").exists()


@pytest.mark.parametrize("deployment", [
    {"include": ["all"]}, {"include": ["*"]},
    {"include": ["openai", "muse"]}, {"exclude": ["claude"]},
])
def test_deployment_selects_openai(tmp_path: Path, deployment: object) -> None:
    source = tmp_path / "source"
    skill(source, "portable", deployment)
    result = invoke(tmp_path, environment(tmp_path, ("codex",)), "--source", str(source))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "codex/skills/portable").resolve() == source / "portable"


def test_explicit_missing_agent_fails_before_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    skill(source, "common", {"include": ["all"]})
    result = invoke(tmp_path, environment(tmp_path, ()), "--source", str(source), "--target", "muse")
    assert result.returncode != 0
    assert "not installed" in result.stderr
    assert not (tmp_path / "config").exists()


@pytest.mark.parametrize("previously_installed", [False, True])
def test_real_muse_install_preserves_resources_and_honors_exclusion(tmp_path: Path, previously_installed: bool) -> None:
    source = tmp_path / "source"
    package = skill(source, "portable", {"include": ["all"]})
    skill_md = package / "SKILL.md"
    skill_md.write_text(skill_md.read_text().replace("name: portable", 'name: "Portable Skill"'))
    (package / "agents").mkdir()
    (package / "agents/resource.yaml").write_text('steps:\n  - model: "original-model"\n    reasoning_effort: low\n')
    (package / "references").mkdir()
    (package / "references/contract.md").write_text("Preserve this reference.\n")
    skill(source, "foreign-only", {"exclude": ["muse"]})
    env = environment(tmp_path, ("muse",))
    subprocess.run(["git", "init", "-q", str(source)], env=env, check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], env=env, check=True)
    if previously_installed:
        subprocess.run(["muse", "skills", "install", str(source / "foreign-only"), "--json"], env=env, check=True, capture_output=True)
    args = ("--source", str(source), "--target", "muse")
    dry_run = invoke(tmp_path, env, *args, "--dry-run")
    assert dry_run.returncode == 0, dry_run.stderr
    if not previously_installed:
        assert not (tmp_path / "config").exists()
    for _ in range(2):
        result = invoke(tmp_path, env, *args)
        assert result.returncode == 0, result.stdout + result.stderr
    installed = tmp_path / "config/muse/skills"
    assert (installed / "portable/references/contract.md").read_text() == "Preserve this reference.\n"
    if previously_installed:
        import json
        result = subprocess.run(["muse", "skills", "inspect", "foreign-only", "--json"], env=env, capture_output=True, text=True, check=True)
        assert json.loads(result.stdout)["skill"]["activation"] == "off"
    else:
        assert not (installed / "foreign-only").exists()
    inspection = subprocess.run(["muse", "skills", "inspect", str(installed / "portable/SKILL.md"), "--json"], env=env, capture_output=True, text=True)
    assert inspection.returncode == 0, inspection.stderr
    assert '"id": "portable"' in inspection.stdout
    assert "deployment:" in (installed / "portable/SKILL.md").read_text()
    assert 'name: "Portable Skill"' in skill_md.read_text()
    assert 'model: "original-model"' in (installed / "portable/agents/resource.yaml").read_text()
    assert "original-model" in (package / "agents/resource.yaml").read_text()


def test_missing_affinity_fails_before_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    package = skill(source, "missing", {"include": ["all"]})
    path = package / "SKILL.md"
    path.write_text(path.read_text().replace("deployment:\n  include:\n  - all\n", ""))
    result = invoke(tmp_path, environment(tmp_path, ("codex",)), "--source", str(source))
    assert result.returncode != 0
    assert "deployment must contain exactly one of include or exclude" in result.stderr
    assert not (tmp_path / "codex").exists()


def test_duplicate_skill_names_fail_before_mutation(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    skill(first, "same", {"include": ["all"]})
    skill(second, "same", {"include": ["all"]})
    result = invoke(tmp_path, environment(tmp_path, ("codex",)), "--source", str(first), "--source", str(second))
    assert result.returncode != 0
    assert "Duplicate skill names" in result.stderr
    assert not (tmp_path / "codex").exists()


def test_muse_package_bundles_tracked_shared_dependency(tmp_path: Path) -> None:
    source = tmp_path / "source"
    package = skill(source, "portable", {"include": ["muse"]})
    shared = source / "shared"
    shared.mkdir()
    (shared / "contract.py").write_text('VALUE = "shared contract"\n')
    (package / "lib").symlink_to("../shared", target_is_directory=True)
    (package / "run.py").write_text(
        'import sys\nfrom pathlib import Path\n'
        'sys.path.insert(0, str(Path(__file__).parent / "lib"))\n'
        'from contract import VALUE\nprint(VALUE)\n'
    )
    env = environment(tmp_path, ("muse",))
    subprocess.run(["git", "init", "-q", str(source)], env=env, check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], env=env, check=True)
    (shared / "private.txt").write_text("Untracked content must stay outside the package.\n")
    for _ in range(2):
        result = invoke(tmp_path, env, "--source", str(source), "--target", "muse")
        assert result.returncode == 0, result.stdout + result.stderr
    installed = tmp_path / "config/muse/skills/portable"
    source.rename(tmp_path / "unavailable-source")
    result = subprocess.run([sys.executable, "-I", str(installed / "run.py")],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "shared contract"
    assert not (installed / "lib").is_symlink()
    assert not (installed / "lib/private.txt").exists()


@pytest.mark.parametrize("dependency", ["outside", "cycle", "untracked"])
def test_muse_dependency_boundary_fails_before_installation(tmp_path: Path, dependency: str) -> None:
    source = tmp_path / "source"
    package = skill(source, "portable", {"include": ["muse"]})
    if dependency == "outside":
        (tmp_path / "external.txt").write_text("Outside the collection.\n")
        (package / "dependency").symlink_to("../../external.txt")
    elif dependency == "cycle":
        (package / "dependency").symlink_to(".", target_is_directory=True)
    else:
        (package / "dependency").symlink_to("../private.txt")
    env = environment(tmp_path, ("muse",))
    subprocess.run(["git", "init", "-q", str(source)], env=env, check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], env=env, check=True)
    if dependency == "untracked":
        (source / "private.txt").write_text("Untracked content.\n")
    result = invoke(tmp_path, env, "--source", str(source), "--target", "muse")
    assert result.returncode != 0
    assert "Package" in result.stderr
    assert not (tmp_path / "config/muse/skills").exists()
