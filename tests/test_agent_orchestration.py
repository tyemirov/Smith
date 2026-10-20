from __future__ import annotations

import hashlib
import os
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install-skills"
GOVERNOR = ROOT / "agent-runtime"


@pytest.fixture
def runtime_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    package = source / "governor-test"
    (package / "agents").mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\nname: governor-test\ndescription: Test governance.\n"
        "deployment:\n  include: [all]\n---\n"
    )
    (package / "agents/install.toml").write_text(
        '[runtime]\ncontract = "agents/runtime.yaml"\nrenderer = "agent_runtime.py"\n'
    )
    renderer = GOVERNOR / "agent_runtime.py"
    (package / "agent_runtime.py").write_text(renderer.read_text() if renderer.exists() else "")
    contract = {
        "kind": "governance", "id": "mprlab-governor",
        "instructions": ["Obey repository instructions.", "Use the primary checkout."],
        "checkpoints": {
            "before_plan": "Before a substantial plan, request an independent architect review.",
            "repeated_error": "After an unexpected failure recurs, review the failed hypothesis.",
            "before_done": "Before substantial task completion, review the diff and validation evidence.",
        },
        "roles": {
            role: {"name": f"mpr-{role}", "description": f"Handle {role} tasks.",
                   "access": "write" if role == "worker" else "read",
                   "instructions": [f"Complete the assigned {role} task."]}
            for role in ("explorer", "worker", "researcher", "architect")
        },
        "hosts": {
            host: {"adapter": adapter, "instructions_file": instructions,
                   "agents_dir": agents,
                   "controller": {"model": "gpt-6.1-sol" if host == "openai" else "inherit",
                                  "reasoning_effort": "high" if host == "openai" else "inherit"},
                   "roles": {role: {"model": model if host == "openai" else "inherit",
                                    "reasoning_effort": effort if host in ("openai", "claude", "muse") else "inherit"}
                             for role, model, effort in (
                                 ("explorer", "gpt-6-luna", "medium"),
                                 ("worker", "gpt-6.1-sol", "medium"),
                                 ("researcher", "gpt-6-luna", "medium"),
                                 ("architect", "gpt-6-astra", "high"))}}
            for host, adapter, instructions, agents in (
                ("openai", "codex", "AGENTS.md", "agents"),
                ("claude", "claude", "CLAUDE.md", "agents"),
                ("opencode", "opencode", "AGENTS.md", "agents"),
                ("antigravity", "antigravity", "GEMINI.md", "config/agents"),
                ("muse", "agent_read", None, "governance"))
        },
    }
    (package / "agents/runtime.yaml").write_text(yaml.safe_dump(contract, sort_keys=False))
    return source


def run_install(tmp_path: Path, source: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    commands = tmp_path / "commands"
    commands.mkdir(parents=True, exist_ok=True)
    for name in ("codex", "claude", "opencode", "agy", "muse"):
        command = commands / name
        if not command.exists():
            command.symlink_to("/usr/bin/true")
    return subprocess.run(
        [str(INSTALLER), "--source", str(source),
         "--codex-home", str(tmp_path / "codex"),
         "--claude-home", str(tmp_path / "claude"),
         "--opencode-config-dir", str(tmp_path / "opencode"),
         "--antigravity-home", str(tmp_path / "antigravity"),
         "--muse-home", str(tmp_path / "muse"), *extra],
        env={**os.environ, "PATH": str(commands) + os.pathsep + os.environ["PATH"]},
        capture_output=True, text=True,
    )


def fingerprints(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def test_codex_install_preserves_unowned_settings_and_is_idempotent(tmp_path: Path, runtime_source: Path) -> None:
    profile = tmp_path / "codex"
    profile.mkdir()
    original = '# Personal config.\nmodel = "old"\n# Keep this comment.\napproval_policy = "never"\nsandbox_mode = "danger-full-access"\n\n[mcp_servers.private]\ncommand = "custom"\n'
    (profile / "config.toml").write_text(original)
    (profile / "AGENTS.md").write_text("Keep my global instructions.\n")
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stdout + result.stderr
    config = (profile / "config.toml").read_text()
    assert '# Keep this comment.\napproval_policy = "never"' in config
    data = tomllib.loads(config)
    assert data["model"] == "old"
    assert "model_reasoning_effort" not in data
    assert config == original
    assert data["mcp_servers"]["private"]["command"] == "custom"
    assert data["sandbox_mode"] == "danger-full-access"
    assert (profile / "AGENTS.md").read_text().startswith("Keep my global instructions.\n")
    architect = tomllib.loads((profile / "agents/mpr-architect.toml").read_text())
    assert architect["model"] == "gpt-6-astra"
    assert architect["sandbox_mode"] == "read-only"
    before = fingerprints(profile)
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stdout + result.stderr
    assert fingerprints(profile) == before


def test_preview_and_check_do_not_install(tmp_path: Path, runtime_source: Path) -> None:
    preview = run_install(tmp_path, runtime_source, "--target", "codex", "--dry-run")
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert "gpt-6-astra" in preview.stdout
    assert not (tmp_path / "codex").exists()
    check = run_install(tmp_path, runtime_source, "--target", "codex", "--check")
    assert check.returncode == 1, check.stdout + check.stderr
    assert not (tmp_path / "codex").exists()


def test_owned_agent_collision_stops_before_any_profile_change(tmp_path: Path, runtime_source: Path) -> None:
    agents = tmp_path / "codex/agents"
    agents.mkdir(parents=True)
    (agents / "mpr-architect.toml").write_text('model = "personal-model"\n')
    before = fingerprints(tmp_path / "codex")
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode != 0
    assert "Conflict" in result.stderr
    assert fingerprints(tmp_path / "codex") == before


def test_all_native_renderers_keep_host_model_inheritance(tmp_path: Path, runtime_source: Path) -> None:
    result = run_install(tmp_path, runtime_source, "--target", "codex", "--target", "claude",
                         "--target", "opencode", "--target", "antigravity")
    assert result.returncode == 0, result.stdout + result.stderr
    for host, path in (("claude", "agents/mpr-architect.md"),
                       ("opencode", "agents/mpr-architect.md"),
                       ("antigravity", "config/agents/mpr-architect.md")):
        content = (tmp_path / host / path).read_text()
        header = yaml.safe_load(content.split("---", 2)[1])
        if host == "opencode":
            assert "model" not in header
        else:
            assert header["model"] == "inherit"
        assert "gpt-6-astra" not in content


@pytest.mark.parametrize("mutation", ["escape", "unknown", "duplicate", "bad_effort", "unknown_role"])
def test_invalid_contract_is_rejected_before_installation(tmp_path: Path, runtime_source: Path, mutation: str) -> None:
    path = runtime_source / "governor-test/agents/runtime.yaml"
    data = yaml.safe_load(path.read_text())
    if mutation == "escape":
        data["hosts"]["openai"]["agents_dir"] = "../escape"
    elif mutation == "unknown":
        data["approval_policy"] = "never"
    elif mutation == "bad_effort":
        data["hosts"]["openai"]["roles"]["architect"]["reasoning_effort"] = "maximum"
    elif mutation == "unknown_role":
        data["hosts"]["openai"]["roles"]["archtect"] = data["hosts"]["openai"]["roles"].pop("architect")
    path.write_text(yaml.safe_dump(data))
    if mutation == "duplicate":
        path.write_text(path.read_text() + "kind: governance\n")
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode != 0
    assert not (tmp_path / "codex").exists()


def test_installed_governance_dependency_resolves_workflow_roles(tmp_path: Path, runtime_source: Path) -> None:
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stdout + result.stderr
    workflow = runtime_source / "workflow-test"
    (workflow / "agents").mkdir(parents=True)
    (workflow / "SKILL.md").write_text("---\nname: workflow-test\ndescription: Test workflow.\ndeployment:\n  include: [openai]\n---\n")
    (workflow / "agents/runtime.yaml").write_text(yaml.safe_dump({
        "kind": "workflow", "governance": "mprlab-governor",
        "controller": {"responsibilities": ["Own the final result."]},
        "steps": [{"id": "inspect", "role": "explorer", "execution": "conditional_subagent",
                   "workspace": "primary", "scope": "Inspect the assigned files."}],
    }))
    workflow_collection = tmp_path / "workflows"
    workflow_collection.mkdir()
    workflow.rename(workflow_collection / workflow.name)
    for profile_root, expected in ((tmp_path, 0), (tmp_path / "fresh", 1)):
        result = run_install(profile_root, workflow_collection, "--target", "codex", "--skill", "workflow-test")
        assert result.returncode == expected, result.stdout + result.stderr
    assert not (tmp_path / "fresh/codex").exists()


def test_workflow_rejects_inline_models(tmp_path: Path, runtime_source: Path) -> None:
    workflow = runtime_source / "workflow-test"
    (workflow / "agents").mkdir(parents=True)
    (workflow / "SKILL.md").write_text("---\nname: workflow-test\ndescription: Test workflow.\ndeployment:\n  include: [openai]\n---\n")
    (workflow / "agents/runtime.yaml").write_text("kind: workflow\ngovernance: mprlab-governor\ncontroller:\n  responsibilities: [Inspect]\nsteps:\n  - id: inspect\n    role: explorer\n    execution: conditional_subagent\n    workspace: primary\n    scope: Inspect files.\n    model: retired-model\n")
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode != 0
    assert not (tmp_path / "codex").exists()


def test_migrated_source_and_plugin_contracts_match() -> None:
    collection = ROOT
    for name in ("gitcommit", "gitrelease", "tidy-folder"):
        path = Path(name) / "agents/runtime.yaml"
        source = (collection / path).read_bytes()
        assert source == (collection / "plugins/tyemirov/skills" / path).read_bytes()
        data = yaml.safe_load(source)
        assert data["kind"] == "workflow"
        assert data["governance"] == "mprlab-governor"
        assert all("model" not in step and "reasoning_effort" not in step for step in data["steps"])


def test_cross_host_conflict_is_detected_before_other_host_writes(tmp_path: Path, runtime_source: Path) -> None:
    agents = tmp_path / "claude/agents"
    agents.mkdir(parents=True)
    (agents / "mpr-worker.md").write_text("Personal agent.\n")
    result = run_install(tmp_path, runtime_source, "--target", "codex", "--target", "claude")
    assert result.returncode != 0
    assert not (tmp_path / "codex").exists()
    assert (agents / "mpr-worker.md").read_text() == "Personal agent.\n"


def test_model_update_regenerates_only_owned_outputs(tmp_path: Path, runtime_source: Path) -> None:
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stderr
    path = runtime_source / "governor-test/agents/runtime.yaml"
    data = yaml.safe_load(path.read_text())
    data["hosts"]["openai"]["roles"]["worker"]["model"] = "next-supported-model"
    path.write_text(yaml.safe_dump(data))
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stderr
    worker = tomllib.loads((tmp_path / "codex/agents/mpr-worker.toml").read_text())
    assert worker["model"] == "next-supported-model"
    result = run_install(tmp_path, runtime_source, "--target", "codex", "--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_renderer_cannot_change_approval_settings(tmp_path: Path, runtime_source: Path) -> None:
    renderer = runtime_source / "governor-test/agent_runtime.py"
    with renderer.open("a") as stream:
        stream.write('\n_original_render = render\ndef render(contract, target):\n    return _original_render(contract, target) + [{"kind": "toml", "path": "config.toml", "values": {"approval_policy": "never"}}]\n')
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode != 0
    assert "scope is limited" in result.stderr
    assert not (tmp_path / "codex").exists()


def test_malformed_managed_markers_stop_before_writes(tmp_path: Path, runtime_source: Path) -> None:
    profile = tmp_path / "codex"
    profile.mkdir()
    (profile / "AGENTS.md").write_text("<!-- BEGIN MPRLAB-ORCHESTRATION -->\nMissing end.\n")
    before = fingerprints(profile)
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode != 0
    assert fingerprints(profile) == before


@pytest.mark.parametrize("drift", ["instructions", "controller"])
def test_workflow_dependency_checks_shared_bootstrap(tmp_path: Path, runtime_source: Path, drift: str) -> None:
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode == 0, result.stderr
    workflow = runtime_source / "workflow-test"
    (workflow / "agents").mkdir(parents=True)
    (workflow / "SKILL.md").write_text("---\nname: workflow-test\ndescription: Test workflow.\ndeployment:\n  include: [openai]\n---\n")
    (workflow / "agents/runtime.yaml").write_text("kind: workflow\ngovernance: mprlab-governor\ncontroller:\n  responsibilities: [Own result.]\nsteps:\n  - id: inspect\n    role: explorer\n    execution: conditional_subagent\n    workspace: primary\n    scope: Inspect files.\n")
    workflow_collection = tmp_path / "workflows"
    workflow_collection.mkdir()
    workflow.rename(workflow_collection / workflow.name)
    result = run_install(tmp_path, workflow_collection, "--target", "codex", "--skill", "workflow-test")
    assert result.returncode == 0, result.stderr
    if drift == "instructions":
        (tmp_path / "codex/AGENTS.md").unlink()
    else:
        (tmp_path / "codex/config.toml").write_text('model = "old-controller"\n')
    result = run_install(tmp_path, workflow_collection, "--target", "codex", "--skill", "workflow-test", "--check")
    if drift == "instructions":
        assert result.returncode != 0
        assert "reinstall Governor" in result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert (tmp_path / "codex/config.toml").read_text() == 'model = "old-controller"\n'


def test_binary_check_detects_missing_links_without_writes(tmp_path: Path, runtime_source: Path) -> None:
    tool = runtime_source / "mprlab-governor/scripts/check-ste"
    tool.parent.mkdir(parents=True)
    tool.write_text("test binary source")
    binary_root = tmp_path / "bin"
    result = run_install(tmp_path, runtime_source, "--target", "bin", "--bin-dir", str(binary_root), "--check")
    assert result.returncode == 1, result.stdout + result.stderr
    assert not binary_root.exists()


def add_maintenance_reference(source: Path) -> Path:
    package = source / "governor-test"
    reference = package / "references/lifecycle.md"
    reference.parent.mkdir()
    reference.write_text("# Lifecycle\n\nAgents own qualification and evidence collection.\n")
    metadata = package / "agents/install.toml"
    metadata.write_text(metadata.read_text() + 'references = ["references/lifecycle.md"]\n')
    runtime = package / "agents/runtime.yaml"
    data = yaml.safe_load(runtime.read_text())
    data["maintenance"] = "references/lifecycle.md"
    runtime.write_text(yaml.safe_dump(data, sort_keys=False))
    return reference


def test_maintenance_policy_is_discoverable_on_every_host(tmp_path: Path, runtime_source: Path) -> None:
    reference = add_maintenance_reference(runtime_source)
    result = run_install(tmp_path, runtime_source, "--target", "codex", "--target", "claude",
                         "--target", "opencode", "--target", "antigravity")
    assert result.returncode == 0, result.stdout + result.stderr
    for host, instructions, agent in (
        ("codex", "AGENTS.md", "agents/mpr-architect.toml"),
        ("claude", "CLAUDE.md", "agents/mpr-architect.md"),
        ("opencode", "AGENTS.md", "agents/mpr-architect.md"),
        ("antigravity", "GEMINI.md", "config/agents/mpr-architect.md"),
    ):
        assert str(reference) in (tmp_path / host / instructions).read_text()
        assert str(reference) in (tmp_path / host / agent).read_text()
        assert "orchestration maintenance" in (tmp_path / host / instructions).read_text()
    result = run_install(tmp_path, runtime_source, "--target", "muse", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"maintenance"' in result.stdout
    assert str(reference) in result.stdout
    assert not (tmp_path / "muse").exists()


@pytest.mark.parametrize("path", ["../outside.md", "references/absent.md"])
def test_invalid_maintenance_reference_stops_before_writes(tmp_path: Path, runtime_source: Path, path: str) -> None:
    package = runtime_source / "governor-test"
    runtime = package / "agents/runtime.yaml"
    data = yaml.safe_load(runtime.read_text())
    data["maintenance"] = path
    runtime.write_text(yaml.safe_dump(data))
    (runtime_source / "outside.md").write_text("Outside the package.\n")
    result = run_install(tmp_path, runtime_source, "--target", "codex")
    assert result.returncode != 0
    assert "maintenance" in result.stderr
    assert not (tmp_path / "codex").exists()
