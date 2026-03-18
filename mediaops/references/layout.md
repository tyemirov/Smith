# Mediaops Folder Layout

Assume the current Codex working directory is the repository root:

```text
$PWD/
```

From that root, the maintained MediaOps layout is:

```text
$PWD/
  main.go                      # Root CLI entrypoint
  cmd/
    root.go                    # Cobra root and non-media commands
  internal/
    media/                     # Shared media CLI/provider implementation
      cli/
      audio/
      image/
      video/
      provider/
      ...
  skills/
    mediaops/
      SKILL.md
      references/
        layout.md
        workflows.md
        cli-help.md
      scripts/
        install_skill.sh
        update_mediaops.sh
        install_provider_env.sh
        ensure_mediaops.sh
        mediaops.sh
      assets/
        mediaops.env.example
      agents/
        openai.yaml
  scripts/
    setup_mediaops_vertex_gcs_adc.sh
    ...
  docs/
    mediaops-cli.md
    fresh-machine-runbook.md
    ...
  outputs/
    mediaops/                  # Final deliverables or approved exports
  output/
    mediaops/                  # Legacy/generated output area kept in the repo
  logs/
    mediaops/                  # Provider request/response snapshots and traces
  work/
    mediaops/                  # Reusable intermediates
  tmp/
    mediaops/                  # Disposable scratch
  .env                         # Optional repo-local dotenv source
```

The installed Codex runtime is separate from the repo checkout:

```text
~/.codex/
  skills/
    mediaops/
      bin/
        mediaops
      .env
      SKILL.md
      references/
        layout.md
        workflows.md
        cli-help.md
      scripts/
        install_skill.sh
        update_mediaops.sh
        install_provider_env.sh
        ensure_mediaops.sh
        mediaops.sh
      assets/
        mediaops.env.example
      agents/
        openai.yaml
```

Machine-local config lives outside both trees:

```text
~/.config/
  mediaops/
    .env
```

Placement rules:

- Run `~/.codex/skills/mediaops/bin/mediaops` for normal Codex runtime usage.
- Treat `main.go`, `cmd/`, `internal/media/`, and `skills/mediaops/` as the maintained sources of truth.
- Treat `~/.codex/skills/mediaops/` as a published runtime bundle derived from that source tree.
- The tracked entrypoint is `~/.codex/skills/mediaops/bin/mediaops`; when present, the persistent compiled runtime is cached under `~/.codex/skills/mediaops/.cache/bin/mediaops`.
- Keep generated videos, images, logs, and scratch work in the repo `outputs/mediaops`, `logs/mediaops`, `work/mediaops`, `tmp/mediaops`, or a user-specified output directory, not inside `~/.codex/skills/mediaops`.
- Use `outputs/` for final requested deliverables and approved exports.
- Use `work/` for reusable intermediates that may be needed to regenerate scenes, edits, boards, or stitched outputs.
- Use `logs/` for request/response sidecars and operation traces when you are not intentionally colocating them beside the media artifact they describe.
- Use `tmp/` only for disposable scratch. Do not store the only copy of prompts, transcripts, anchor frames, or other regeneration-critical inputs there.
- Treat `*.request.json` as potentially regeneration-critical metadata until the same prompt/provider settings are preserved elsewhere. Treat `*.response.json`, `*.operation-start.json`, `*.operation-polls.jsonl`, and `*.operation-final.json` as logs that are usually disposable after a verified successful run.
- Treat `~/.config/mediaops/.env` as the default machine-local secret file when the installed skill is not carrying its own bundled `.env`.
