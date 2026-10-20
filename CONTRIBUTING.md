# Contributor guide

Use this guide when you add or change skill helper scripts.
See the [README](README.md) for skill installation and use.

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
