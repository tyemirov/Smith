# Mediaops CLI Help

This reference is captured from the current rebuilt `bin/mediaops` runtime. Refresh it whenever flags or command usage change.

## Root

```text
Usage:
  mediaops video generate [video flags]
  mediaops video capabilities [video flags]
  mediaops mix render [mix flags]
  mediaops doctor vertex
  mediaops audio speech generate [audio flags]
  mediaops audio speech convert [audio flags]
  mediaops audio speech capabilities [audio flags]
  mediaops audio music generate [audio flags]
  mediaops audio music capabilities [audio flags]
  mediaops audio align [audio flags]
  mediaops audio align capabilities [audio flags]
  mediaops image generate [image flags]
  mediaops image edit [image flags]
  mediaops image capabilities [image flags]
  mediaops stitch -out ./stitched.mp4 ./clip1.mp4 ./clip2.mp4 [./clip3.mp4 ...]
  mediaops heygen translate [flags]
  mediaops heygen create-character [flags]
  mediaops heygen add-motion [flags]
  mediaops heygen lipsync [flags]
```

## Doctor

```text
Doctor usage:
  mediaops doctor vertex

Doctor commands:
  vertex        Check Vertex env, ADC discovery, and Cloud Storage output writability
```

## Mix

```text
Mix usage:
  mediaops mix render [flags]

Mix commands:
  render        Render a final mixed video from a local composition spec

Mix flags:
  -spec string
        Required path to the local composition JSON spec
  -out string
        Required path for the rendered output video
  -ffmpeg-path string
        Optional ffmpeg binary path; defaults to FRAMEPICKER_FFMPEG_PATH or ffmpeg
  -timeout-seconds int
        Optional render timeout in seconds; 0 disables the deadline
```

## Video

```text
Video usage:
  mediaops video generate [flags]
  mediaops video capabilities [flags]

Video commands:
  generate      Generate video with Vertex or Runway
  capabilities  Print the supported video models and feature matrix

Video flags:
  -provider string
        Video provider: vertex or runway
  -prompt string
        The text description for the initial video generation
  -avoid string
        Optional constraints merged into the main prompt text for all providers
  -extend string
        Optional prompt to extend a generated or input video
  -model string
        Optional exact initial model; use `video capabilities` to inspect supported values
  -extend-model string
        Optional extension model; use `video capabilities` to inspect provider/model-specific support
  -start string
        Optional starting image for initial generation
  -end string
        Optional ending image for Vertex first/last-frame bridging
  -video string
        Optional local MP4 to extend directly on providers that support source-video extension
  -aspect string
        Target aspect ratio; use `auto` to infer from -start/-end anchors or use `video capabilities` for provider/model-specific supported values
  -duration int
        Initial generation duration; use `video capabilities` for provider/model-specific supported values
  -disable-audio
        Disable audio generation on providers that support generated audio
  -output-gcs-uri string
        Optional Vertex Cloud Storage output override
  -out string
        Path to save the generated video
```

## Video Generate

```text
Usage of video generate:
  -aspect string
    	Target aspect ratio. Use auto to infer from -start/-end anchors, or use mediaops video capabilities for provider/model-specific supported values (default "9:16")
  -avoid string
    	Optional constraints merged into the main prompt text for all providers, for example: "no extra objects, no duplicated skulls"
  -disable-audio
    	Disable audio generation
  -duration int
    	Initial generation duration in seconds. Use mediaops video capabilities for provider/model-specific supported values (default 8)
  -end string
    	Path to the ending image (Optional)
  -extend string
    	Optional prompt to extend a generated or input video
  -extend-model string
    	Model for the video extension step. Use mediaops video capabilities for provider/model-specific supported values
  -model string
    	Model for the initial generation step. Use mediaops video capabilities for provider/model-specific supported values
  -out string
    	Path to save the generated video (default "final_clip.mp4")
  -output-gcs-uri string
    	Optional gs://bucket/prefix for Vertex output storage when the API must write large results to Cloud Storage
  -prompt string
    	The text description for the initial video generation
  -provider string
    	Video provider: vertex or runway (default "vertex")
  -start string
    	Optional starting image for initial generation. Omit for true text-to-video
  -video string
    	Optional local MP4 to extend directly. Requires -extend and cannot be combined with -start/-end
```

## Video Capabilities

```text
Usage of video capabilities:
  -model string
    	Optional exact model name; requires -provider
  -provider string
    	Optional provider filter: vertex or runway
```

## Audio Speech Generate

```text
Usage of audio speech generate:
  -format string
    	Optional output format. Use mediaops audio speech capabilities for provider/model-specific supported values (default "mp3_44100_128")
  -model string
    	Optional provider-specific audio model
  -out string
    	Path to save the generated audio (default "generated_audio.mp3")
  -provider string
    	Audio provider: elevenlabs (default "elevenlabs")
  -similarity-boost value
    	Optional ElevenLabs similarity boost value between 0 and 1
  -speaker-boost
    	Optional ElevenLabs speaker boost toggle
  -stability value
    	Optional ElevenLabs stability value between 0 and 1
  -style value
    	Optional ElevenLabs style exaggeration value between 0 and 1
  -text string
    	The text to synthesize into speech
  -voice string
    	Required voice ID. Falls back to ELEVENLABS_VOICE_ID when present
```

## Audio Speech Convert

```text
Usage of audio speech convert:
  -audio string
    	Path to the source audio file to convert
  -format string
    	Optional output format. Use mediaops audio speech capabilities for provider/model-specific supported values (default "mp3_44100_128")
  -input-format string
    	Optional input audio format hint. Use mediaops audio speech capabilities for provider/model-specific supported values (default "other")
  -model string
    	Optional provider-specific audio model
  -out string
    	Path to save the converted audio (default "converted_audio.mp3")
  -provider string
    	Audio provider: elevenlabs (default "elevenlabs")
  -remove-background-noise
    	Optional ElevenLabs background-noise removal toggle
  -seed value
    	Optional ElevenLabs deterministic seed between 0 and 4294967295
  -similarity-boost value
    	Optional ElevenLabs similarity boost value between 0 and 1
  -speaker-boost
    	Optional ElevenLabs speaker boost toggle
  -stability value
    	Optional ElevenLabs stability value between 0 and 1
  -style value
    	Optional ElevenLabs style exaggeration value between 0 and 1
  -voice string
    	Required voice ID. Falls back to ELEVENLABS_VOICE_ID when present
```

## Audio Speech Capabilities

```text
Usage of audio speech capabilities:
  -model string
    	Optional exact model name; requires -provider
  -provider string
    	Optional provider filter: elevenlabs
```

## Audio Music Generate

```text
Usage of audio music generate:
  -duration-ms value
    	Target duration in milliseconds. Use mediaops audio music capabilities for provider/model-specific supported values
  -format string
    	Optional output format. Use mediaops audio music capabilities for provider/model-specific supported values (default "mp3_44100_128")
  -instrumental
    	Force the generated song to be instrumental
  -model string
    	Optional provider-specific music model
  -out string
    	Path to save the generated music (default "generated_music.mp3")
  -prompt string
    	The text prompt to compose into music
  -provider string
    	Audio music provider: elevenlabs (default "elevenlabs")
```

## Audio Music Capabilities

```text
Usage of audio music capabilities:
  -model string
    	Optional exact model name; requires -provider
  -provider string
    	Optional provider filter: elevenlabs
```

## Audio Align

```text
Audio align usage:
  mediaops audio align [flags]
  mediaops audio align capabilities [flags]

Audio align commands:
  capabilities  Print the supported alignment providers and feature matrix

Audio align flags:
  -provider string
        Audio alignment provider: elevenlabs
  -audio string
        Path to the source audio file to align
  -text string
        Transcript text to align against the audio
  -enable-spooled-file
        Enable the provider's spooled-file upload mode when supported
  -out string
        Path to save the alignment JSON
```

## Audio Align Capabilities

```text
Usage of audio align capabilities:
  -provider string
    	Optional provider filter: elevenlabs
```

## Image

```text
Image usage:
  mediaops image generate [flags]
  mediaops image edit [flags]
  mediaops image capabilities [flags]

Image commands:
  generate      Generate an image from a text prompt
  edit          Edit an image from a prompt and input image
  capabilities  Print the supported image models and feature matrix

Image flags:
  -provider string
        Image provider: vertex or openai
  -prompt string
        The text description for image generation or editing
  -model string
        Optional exact image model; use `image capabilities` to inspect supported values
  -aspect string
        Target aspect ratio; use `image capabilities` for provider/model-specific supported values
  -image string
        Required input image for `image edit`
  -mask string
        Optional mask image for providers that support mask-guided edits
  -out string
        Path to save the generated or edited image
```

## Image Generate

```text
Usage of image generate:
  -aspect string
    	Target aspect ratio. Use mediaops image capabilities for provider/model-specific supported values (default "1:1")
  -model string
    	Optional provider-specific image model
  -out string
    	Path to save the generated image (default "generated_image.png")
  -prompt string
    	The text description for image generation
  -provider string
    	Image provider: vertex or openai (default "vertex")
```

## Image Edit

```text
Usage of image edit:
  -aspect string
    	Optional target aspect ratio. Use mediaops image capabilities for provider/model-specific supported values
  -image string
    	Required input image to edit
  -mask string
    	Optional mask image for providers that support mask-guided edits
  -model string
    	Optional provider-specific image model
  -out string
    	Path to save the edited image (default "edited_image.png")
  -prompt string
    	The text description for image editing
  -provider string
    	Image provider: vertex or openai (default "vertex")
```

## Image Capabilities

```text
Usage of image capabilities:
  -model string
    	Optional exact model name; requires -provider
  -provider string
    	Optional provider filter: vertex or openai
```

## Stitch

```text
Usage of stitch:
  -audio-bitrate string
    	Audio bitrate used for re-encode fallback (default "192k")
  -audio-codec string
    	Audio codec used for re-encode fallback (default "aac")
  -crf int
    	CRF used for re-encode fallback (default 18)
  -force-reencode
    	Always re-encode instead of trying stream copy first
  -out string
    	Path to save the stitched output video (default "stitched.mp4")
  -preset string
    	Encoder preset used for re-encode fallback (default "veryfast")
  -video-codec string
    	Video codec used for re-encode fallback (default "libx264")
```

## HeyGen

```text
HeyGen usage:
  mediaops heygen translate [flags]
  mediaops heygen create-character -image-file ./portrait.png [-name Hamlet] [-character-file ./hamlet_character.json]
  mediaops heygen add-motion -character-file ./hamlet_character.json
  mediaops heygen lipsync -character-file ./hamlet_character.json -audio-file ./Hamlet.wav -out ./hamlet_lipsync.mp4
```
