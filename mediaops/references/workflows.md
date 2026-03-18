# Mediaops Workflows

## Provider Selection

- `vertex`: Veo generation, first/last-frame bridging, and extension workflows.
- `elevenlabs` under `audio speech`: text-to-speech generation and speech-to-speech conversion.
- `elevenlabs` under `audio music`: prompt-based music generation.
- `elevenlabs` under `audio align`: transcript-to-audio forced alignment.
- `vertex` under `image`: Gemini image generation/editing for stable branded anchor frames. Current CLI aspect ratios: `1:1`, `3:4`, `4:3`, `9:16`, `16:9`. Current CLI output count: one image per request.
- `runway`: text-to-video and image-to-video where short, stylized shots matter more than Vertex-specific features.
- `openai` under `image`: image generation plus mask-guided image edits. Current CLI aspect ratios: `1:1`, `3:2`, `2:3`.
- `heygen`: translation, photo avatars, motion avatars, and talking-photo lipsync.

For speech workflows, use `audio speech capabilities` before selecting a non-default model or output format. With `ELEVENLABS_API_KEY`, it also reports live model limits, speech-to-speech support flags, and current subscription-tier context.

For music workflows, use `audio music capabilities` before selecting a non-default model, duration, or output format.

For forced-alignment workflows, use `audio align capabilities` before selecting a provider or upload mode.

For image workflows, use `image capabilities` before selecting a non-default provider, model, or aspect ratio.

For video workflows, use `video capabilities` before selecting a non-default provider, model, duration, or aspect ratio.

For GCS-backed Vertex generation or extension workflows, use `doctor vertex` before retrying a failed run or starting a long batch. Treat failing `MEDIAOPS_OUTPUT_GCS_URI`, `adc`, and `gcs_bucket_access` checks as blocking. Treat a `gcs_prefix_write` warning as advisory when the doctor reaches the local write probe, because Vertex uploads outputs separately from the later local download step.

## Standard Commands

### Help

```bash
bin/mediaops help
```

### Audio speech capabilities

```bash
bin/mediaops audio speech capabilities
```

```bash
bin/mediaops audio speech capabilities -provider elevenlabs
```

### Audio music capabilities

```bash
bin/mediaops audio music capabilities
```

```bash
bin/mediaops audio music capabilities -provider elevenlabs
```

### Audio align capabilities

```bash
bin/mediaops audio align capabilities
```

```bash
bin/mediaops audio align capabilities -provider elevenlabs
```

### Image capabilities

```bash
bin/mediaops image capabilities
```

```bash
bin/mediaops image capabilities -provider openai
```

### Video capabilities

```bash
bin/mediaops video capabilities
```

```bash
bin/mediaops video capabilities -provider vertex
```

The Vertex extension model now reports `client.fixedOutputDurationSeconds=7`, so continuation planning no longer requires guessing.

### Vertex doctor

```bash
bin/mediaops doctor vertex
```

### Vertex generate

```bash
bin/mediaops video generate \
  -provider vertex \
  -start ./start.png \
  -aspect auto \
  -prompt "Slow cinematic dolly in" \
  -duration 6 \
  -disable-audio \
  -out ./vertex.mp4
```

### Runway generate

```bash
bin/mediaops video generate \
  -provider runway \
  -model gen4.5 \
  -start ./start.png \
  -prompt "A puppet girl under neon rain" \
  -duration 4 \
  -out ./runway.mp4
```

### ElevenLabs audio speech generate

```bash
bin/mediaops audio speech generate \
  -provider elevenlabs \
  -voice JBFqnCBsd6RMkjVDRZzb \
  -text "To be, or not to be, that is the question." \
  -model eleven_multilingual_v2 \
  -format mp3_44100_128 \
  -out ./speech.mp3
```

### ElevenLabs audio speech convert

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

### ElevenLabs audio music generate

```bash
bin/mediaops audio music generate \
  -provider elevenlabs \
  -prompt "A mournful sea ballad with low strings and distant bells" \
  -model music_v1 \
  -duration-ms 4000 \
  -format mp3_44100_128 \
  -out ./song.mp3
```

### ElevenLabs forced alignment

```bash
bin/mediaops audio align \
  -provider elevenlabs \
  -audio ./speech.mp3 \
  -text "To be, or not to be, that is the question." \
  -out ./alignment.json
```

### Vertex image generate

```bash
bin/mediaops image generate \
  -provider vertex \
  -prompt "Photorealistic product shot of a Rivian on a dusty road at sunset" \
  -aspect 4:3 \
  -out ./vertex.png
```

### OpenAI image edit

```bash
bin/mediaops image edit \
  -provider openai \
  -image ./base.png \
  -mask ./mask.png \
  -prompt "Replace only the portal membrane and keep the truck unchanged" \
  -aspect 3:2 \
  -out ./edited.png
```

### Stitch

```bash
bin/mediaops stitch \
  -out ./stitched.mp4 \
  ./part1.mp4 \
  ./part2.mp4 \
  ./part3.mp4
```

### Mix local media into one final video

```bash
bin/mediaops mix render \
  -spec ./composition.json \
  -out ./final.mov
```

### HeyGen translate

```bash
bin/mediaops heygen translate \
  -video-file ./source.mp4 \
  -output-language Russian \
  -mode quality \
  -out ./translated.mp4
```

### HeyGen lipsync

```bash
bin/mediaops heygen lipsync \
  -character-file ./actor.character.json \
  -audio-file ./voice.wav \
  -trim-seconds 10 \
  -out ./lipsync.mp4
```

## Cost and Accounting

- The CLI prints an estimated cost before execution.
- `runway` also prints a best-effort observed account credit delta after the run.
- `heygen` prints a best-effort observed remaining-quota delta after the run.
- `vertex` remains estimate-only in this client.

## Artifact Hygiene

- Prefer an explicit project output directory over writing ad hoc files into the skill install tree.
- Close every successful workflow with a cleanup pass, even when the user did not ask for one explicitly.
- Before the final answer, sort artifacts into `keep` and `disposable` groups and say which rule justified the choice.
- Keep final deliverables plus the minimum set of assets needed to regenerate them: source media, transcripts, cue sheets, stable edit anchors, scene frames, character manifests, and request sidecars or equivalent prompt metadata.
- Keep `*.request.json` until the same prompt, transcript, provider, and model choices are captured somewhere durable such as a maintained Markdown, CSV, or JSON manifest.
- Treat `*.response.json`, `*.operation-start.json`, `*.operation-polls.jsonl`, and `*.operation-final.json` as debug traces. Remove them after a verified successful run unless the user wants audit logs or the workflow is still unstable.
- After verifying a stitched or muxed final deliverable, remove silent assembly masters, temporary stitch inputs, aborted renders, and other scratch artifacts that can be recreated from the retained assets.
- If the disposable set is obvious and low-risk, remove it before replying instead of merely suggesting cleanup.
- If any artifact is plausibly reusable, keep it and mention the ambiguity instead of deleting it by default.
- When cleaning up for the user, explicitly separate what you kept for regeneration from what you removed as disposable.

## Current Image Client Limits

- `image capabilities` is the source of truth for the current `mediaops image` surface.
- Vertex provider docs expose more than the current CLI: multiple input images, text+image responses, and multi-turn editing exist upstream, but the current model path still pins `candidateCount` to `1`, so `mediaops` keeps one image output per run.
- OpenAI provider docs expose more than the current CLI: Responses API multiple input images, input-fidelity selection, and transparent-mask editing are not surfaced through `mediaops`.
- The current CLI writes one image artifact per run and only supports a separate `-mask` file on the OpenAI path.

## Current Video Client Limits

- `video capabilities` is the source of truth for the current `mediaops video` surface.
- Vertex in the current CLI supports text-to-video, image-to-video, first/last-frame bridging, and generated-clip or local-MP4 extension through `-extend`.
- Vertex continuation planning no longer needs manual duration guesses; `video capabilities` reports the fixed `7` second extension output on the extension model.
- Runway in the current CLI supports text-to-video and image-to-video, but does not expose `-extend`, `-video`, or `-end`.

## Current Audio Client Limits

- `audio speech capabilities` is the source of truth for the current `mediaops` speech surface.
- `audio speech capabilities` enriches the static catalog with live ElevenLabs `models` and `user/subscription` metadata when `ELEVENLABS_API_KEY` is present.
- `audio speech generate` uses that live metadata to reject text that exceeds the current model limit and output formats gated above the current subscription tier before the provider request is sent.
- `audio speech convert` uses the same speech capability surface for STS model/output-format selection and supports source-audio hints through `-input-format`.
- `audio music capabilities` is the source of truth for the current `mediaops` music surface.
- `audio music generate` exposes prompt-based ElevenLabs `/v1/music` generation with optional `-duration-ms`, optional `-instrumental`, and one output file per run.
- The current music CLI does not yet expose composition-plan, streaming, upload, or stem-separation workflows.
- `audio align capabilities` is the source of truth for the current `mediaops` forced-alignment surface.
- `audio align` writes one JSON alignment artifact per run.
- `mix render` is the source of truth for the current local mux/composition surface.
- `mix render` uses a local JSON composition spec with the block/track timing contract plus a top-level `assets` map of local file paths.
- Repeated blocks that share one `asset_key` reuse one ffmpeg input in the current `mix render` implementation.
- ElevenLabs provider docs expose more than the current CLI: account voice listing, streaming TTS, pronunciation dictionaries, and request-chaining context are not surfaced through `mediaops`.
- The current speech CLI writes one output audio file per run and requires a voice ID instead of exposing a voice search/list command.
