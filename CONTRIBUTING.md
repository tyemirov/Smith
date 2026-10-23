# Contributor guide

Use this guide when you add or change skill helper scripts.
See the [README](README.md) for skill installation and use.

## Skill requirements

Inspect the skill's instructions, helpers, imports, commands, and referenced workflows before you declare requirements.
Use the standard `compatibility` frontmatter field for specific environment requirements.
Keep its value between 1 and 500 characters.
Use the skill body for feature-specific tools, authentication, network access, and setup details.
Separate a whole-skill OS restriction from an optional feature's OS restriction.
Separate agent host selection under `deployment` from operating system requirements.
Record runtime versions and dependencies from the actual helper declarations.
Identify required connectors and service access for workflows without local scripts.
Keep common installer requirements in the collection README.
Preserve the distinction between source-derived requirements and execution test evidence.
When instructions have no special environment requirement, omit `compatibility`.

## Python helpers

Python helper scripts must be executable and use a `uv` script shebang:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
```

Declare script dependencies inline in the `dependencies` list.
Invoke helpers directly, for example `./scripts/helper.py`.
The shebang starts `uv` with the declared Python version and dependencies.
Make `uv` available on `PATH`.
Scripts that must start another `uv` process can use a `UV` environment variable.
