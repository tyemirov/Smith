---
name: mediaops
description: Use this skill when the user wants to inspect supported audio/image/video models, generate speech/music/images/videos, align transcripts to audio, render mixed media compositions, stitch clips, or run HeyGen translation/avatar workflows with the installed `mediaops` CLI bundled inside this skill.
---

# Mediaops

## Overview

Use this skill for the local multi-provider media CLI bundled inside the skill directory. The primary runtime entrypoint is `bin/mediaops`. The tracked file at that path is a wrapper; when a compiled runtime is available it is cached under `.cache/bin/mediaops`. The maintained sources of truth are the repo root `main.go` / `cmd/root.go`, the shared media implementation under `internal/media/`, and the skill content under `skills/mediaops/`; the installed skill copy is a published runtime bundle.

Read [references/layout.md](references/layout.md) when you need to know what lives where. Read [references/workflows.md](references/workflows.md) when you need command patterns, provider selection guidance, or the current audio/image/video capability matrix. Read [references/cli-help.md](references/cli-help.md) when you need the full current CLI flag reference.

## Quick Start

1. Use `bin/mediaops` for runtime commands.
2. Use `scripts/install_skill.sh` from the repo copy when you want to publish or refresh a self-contained skill into `~/.codex/skills/mediaops`.
3. Start speech work with `bin/mediaops audio speech capabilities` when the user needs provider/model/output-format guidance, current ElevenLabs plan gating, or is choosing a speech model.
4. Start music work with `bin/mediaops audio music capabilities` when the user needs provider/model/duration/output-format guidance before composing music from a prompt.
5. Start forced-alignment work with `bin/mediaops audio align capabilities` when the user needs provider guidance before aligning transcript text against an audio file.
6. Start image work with `bin/mediaops image capabilities` when the user needs provider/model/aspect guidance or may be asking for masks, multiple inputs, or other provider-specific image behavior.
7. Start video work with `bin/mediaops video capabilities` when the user needs provider/model/duration/aspect guidance or is choosing between Vertex and Runway.
8. Start Vertex extension debugging with `bin/mediaops doctor vertex` when the user may be missing ADC, may have malformed `MEDIAOPS_OUTPUT_GCS_URI`, or when you need to distinguish blocking configuration failures from advisory local prefix-write probe failures.
9. Use `audio speech generate` or `audio speech convert` for the ElevenLabs speech workflows the current CLI exposes.
10. Use `audio music generate` for the ElevenLabs music workflow the current CLI exposes.
11. Use `audio align` for the forced-alignment workflow the current CLI exposes.
12. Use `video generate` for the video workflows the current CLI actually exposes.
13. Use `image generate` or `image edit` for the image workflows the current CLI actually exposes.
14. Use `mix render` for audio/image/video composition into one final video through the dedicated timeline export service.
15. Use `stitch` for concatenating MP4 clips.
16. Use `heygen translate`, `heygen create-character`, `heygen add-motion`, and `heygen lipsync` for HeyGen workflows.
17. Trust the CLI's printed cost estimate as a planning number, and the printed observed provider delta as a best-effort post-run accounting number.

## Credentials

- The requirement is that the provider env vars are present at execution time: `VERTEX_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `RUNWAY_API_KEY` or `RUNWAYML_API_SECRET`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, and `HEYGEN_API_KEY`, depending on the command/provider in use.
- For Vertex extension/generation flows that need Cloud Storage-backed output, set `MEDIAOPS_OUTPUT_GCS_URI=gs://bucket/prefix/` and provide ADC-backed GCS access through `GOOGLE_APPLICATION_CREDENTIALS` or another Application Default Credentials source.
- `gcloud auth login` creates local CLI login state under `~/.config/gcloud/`; do not treat that directory as the deployable backend credential for Vertex GCS output.
- For unattended/runtime Vertex GCS flows, use a service-account JSON key or another real ADC source via `GOOGLE_APPLICATION_CREDENTIALS`.
- `MEDIAOPS_OUTPUT_GCS_URI` is a Vertex-only default. It does not apply to Runway requests, so one shared provider env file can safely hold both Runway keys and the Vertex GCS output location.
- The CLI preflights the Vertex GCS output path before starting a GCS-backed Vertex run. Malformed `MEDIAOPS_OUTPUT_GCS_URI` values and missing ADC still fail immediately. Bucket metadata permission is not required for the runtime flow, and a local ADC prefix-write probe failure is reported as advisory because Vertex uploads outputs separately from the later local download step.
- The standard secret location for this skill is `~/.config/mediaops/.env`.
- Use `scripts/install_provider_env.sh` once to install a starter dotenv template there, then fill in the provider keys you actually use.
- `bin/mediaops` inherits any env vars that are already exported in the shell.
- The binary loads dotenv files itself. The installed skill runtime prefers a bundled skill-local `.env`, then `~/.config/mediaops/.env`, then other fallback dotenv locations.
- `scripts/install_skill.sh` copies the current `.env` into the installed skill directory so `~/.codex/skills/mediaops/bin/mediaops` can run without a checked-out repo.

## Shell Quoting

- Prefer direct execution like `bin/mediaops ...` when you do not need pipes, redirects, or compound shell logic. This avoids an extra quoting layer entirely.
- Do not wrap prompt text, transcript text, or jq programs inside nested single-quoted shell strings. That is the failure mode that breaks commands like `bash -lc '... jq '{...}' ...'`.
- For prompt or transcript text that contains apostrophes, quote the flag value with double quotes:

```bash
bin/mediaops audio speech generate \
  -provider elevenlabs \
  -voice "$ELEVENLABS_VOICE_ID" \
  -text "He won't write. He won't call." \
  -out ./speech.mp3
```

- For long or multiline prompt text, load it through a quoted here-doc and then pass the variable, instead of trying to escape the text inline:

```bash
PROMPT=$(cat <<'EOF'
An exhausted sailor whispers, "He won't write. He won't call."
Wind moves through the harbor behind him.
EOF
)

bin/mediaops video generate \
  -provider runway \
  -prompt "$PROMPT" \
  -out ./clip.mp4
```

- If you must use `bash -lc`, keep the outer wrapper in double quotes and keep jq filters in single quotes inside that wrapper:

```bash
bash -lc "bin/mediaops audio speech capabilities -provider elevenlabs > /tmp/caps.json && jq -c '{subscription: .subscription}' /tmp/caps.json"
```

- If a `bash -lc` command also needs prompt text with apostrophes, export the text as an env var first and reference the env var inside the inner shell instead of escaping inline text repeatedly:

```bash
export MEDIAOPS_PROMPT="He won't write. He won't call."
bash -lc 'bin/mediaops audio speech generate -provider elevenlabs -voice "$ELEVENLABS_VOICE_ID" -text "$MEDIAOPS_PROMPT" -out /tmp/speech.mp3'
```

- When the jq program itself becomes large or dynamic, write it to a file or use a here-doc instead of embedding it into a deeply nested shell string.
- Do not build shell commands by concatenating unescaped user text into the command line. Put dynamic prompt/text content in variables and pass the variables to `mediaops`.

## Artifact Hygiene

- Write outputs into a user or project workspace, not into `~/.codex/skills/mediaops/`.
- Separate artifacts into four buckets before a long workflow starts: final deliverables, regeneration inputs, debug logs, and scratch.
- At the end of every successful generation, stitch, mux, or render workflow, do a cleanup review automatically even if the user did not explicitly ask for cleanup.
- In that cleanup review, explicitly classify what was produced into `keep` and `disposable` buckets before giving the final answer.
- Keep the final files the user asked for plus the upstream assets needed to regenerate them: source audio/images/video, transcripts, cue sheets, scene markers, storyboard metadata, stable anchor frames, character manifests, and other reusable edit inputs.
- Keep `*.request.json` when it is the only durable record of the effective prompt, transcript, provider, or model parameters. If the same information is preserved elsewhere in a maintained manifest such as Markdown, CSV, or JSON, the sidecar can become optional after verification.
- Treat `*.response.json`, `*.operation-start.json`, `*.operation-polls.jsonl`, and `*.operation-final.json` as debug or audit traces by default. After a successful run, remove them unless the workflow is failing, the user asked for forensic logs, or the data is still needed to diagnose quota/provider issues.
- Remove obviously disposable intermediates after success: temporary stitch inputs, silent assembly masters once the muxed deliverable is verified, aborted partial renders, scratch exports, cache files, and `.DS_Store`.
- Do not delete generated stills, clips, or manifests that downstream edits, extensions, or stitches depend on unless the user explicitly wants a slimmed-down deliverable package.
- If the disposable set is unambiguous and low-risk, remove it before the final answer and report what was kept versus removed.
- If any candidate cleanup target is ambiguous or may still be reused, keep it and call it out explicitly in the final answer instead of silently deleting it.
- If the user asks for cleanup, report what you kept for regeneration and what you removed as disposable.
- When you are unsure whether an artifact is reusable or merely diagnostic, keep it and state the ambiguity instead of deleting it.

## Commands

### Inspect audio speech capabilities

```bash
bin/mediaops audio speech capabilities
```

```bash
bin/mediaops audio speech capabilities -provider elevenlabs
```

```bash
bin/mediaops audio speech capabilities -provider elevenlabs -model eleven_multilingual_v2
```

Audio speech capability rules:

- Use `audio speech capabilities` before choosing a non-default speech provider, model, or output format.
- With `ELEVENLABS_API_KEY`, `audio speech capabilities` enriches the static model catalog with live ElevenLabs model limits, speech-to-speech support flags, and the current account subscription tier.
- Trust the `client` section over generic provider docs when deciding what `mediaops` can do today.
- `surfaces` may mention provider-native features that are not exposed through `mediaops`; do not promise those features unless the `client` section also shows them.
- `-model` requires `-provider`.

### Inspect audio music capabilities

```bash
bin/mediaops audio music capabilities
```

```bash
bin/mediaops audio music capabilities -provider elevenlabs
```

Audio music capability rules:

- Use `audio music capabilities` before choosing a non-default music model, duration, or output format.
- Trust the `client` section over generic provider docs when deciding what `mediaops` can do today.
- `surfaces` may mention provider-native music features that are not exposed through `mediaops`; do not promise those features unless the `client` section also shows them.
- `-model` requires `-provider`.

### Inspect audio align capabilities

```bash
bin/mediaops audio align capabilities
```

```bash
bin/mediaops audio align capabilities -provider elevenlabs
```

Audio align capability rules:

- Use `audio align capabilities` before choosing a non-default alignment provider.
- Trust the `client` section over generic provider docs when deciding what `mediaops` can do today.
- `surfaces` may mention provider-native alignment features that are not exposed through `mediaops`; do not promise those features unless the `client` section also shows them.

### Inspect image capabilities

```bash
bin/mediaops image capabilities
```

```bash
bin/mediaops image capabilities -provider openai
```

```bash
bin/mediaops image capabilities -provider vertex -model gemini-3-pro-image-preview
```

Image capability rules:

- Use `image capabilities` before choosing a non-default image provider, model, or aspect ratio.
- Trust the `client` section over generic provider docs when deciding what `mediaops` can do today.
- `surfaces` may mention provider-native image features that are not exposed through `mediaops`; do not promise those features unless the `client` section also shows them.
- `-model` requires `-provider`.

### Inspect video capabilities

```bash
bin/mediaops video capabilities
```

```bash
bin/mediaops video capabilities -provider vertex
```

```bash
bin/mediaops video capabilities -provider runway -model gen4.5
```

Video capability rules:

- Use `video capabilities` before choosing a non-default video provider, model, duration, or aspect ratio.
- Trust the `client` section over generic provider docs when deciding what `mediaops` can do today.
- `surfaces` may mention provider-native video features that are not exposed through `mediaops`; do not promise those features unless the `client` section also shows them.
- `-model` requires `-provider`.
- For Vertex continuation planning, look for `client.fixedOutputDurationSeconds=7` on `veo-3.1-generate-preview`.

### Doctor Vertex

```bash
bin/mediaops doctor vertex
```

Doctor rules:

- Use `doctor vertex` before rerunning a failed Vertex extension or before a long GCS-backed Veo batch.
- Treat a failing `MEDIAOPS_OUTPUT_GCS_URI`, `adc`, or `gcs_bucket_access` check as blocking for Vertex continuation work.
- Treat `gcs_prefix_write` as advisory when `doctor vertex` reaches it; local ADC write access is not required for Vertex to upload its own outputs.
- `doctor vertex` checks the same env, GCS URI format, ADC path, and local prefix-write probe the CLI now runs before GCS-backed Veo generation starts.

### Generate video

```bash
bin/mediaops video generate \
  -provider runway \
  -start ./start.png \
  -aspect auto \
  -prompt "A marionette walks through a neon city" \
  -duration 4 \
  -out ./out.mp4
```

### Generate speech audio

```bash
bin/mediaops audio speech generate \
  -provider elevenlabs \
  -voice JBFqnCBsd6RMkjVDRZzb \
  -text "To be, or not to be, that is the question." \
  -model eleven_multilingual_v2 \
  -format mp3_44100_128 \
  -out ./speech.mp3
```

### Convert speech audio

```bash
bin/mediaops audio speech convert \
  -provider elevenlabs \
  -audio ./speech.mp3 \
  -voice JBFqnCBsd6RMkjVDRZzb \
  -model eleven_multilingual_sts_v2 \
  -format mp3_44100_128 \
  -input-format other \
  -remove-background-noise \
  -out ./speech_converted.mp3
```

### Generate music

```bash
bin/mediaops audio music generate \
  -provider elevenlabs \
  -prompt "A mournful sea ballad with low strings and distant bells" \
  -model music_v1 \
  -duration-ms 4000 \
  -format mp3_44100_128 \
  -out ./song.mp3
```

### Generate forced alignment

```bash
bin/mediaops audio align \
  -provider elevenlabs \
  -audio ./speech.mp3 \
  -text "To be, or not to be, that is the question." \
  -out ./alignment.json
```

### Generate image

```bash
bin/mediaops image generate \
  -provider vertex \
  -prompt "Photorealistic product shot of a Rivian on a dusty road at sunset" \
  -aspect 4:3 \
  -out ./out.png
```

### Edit image

```bash
bin/mediaops image edit \
  -provider openai \
  -image ./base.png \
  -mask ./mask.png \
  -prompt "Replace only the portal membrane and keep the truck unchanged" \
  -aspect 3:2 \
  -out ./edited.png
```

### Veo 3 Extensions On Vertex

- There is no separate `veo3` provider flag in `mediaops`. Use `-provider vertex` for Veo 3 and Veo 3.1 generation/extension workflows.
- Choose the Veo model with `-model` for generation and `-extend-model` for continuation. Current examples use `veo-3.1-generate-preview`.
- If Vertex needs Cloud Storage-backed output for the result, pass `-output-gcs-uri gs://bucket/prefix/` or set `MEDIAOPS_OUTPUT_GCS_URI`.

For Veo 3 / Veo 3.1 direct MP4 extension:

```bash
bin/mediaops video generate \
  -provider vertex \
  -video ./seed.mp4 \
  -extend "Continue the motion with a smooth cinematic follow-through" \
  -extend-model veo-3.1-generate-preview \
  -output-gcs-uri gs://mediaops-uscentral1/mediaops/ \
  -out ./extended.mp4
```

For Veo 3 / Veo 3.1 generate-then-extend from text or a start image:

```bash
bin/mediaops video generate \
  -provider vertex \
  -prompt "A girl smiles and waves to camera" \
  -start ./start.png \
  -extend "The camera flies past her and arcs back to the original framing" \
  -extend-model veo-3.1-generate-preview \
  -out ./extended.mp4
```

Extension guidance:

- Use `-extend` with `-prompt` and optional `-start` when you want `mediaops` to generate the first clip and then continue it with Veo.
- Use `-video` with `-extend` when you already have a local seed MP4 and want Veo to continue that exact clip.
- For Veo extension work, keep `-provider vertex`; the model name changes, not the provider name.
- For either extension path, add `-output-gcs-uri` or set `MEDIAOPS_OUTPUT_GCS_URI` when Vertex needs Cloud Storage-backed output for larger results.

### Image workflow limits

- Vertex in the current CLI supports `image generate` plus `image edit` with one prompt and one reference image. It writes one output image per run. It does not expose a separate `-mask` file, multi-turn editing, or multiple input images.
- OpenAI in the current CLI supports `image generate` plus `image edit` with an optional PNG `-mask`. It does not expose Responses API-only features such as multiple input images, input-fidelity selection, or transparent-mask editing without an explicit mask image.
- Vertex provider docs describe broader interleaved image+text and multi-turn flows upstream, but the current `GenerateContent` model path still pins `candidateCount` to `1`, so `mediaops` keeps a single-output image workflow.
- If the user asks for a feature that exists in provider docs but not in the `client` capability surface, explain that `mediaops` does not expose it yet instead of approximating it.

### Audio workflow limits

- ElevenLabs in the current CLI supports `audio speech generate` from text, `audio speech convert` from one source audio file through one voice ID at a time, and `audio music generate` from one prompt at a time. It does not yet expose account voice listing, streaming synthesis, pronunciation dictionaries, chained context fields such as `previous_text`, music composition plans, music uploads, or stem separation.
- `audio speech generate` uses live ElevenLabs metadata when `ELEVENLABS_API_KEY` is available to reject text above the current model limit and output formats gated above the current subscription tier before provider submission.
- `audio speech convert` uses the same typed speech capability surface for model/output-format selection and accepts source-audio hints through `-input-format` plus optional `-remove-background-noise`.
- `audio music capabilities` is the source of truth for the current music model, duration, and output-format surface.
- `audio music generate` uses ElevenLabs `/v1/music` with prompt text, optional `-duration-ms`, optional `-instrumental`, and one output file per run.
- `audio align` currently writes one JSON alignment artifact per run from one audio file plus one transcript text input.
- The current CLI writes one output artifact per run, even when the provider exposes richer streaming or batch surfaces elsewhere.
- If the user asks for a feature that exists in provider docs but not in the `client` capability surface, explain that `mediaops` does not expose it yet instead of approximating it.

### Stitch clips

```bash
bin/mediaops stitch \
  -out ./story.mp4 \
  ./clip1.mp4 \
  ./clip2.mp4 \
  ./clip3.mp4
```

### Mix local media into one video

```bash
export TIMELINE_EXPORT_SERVICE_URL=http://127.0.0.1:8080

bin/mediaops mix render \
  -spec ./composition.json \
  -out ./final.mov
```

Mix rules:

- Use `mix render` when the user already has local image/audio/video assets and needs one composed output video.
- `mix render` and the TelePrompter timeline export path share the same composition engine in `internal/media/mix`; the CLI parses the local spec and uploads its assets to the same timeline export job API.
- The spec is JSON rooted in the current block/track composition contract with a top-level `assets` map keyed by `asset_key`.
- `TIMELINE_EXPORT_SERVICE_URL` must point at the dedicated export service before the command can run.
- Repeated blocks with the same `asset_key` are uploaded once and reused by the service render path; keep the same key when the same asset should be reused efficiently.
- Video-track still images require `is_still_image: true`.
- Audio tracks and video tracks both contribute to the final output timeline; `mix render` always writes a video file, even for audio-led compositions.

### HeyGen translate

```bash
bin/mediaops heygen translate \
  -video-file ./source.mp4 \
  -output-language Russian \
  -out ./translated.mp4
```

### HeyGen photo avatar lipsync

```bash
bin/mediaops heygen create-character \
  -image-file ./portrait.png \
  -character-file ./portrait.character.json
```

```bash
bin/mediaops heygen lipsync \
  -character-file ./portrait.character.json \
  -audio-file ./voice.wav \
  -out ./portrait.mp4
```

## Update Mechanism

- `scripts/install_skill.sh` syncs the skill into the Codex skills directory, keeps `bin/mediaops` as the tracked wrapper entrypoint, and builds the compiled runtime into `.cache/bin/mediaops`.
- `scripts/ensure_mediaops.sh` prefers a bundled skill-local `.cache/bin/mediaops`. If no cached binary exists, it falls back to repo discovery and performs a temporary source-backed build only for that invocation.
- `scripts/install_provider_env.sh` installs a starter dotenv template at `~/.config/mediaops/.env` and refuses to overwrite an existing file.
- `scripts/update_mediaops.sh` refreshes the cached runtime directly from source when a repo checkout is available, and exits cleanly with the existing cached runtime when no repo checkout is present.
- Repo fallback discovery checks `MEDIAOPS_REPO`, the current working directory, `./mediaops`, and the checked-in repo path before failing.
- Env delivery checks the existing process env first, then dotenv files.
- Credential loading checks `MEDIAOPS_ENV_FILE`, then the `.env` adjacent to the running binary, then `~/.config/mediaops/.env`, then `MEDIAOPS_REPO/.env`, then the current working directory `.env`.

## Decision Rules

- Prefer `Runway` for short, stylized action shots and flexible durations.
- Prefer `Vertex` for Veo workflows, first/last-frame generation, and Gemini image generation/editing.
- Prefer `ElevenLabs` under `audio speech` for text-to-speech generation when the user needs narrated voice output from text.
- Prefer `ElevenLabs` under `audio music` when the user needs prompt-to-song or prompt-to-instrumental composition from text.
- Prefer `ElevenLabs` under `audio align` when the user needs transcript-to-audio forced alignment.
- Prefer `Vertex` for image work when the user needs `1:1`, `3:4`, `4:3`, `9:16`, or `16:9` stills and does not need a separate mask file.
- Prefer `OpenAI` for mask-guided image edits through `image edit`, or when the user needs `1:1`, `3:2`, or `2:3` aspect ratios.
- If the user asks which video model, duration, aspect ratio, or extension path is supported, run `bin/mediaops video capabilities` instead of guessing.
- If the user asks which speech model or output format is supported, run `bin/mediaops audio speech capabilities` instead of guessing.
- If the user asks which music model, duration, or format is supported, run `bin/mediaops audio music capabilities` instead of guessing.
- If the user asks whether speech-to-speech is supported or which STS model to use, run `bin/mediaops audio speech capabilities` instead of guessing.
- If the user asks which forced-alignment providers or upload semantics are supported, run `bin/mediaops audio align capabilities` instead of guessing.
- If the user asks why an ElevenLabs speech format or prompt length is rejected, check `bin/mediaops audio speech capabilities` first because it now reports live model limits and subscription-tier context when credentials are present.
- If the user asks which image model, aspect ratio, or mask behavior is supported, run `bin/mediaops image capabilities` instead of guessing.
- If the user asks for ElevenLabs voice listing, streaming synthesis, pronunciation dictionaries, or request-chaining context, explain that the provider may support it upstream but the current `mediaops` CLI does not expose it.
- If the user asks for multi-image compositing, multi-turn image editing, transparent-mask edits, text+image mixed responses, or more than `8` image outputs in one run, explain that the provider may support it upstream but the current `mediaops` CLI does not expose it.
- Prefer `HeyGen` only for translation, photo-avatar generation, motion augmentation, and audio-driven lipsync. Do not use it for cinematic full-body scene generation.
- If the user asks for cost, rely on the CLI's built-in estimate and observed provider delta output before trying to reconstruct charges manually.
- If the user asks to update the tool, run `scripts/update_mediaops.sh` before using the CLI.
- If the binary fails unexpectedly, rebuild once with `scripts/update_mediaops.sh` before assuming a provider-side problem.
