from __future__ import annotations

from pathlib import Path

import pytest

from test_agent_orchestration import run_install, runtime_source  # noqa: F401

AGENT = 'name = "sample_reviewer"\ndescription = "Review evidence."\ndeveloper_instructions = "Read the evidence and return findings."\n'


def reviewer_source(tmp_path: Path, name: str = "review-skill", agent_name: str = "sample_reviewer") -> Path:
    source = tmp_path / "review-source"
    skill = source / name
    (skill / "codex/agents").mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Review.\ndeployment:\n  include: [openai]\n---\n")
    (skill / f"codex/agents/{agent_name}.toml").write_text(AGENT.replace("sample_reviewer", agent_name))
    return source


def test_reviewer_install_repeat_check_preserves_other_skills(tmp_path: Path) -> None:
    source = reviewer_source(tmp_path)
    unrelated = tmp_path / "codex/skills/unrelated/SKILL.md"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("Keep this skill.")
    for extra in ((), (), ("--check",)):
        result = run_install(tmp_path, source, "--target", "codex", *extra)
        assert result.returncode == 0, result.stdout + result.stderr
        assert (tmp_path / "codex/agents/sample_reviewer.toml").read_text() == AGENT
        assert unrelated.read_text() == "Keep this skill."


def test_reviewer_preview_and_missing_check_do_not_write(tmp_path: Path) -> None:
    source = reviewer_source(tmp_path)
    preview = run_install(tmp_path, source, "--target", "codex", "--dry-run")
    assert preview.returncode == 0, preview.stderr
    assert "sample_reviewer.toml" in preview.stdout
    assert not (tmp_path / "codex").exists()
    check = run_install(tmp_path, source, "--target", "codex", "--check")
    assert check.returncode == 1
    assert "sample_reviewer.toml" in check.stdout
    assert not (tmp_path / "codex").exists()


@pytest.mark.parametrize("identical", [False, True])
def test_existing_reviewer_conflict_or_identical(tmp_path: Path, identical: bool) -> None:
    source = reviewer_source(tmp_path)
    existing = tmp_path / "codex/agents/sample_reviewer.toml"
    existing.parent.mkdir(parents=True)
    original = AGENT if identical else 'name = "private"\n'
    existing.write_text(original)
    result = run_install(tmp_path, source, "--target", "codex")
    assert result.returncode == (0 if identical else 1), result.stdout + result.stderr
    assert existing.read_text() == original
    if not identical:
        assert not (tmp_path / "codex/skills").exists()


@pytest.mark.parametrize("content", ['name = "wrong"\n', 'name = [', AGENT.replace('description = "Review evidence."', 'description = 4')])
def test_invalid_reviewer_fails_before_writes(tmp_path: Path, content: str) -> None:
    source = reviewer_source(tmp_path)
    (source / "review-skill/codex/agents/sample_reviewer.toml").write_text(content)
    result = run_install(tmp_path, source, "--target", "codex")
    assert result.returncode == 1
    assert not (tmp_path / "codex").exists()


def test_duplicate_reviewer_ownership_fails_before_writes(tmp_path: Path) -> None:
    source = reviewer_source(tmp_path)
    reviewer_source(tmp_path, "second-skill")
    result = run_install(tmp_path, source, "--target", "codex")
    assert result.returncode == 1
    assert not (tmp_path / "codex").exists()


def test_runtime_reviewer_ownership_collision(tmp_path: Path, runtime_source: Path) -> None:
    source = reviewer_source(tmp_path, agent_name="mpr-architect")
    result = run_install(tmp_path, source, "--source", str(runtime_source), "--target", "codex")
    assert result.returncode == 1
    assert not (tmp_path / "codex").exists()


@pytest.mark.parametrize("original", [None, '# Personal settings\nmodel = "my-model"\nmodel_reasoning_effort = "low"\napproval_policy = "never"\n'])
def test_governor_preserves_model_preferences(tmp_path: Path, runtime_source: Path, original: str | None) -> None:
    config = tmp_path / "codex/config.toml"
    if original is not None:
        config.parent.mkdir(parents=True)
        config.write_text(original)
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (config.read_text() if config.exists() else None) == original
    if original is not None:
        config.write_text(original.replace("my-model", "new-user-choice"))
    check = run_install(tmp_path, runtime_source, "--target", "codex", "--check")
    assert check.returncode == 0, check.stdout + check.stderr


def test_force_backs_up_conflicting_reviewer_link(tmp_path: Path) -> None:
    source = reviewer_source(tmp_path)
    private = tmp_path / "private-agent.toml"
    private.write_text("Keep private contents.")
    destination = tmp_path / "codex/agents/sample_reviewer.toml"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(private)
    result = run_install(tmp_path, source, "--target", "codex", "--force")
    assert result.returncode == 0, result.stdout + result.stderr
    assert destination.read_text() == AGENT
    backups = list(destination.parent.glob(".custom-skills-backup-*/sample_reviewer.toml"))
    assert len(backups) == 1
    assert backups[0].is_symlink()
    assert backups[0].readlink() == private
    assert private.read_text() == "Keep private contents."


def test_reviewer_check_detects_edited_file_without_changes(tmp_path: Path) -> None:
    source = reviewer_source(tmp_path)
    destination = tmp_path / "codex/agents/sample_reviewer.toml"
    destination.parent.mkdir(parents=True)
    destination.write_text(AGENT)
    result = run_install(tmp_path, source, "--target", "codex")
    assert result.returncode == 0, result.stderr
    destination.write_text("Edited contents.")
    result = run_install(tmp_path, source, "--target", "codex", "--check")
    assert result.returncode == 1
    assert str(destination) in result.stdout
    assert destination.read_text() == "Edited contents."


def test_installed_governor_owns_agent_without_selected_runtime(tmp_path: Path, runtime_source: Path) -> None:
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stderr
    original = (tmp_path / "codex/agents/mpr-architect.toml").read_bytes()
    source = reviewer_source(tmp_path, agent_name="mpr-architect")
    result = run_install(tmp_path, source, "--target", "codex", "--force")
    assert result.returncode == 1
    assert (tmp_path / "codex/agents/mpr-architect.toml").read_bytes() == original
    assert not (tmp_path / "codex/skills/review-skill").exists()


def test_custom_models_allow_installed_governor_workflow(tmp_path: Path, runtime_source: Path) -> None:
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stderr
    config = tmp_path / "codex/config.toml"
    original = 'model = "chosen-controller"\nmodel_reasoning_effort = "low"\n'
    config.write_text(original)
    workflow = runtime_source / "review-workflow"
    (workflow / "agents").mkdir(parents=True)
    (workflow / "SKILL.md").write_text("---\nname: review-workflow\ndescription: Review workflow.\ndeployment:\n  include: [openai]\n---\n")
    (workflow / "agents/runtime.yaml").write_text("kind: workflow\ngovernance: mprlab-governor\ncontroller:\n  responsibilities: [Own result.]\nsteps:\n  - id: inspect\n    role: explorer\n    execution: conditional_subagent\n    workspace: primary\n    scope: Inspect files.\n")
    for extra in ((), ("--check",)):
        result = run_install(tmp_path, runtime_source, "--target", "codex", "--skill", "review-workflow", *extra)
        assert result.returncode == 0, result.stdout + result.stderr
        assert config.read_text() == original


@pytest.mark.parametrize("parent_kind", ["file", "external-link"])
@pytest.mark.parametrize("extra", [(), ("--force",), ("--check",), ("--dry-run",)])
def test_reviewer_parent_conflict_prevents_all_writes(tmp_path: Path, parent_kind: str, extra: tuple[str, ...]) -> None:
    source = reviewer_source(tmp_path)
    profile = tmp_path / "codex"
    profile.mkdir()
    config = profile / "config.toml"
    original_config = 'model = "personal"\n'
    config.write_text(original_config)
    agents = profile / "agents"
    outside = tmp_path / "outside"
    outside.mkdir()
    if parent_kind == "file":
        agents.write_text("Keep this file.")
    else:
        agents.symlink_to(outside, target_is_directory=True)
    result = run_install(tmp_path, source, "--target", "codex", *extra)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "agents" in result.stderr
    assert not (profile / "skills").exists()
    assert config.read_text() == original_config
    assert not list(outside.iterdir())
    assert {entry.name for entry in profile.iterdir()} == {"agents", "config.toml"}
    if parent_kind == "file":
        assert agents.read_text() == "Keep this file."
    else:
        assert agents.is_symlink()
        assert agents.readlink() == outside
