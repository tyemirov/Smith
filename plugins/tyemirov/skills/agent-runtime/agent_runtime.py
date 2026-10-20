"""Validate shared role contracts and render native agent configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import json
import re

import tomli_w
import yaml

HOSTS = {"openai": "codex", "claude": "claude", "opencode": "opencode",
         "antigravity": "antigravity", "muse": "agent_read"}
ROLES = frozenset({"explorer", "worker", "researcher", "architect"})
EFFORTS = frozenset({"inherit", "none", "low", "medium", "high", "xhigh", "max", "ultra"})
CHECKPOINTS = frozenset({"before_plan", "repeated_error", "before_done"})
EXECUTIONS = frozenset({"primary_agent", "primary_agent_with_scripts", "conditional_subagent"})


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys at the file boundary."""


def unique_mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict:
    result: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise ValueError("mapping keys must be distinct strings")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


@dataclass(frozen=True)
class Binding:
    model: str
    reasoning_effort: str


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    description: str
    access: str
    instructions: tuple[str, ...]


@dataclass(frozen=True)
class Host:
    id: str
    adapter: str
    instructions_file: str | None
    agents_dir: str
    controller: Binding
    roles: dict[str, Binding]


@dataclass(frozen=True)
class Governance:
    id: str
    source: Path
    instructions: tuple[str, ...]
    checkpoints: dict[str, str]
    roles: dict[str, Role]
    hosts: dict[str, Host]
    maintenance: Path | None = None


@dataclass(frozen=True)
class Workflow:
    governance: str
    source: Path
    roles: frozenset[str]


def mapping(value: object, required: set[str] | frozenset[str], optional: set[str] | frozenset[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError(f"expected fields {sorted(required)}, optional {sorted(optional)}")
    return value


def string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a nonempty string")
    return value


def strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("expected a nonempty string list")
    return tuple(string(item) for item in value)


def relative_path(value: object) -> str:
    path = PurePosixPath(string(value))
    if path.is_absolute() or ".." in path.parts or str(path) == "." or "\\" in str(path):
        raise ValueError("expected a relative path inside the host root")
    return str(path)


def binding(value: object) -> Binding:
    data = mapping(value, {"model", "reasoning_effort"})
    model, effort = string(data["model"]), string(data["reasoning_effort"])
    if effort not in EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {effort}")
    return Binding(model, effort)


def load(path: Path) -> Governance | Workflow:
    try:
        data = yaml.load(path.read_text(), Loader=UniqueLoader)
        if not isinstance(data, dict):
            raise ValueError("expected a runtime mapping")
        kind = data.get("kind")
        if kind == "workflow":
            return load_workflow(path, data)
        if kind != "governance":
            raise ValueError("runtime requires kind: governance or kind: workflow")
        mapping(data, {"kind", "id", "instructions", "checkpoints", "roles", "hosts"}, {"maintenance"})
        maintenance = None
        if "maintenance" in data:
            try:
                package = path.resolve().parent.parent
                maintenance = (package / relative_path(data["maintenance"])).resolve()
                if not maintenance.is_relative_to(package) or not maintenance.is_file():
                    raise ValueError("reference must exist inside the skill package")
            except ValueError as error:
                raise ValueError(f"invalid maintenance reference: {error}") from error
        identifier = string(data["id"])
        if not re.fullmatch(r"[a-z][a-z0-9-]*", identifier):
            raise ValueError("invalid governance identifier")
        instructions = strings(data["instructions"])
        checkpoints = {key: string(value) for key, value in mapping(data["checkpoints"], CHECKPOINTS).items()}
        roles: dict[str, Role] = {}
        names: set[str] = set()
        for key, value in mapping(data["roles"], ROLES).items():
            role = mapping(value, {"name", "description", "access", "instructions"})
            name = string(role["name"])
            if not re.fullmatch(r"mpr-[a-z][a-z0-9-]*", name) or name in names:
                raise ValueError("role names must be distinct mpr-prefixed identifiers")
            access = string(role["access"])
            if access not in {"read", "write"} or (key != "worker" and access != "read"):
                raise ValueError("only the worker role can have write access")
            names.add(name)
            roles[key] = Role(key, name, string(role["description"]), access, strings(role["instructions"]))
        hosts: dict[str, Host] = {}
        for key, value in mapping(data["hosts"], set(HOSTS)).items():
            host = mapping(value, {"adapter", "instructions_file", "agents_dir", "controller", "roles"})
            if host["adapter"] != HOSTS[key]:
                raise ValueError(f"invalid adapter for {key}")
            instructions_file = host["instructions_file"]
            if instructions_file is not None:
                instructions_file = relative_path(instructions_file)
            if key != "muse" and instructions_file is None:
                raise ValueError("native hosts require an instructions file")
            role_bindings = {role: binding(item) for role, item in mapping(host["roles"], ROLES).items()}
            controller = binding(host["controller"])
            if key != "openai" and controller != Binding("inherit", "inherit"):
                raise ValueError("only Codex controller model settings have a native adapter")
            for item in role_bindings.values():
                if key == "antigravity" and (item.model not in {"inherit", "flash", "pro"} or item.reasoning_effort != "inherit"):
                    raise ValueError("Antigravity requires its native model tiers and inherited effort")
                if key == "claude" and (item.model not in {"inherit", "haiku", "sonnet", "opus"}
                                        or item.reasoning_effort not in {"inherit", "low", "medium", "high", "xhigh", "max"}):
                    raise ValueError("Claude requires a supported native model alias and effort")
                if key == "opencode" and item.model != "inherit" and "/" not in item.model:
                    raise ValueError("OpenCode models require provider/model identifiers")
            hosts[key] = Host(key, host["adapter"], instructions_file, relative_path(host["agents_dir"]), controller, role_bindings)
        return Governance(identifier, path.resolve(), instructions, checkpoints, roles, hosts, maintenance)
    except (OSError, ValueError, yaml.YAMLError, TypeError) as error:
        raise ValueError(f"Invalid runtime {path}: {error}") from error


def load_workflow(path: Path, data: dict) -> Workflow:
    mapping(data, {"kind", "governance", "controller", "steps"}, {"delegation"})
    controller = mapping(data["controller"], {"responsibilities"})
    strings(controller["responsibilities"])
    if "delegation" in data:
        rules = mapping(data["delegation"], set(), {"selection", "context", "execution_record", "capability_check"})
        for rule in rules.values():
            strings(rule)
    steps = data["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("workflow requires steps")
    ids: set[str] = set()
    roles: set[str] = set()
    for value in steps:
        step = mapping(value, {"id", "role", "execution", "workspace", "scope"},
                       {"controller_handoff", "required_review", "review_condition"})
        identifier, role = string(step["id"]), string(step["role"])
        if identifier in ids or role not in ROLES:
            raise ValueError("workflow steps require distinct IDs and defined roles")
        if step["execution"] not in EXECUTIONS or step["workspace"] != "primary":
            raise ValueError("workflow steps require a supported execution method and the primary checkout")
        string(step["scope"])
        if "controller_handoff" in step:
            string(step["controller_handoff"])
        if "required_review" in step and not isinstance(step["required_review"], bool):
            raise ValueError("required_review must be a boolean")
        if "review_condition" in step:
            string(step["review_condition"])
            if not step.get("required_review"):
                raise ValueError("review_condition requires required_review: true")
        ids.add(identifier)
        roles.add(role)
    return Workflow(string(data["governance"]), path.resolve(), frozenset(roles))


def markdown(header: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(header, sort_keys=False) + "---\n\n" + body + "\n"


def role_body(contract: Governance, role: Role) -> str:
    instructions = [*contract.instructions]
    maintenance = maintenance_instruction(contract)
    if maintenance:
        instructions.append(maintenance)
    instructions.extend(role.instructions)
    return "\n".join(f"- {item}" for item in instructions)


def maintenance_instruction(contract: Governance) -> str | None:
    if contract.maintenance is None:
        return None
    return f"For orchestration maintenance, read `{contract.maintenance}` before model adoption, host changes, or retirement."


def render(contract: Governance, target: str) -> list[dict]:
    host_id = "openai" if target == "codex" else target
    host = contract.hosts[host_id]
    operations: list[dict] = []
    if host.adapter == "agent_read":
        catalog = {
            "governance": contract.id,
            "execution": "agent_read",
            "source": str(contract.source),
            "roles": {key: {"name": role.name, "model": host.roles[key].model,
                            "reasoning_effort": host.roles[key].reasoning_effort,
                            "instructions": role_body(contract, role)}
                      for key, role in contract.roles.items()},
            "instructions": list(contract.instructions), "checkpoints": contract.checkpoints,
        }
        if contract.maintenance:
            catalog["maintenance"] = str(contract.maintenance)
            catalog["instructions"].append(maintenance_instruction(contract))
        operations.append({"kind": "file", "path": f"{host.agents_dir}/{contract.id}.json",
                           "content": json.dumps(catalog, indent=2) + "\n"})
    else:
        for key, role in contract.roles.items():
            assigned = host.roles[key]
            body = role_body(contract, role)
            if host.adapter == "codex":
                fields = {"name": role.name, "description": role.description, "developer_instructions": body}
                if assigned.model != "inherit":
                    fields["model"] = assigned.model
                if assigned.reasoning_effort != "inherit":
                    fields["model_reasoning_effort"] = assigned.reasoning_effort
                if role.access == "read":
                    fields["sandbox_mode"] = "read-only"
                content, suffix = tomli_w.dumps(fields), ".toml"
            elif host.adapter == "claude":
                fields = {"name": role.name, "description": role.description, "model": assigned.model}
                if assigned.reasoning_effort != "inherit":
                    fields["effort"] = assigned.reasoning_effort
                if role.access == "read":
                    fields["tools"] = "Read, Glob, Grep, Bash, WebFetch, WebSearch"
                    fields["disallowedTools"] = "Write, Edit, NotebookEdit"
                content, suffix = markdown(fields, body), ".md"
            elif host.adapter == "opencode":
                fields = {"description": role.description, "mode": "subagent"}
                if assigned.model != "inherit":
                    fields["model"] = assigned.model
                if assigned.reasoning_effort != "inherit":
                    fields["reasoningEffort"] = assigned.reasoning_effort
                if role.access == "read":
                    fields["permission"] = {"edit": "deny"}
                content, suffix = markdown(fields, body), ".md"
            else:
                fields = {"name": role.name, "description": role.description, "mainAgent": False,
                          "subagent": True, "model": assigned.model,
                          "tools": ["view_file", "grep_search", "run_command"]}
                if role.access == "write":
                    fields["tools"].extend(["replace_file_content", "write_to_file"])
                content, suffix = markdown(fields, body), ".md"
            operations.append({"kind": "file", "path": f"{host.agents_dir}/{role.name}{suffix}", "content": content})
    if host.instructions_file:
        lines = ["## MPR Lab Agent Orchestration", "", f"Shared contract: `{contract.id}`.",
                 f"Read `{contract.source}` before role selection."]
        maintenance = maintenance_instruction(contract)
        if maintenance:
            lines.append(maintenance)
        lines.extend(["",
                 *[f"- {item}" for item in contract.instructions], "",
                 *[f"- {item}" for item in contract.checkpoints.values()], "",
                 "| Role | Agent | Model | Effort |", "| --- | --- | --- | --- |"])
        lines.extend(f"| {key} | {role.name} | {host.roles[key].model} | {host.roles[key].reasoning_effort} |"
                     for key, role in contract.roles.items())
        operations.append({"kind": "section", "path": host.instructions_file,
                           "marker": "MPRLAB-ORCHESTRATION", "content": "\n".join(lines) + "\n"})
    if host.adapter == "codex":
        values = {}
        if host.controller.model != "inherit":
            values["model"] = host.controller.model
        if host.controller.reasoning_effort != "inherit":
            values["model_reasoning_effort"] = host.controller.reasoning_effort
        if values:
            operations.append({"kind": "toml", "path": "config.toml", "values": values})
    return operations
