# Grizzly

A local, Apple Silicon accelerated story studio. You give it a premise. A local LLM writes a story bible, an outline and a shot list, and a local diffusion model illustrates every shot. Grizzly then assembles the result as a **comic** (PDF), a **visual novel** (Ren'Py project plus a standalone HTML player) or a **short film animatic** (MP4 with voice-over and subtitles).

Everything runs on-device: no cloud, no API keys.

## Status

Prototype, aimed at a **MacBook Pro M5 Pro with 24GB**.

- The pipeline, the exports, the web studio and the CLI are tested end to end with mock backends (`pytest`, 13 tests).
- The MLX backends (`grizzly/llm/mlx_backend.py`, `grizzly/image/mflux_backend.py`) are written against the current `mlx-lm` 0.32 and `mflux` 0.23 sources. Their first real run happens on the Mac.

## Quick start (Mac)

```sh
brew install ffmpeg uv
git clone https://github.com/liquidpr3y/Grizzly && cd Grizzly
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e '.[mac,server]'

grizzly doctor          # checks MLX, then loads and tests each model on its own
grizzly new "The Lighthouse Signal" "A young keeper discovers the lighthouse beam is answering something beneath the sea." --format comic
grizzly -v run the_lighthouse_signal --scenes 3 --shots 4

# or use the web studio to edit the story and re-render individual shots
grizzly serve   # http://127.0.0.1:8642
```

The first run downloads about 5GB for the writer and about 7GB for the illustrator from Hugging Face into `~/.cache/huggingface`. Projects are saved to `~/Grizzly/projects/<id>/`.

To try it without any models: `GRIZZLY_PROFILE=mock grizzly run <id>`.

## How it works

```
premise ──LLM──▶ story bible ──LLM──▶ outline ──LLM──▶ shot list
                 (characters,          (scenes)         (framing, action,
                  locations,                             dialogue, narration)
                  art style)                │
                                            ▼
                    character portraits ◀─diffusion─▶ shot images
                                            │
                  ┌─────────────────────────┼─────────────────────────┐
                  ▼                         ▼                         ▼
          comic pages + PDF      Ren'Py project + HTML VN     animatic MP4 (+ `say` TTS, SRT)
```

| Step | Command | Output |
|---|---|---|
| bible | `grizzly step <id> bible` | characters with fixed visual appearance, locations, art style |
| outline | `grizzly step <id> outline --scenes 4` | scene list |
| shots | `grizzly step <id> shots --shots 4` | per-scene shot list |
| portraits | `grizzly step <id> portraits` | one reference portrait per character |
| images | `grizzly step <id> images [--only s1_02] [--force]` | one image per shot |
| comic / vn / animatic | `grizzly step <id> comic` | `exports/…` |

Every stage saves to `project.json`, which is plain JSON. You can edit it, or edit through the studio, between steps. Rerunning a write step clears everything that depends on it.

### Memory budget on 24GB

macOS lets the GPU wire roughly two thirds of unified memory. The `m5pro-24gb` profile therefore keeps **one model resident at a time** (`grizzly/memory.py`) and swaps between them:

| Role | Default model | Approx. resident |
|---|---|---|
| Writer | `mlx-community/Qwen3-8B-4bit` (mlx-lm) | ~5GB |
| Character portraits | Z-Image Turbo, 4-bit (`filipstrand/Z-Image-Turbo-mflux-4bit`, mflux) | ~6–8GB peak |
| Shots, drawn from the portraits | FLUX.2 Klein 4B, 4-bit (`mflux-community/flux2-klein-4b-mflux-q4`, mflux, Apache-2.0) | ~4.6GB download |

Other profiles: `m5pro-24gb-ollama` (the writer runs in an existing Ollama install), `mac-48gb` (both models stay loaded, with a 14B writer) and `mock`. You can override models with `GRIZZLY_LLM_MODEL`, `GRIZZLY_IMAGE_MODEL` and `GRIZZLY_IMAGE_STEPS`. `GRIZZLY_REFS=off` draws shots with Z-Image from text alone, as before.

### Character consistency

1. **Text.** Each prompt repeats the global art style, the fixed `appearance` text of every visible character, the location description and an explicit head count. Seeds are derived from stable ids, so a re-render is reproducible.
2. **Reference images.** Z-Image draws one full-body portrait per character (`images/characters/`). FLUX.2 Klein then draws every shot with the portraits of up to three characters in frame as reference images (downscaled copies in `images/refs/`). The prompt names which image shows whom. This pins down details that text alone drifts on, such as a monocle turning into glasses.

The portrait is what every shot copies, so check `images/characters/` before rendering shots. To re-draw one character's portrait with a fresh seed, run `grizzly step <id> portraits --only <character_id> --reroll`, or click **Save + new portrait** in the studio. If the model keeps getting a detail wrong, sharpen their appearance text first. Then run `grizzly step <id> images --force`.

## Roadmap

**Phase 1: prototype (this repo).** Validate quality and speed on the M5 Pro.

**Phase 2: quality**
- Per-character LoRAs trained locally from the portrait sheet (mflux supports LoRA training), applied automatically when a character is in shot.
- Pose and layout control via ControlNet (Z-Image Turbo ControlNet Union is already in mflux).
- Real image-to-video per shot (Wan 2.x 5B / LTX-Video class) replacing the Ken Burns clip in `render/animatic.py`.
- Branching choices for visual novels; better bubble placement (face detection to point tails).

**Phase 3: product.** The HTTP API in `grizzly/server.py` is the seam for either route:
- **Mac app:** a SwiftUI front end with the Python engine bundled as a signed helper process (the Ollama model). Inference can later be ported to `mlx-swift` piece by piece. Distribute via a notarised direct download; the Mac App Store sandbox and size limits make it a poor fit for multi-GB models.
- **SaaS:** keep the pipeline and swap the backends for CUDA ones (vLLM / diffusers), add a job queue, object storage and per-user auth.

Check each model's licence before commercial use. Choose models whose licences allow both local redistribution and hosted use.

## Development

```sh
uv pip install -e '.[dev]'
pytest
```
