# Grizzly for Mac

The native SwiftUI front end. It starts the Python engine (`grizzly serve`) and talks to it over the engine's local HTTP API on `127.0.0.1`. That's the same model Ollama's app uses: a native shell around a local inference server.

```
Grizzly.app (SwiftUI)  ──HTTP 127.0.0.1:8642──▶  grizzly serve (Python: MLX writer, mflux, mlx-video)
      │                                                  │
      └── starts / stops the engine process ─────────────┘
```

The engine runs from one of two places:

- **Built in** (the default when present): `Grizzly.app/Contents/Resources/engine`, made by `scripts/make-app.sh`. It holds a standalone Python 3.12 ([python-build-standalone](https://github.com/astral-sh/python-build-standalone), fetched by uv), Grizzly with MLX, mflux and mlx-video installed into it, and a static ffmpeg. The Mac it runs on needs no Python, uv or Homebrew. Model weights are not bundled; they download on first use, as before.
- **A Grizzly checkout**, for development: `~/Grizzly/.venv`, or any folder you pick in Settings.

## Run it

Requirements to build: macOS 14 or later, Xcode 16 or later, and uv.

- **Self-contained app:** `app/scripts/make-app.sh`, then `open app/build/Grizzly.app`. The first build takes a few minutes and downloads about 1.5GB of Python packages. `--reuse` skips rebuilding the engine; `--no-engine` builds the app alone.
- **Xcode (while developing):** `open app/Package.swift`, pick the **Grizzly** scheme and **My Mac**, then press ⌘R. This runs the engine from your checkout (`uv pip install -e '.[mac,server,video]'` from the repo root first).
- **Terminal:** `cd app && swift run Grizzly`, also from your checkout.

Without a built-in engine the app looks in `~/Grizzly/.venv`. If your checkout is somewhere else, use **Settings → Choose…** or the button on the "engine isn't running" screen. An app with a built-in engine can be switched to a checkout in **Settings → Engine**. If an engine is already running on the port (for example `grizzly serve` in a terminal), the app uses it instead of starting its own. Quitting the app stops the engine it started, so model memory is released.

## What's where

| Area | What it does |
|---|---|
| Library (sidebar) | Your stories with cover art; **New Story** (⌘N); right-click to delete. |
| Graph (default) | The story's pipeline as a node graph in the style of ComfyUI: Premise → Story Bible → Outline → Storyboard, with Cast and Storyboard both feeding Panels, then Clips and Exports. Wires are coloured by data type (text, image, video, file). Nodes show live status and previews. Click a node to open its tab; pinch or use the zoom control to zoom. |
| Pipeline bar | Shown on the other tabs: Story → Cast → Panels → Export, with live progress such as "Drawing panels · 7 of 16". |
| Story | Premise, genre and tone, editable art direction, scene outline. |
| Cast | Character portraits with editable appearance and voice. **New Portrait** redraws one character with a fresh seed. |
| Storyboard | Panels grouped by scene. Click one to open the inspector: edit the description, framing, narration and dialogue, then **Redraw**, **New Take** or **Animate**. Animated shots play inline. |
| Export | Build or rebuild the comic PDF (with page previews), the visual novel (opens in your browser, plus a Ren'Py project) and the animatic (plays inline). |

While a job runs on a story, editing that story is locked. The engine saves its own copy as it works, so an edit made mid-run would be overwritten.

## Layout

- `Sources/GrizzlyCore`: engine client, models and process launcher. Foundation only.
- `Sources/Grizzly`: the SwiftUI app.
- `Tests/GrizzlyCoreTests`: unit tests, plus an integration test that launches the real engine with mock models and drives a whole story through the client.

- `scripts/bundle-engine.sh`: builds the self-contained engine; `scripts/make-app.sh`: builds and signs the app around it.

GrizzlyCore builds and is tested on Linux too: `GRIZZLY_ENGINE_DIR=/path/to/Grizzly swift test`. Add `GRIZZLY_BUNDLED_ENGINE=/path/to/engine` (from `GRIZZLY_EXTRAS=server scripts/bundle-engine.sh /path/to/engine`) to also run a story through a bundled engine and check it writes nothing into its own folder. The SwiftUI target compiles only on macOS; elsewhere it builds to a stub.

## Not done yet

- **Distribution.** The app is self-contained but signed ad hoc, so it runs only on the Mac that built it. Shipping needs a first-launch model download manager, Developer ID signing with the hardened runtime, notarisation, and a licence review of everything bundled (the static ffmpeg is a GPL build).
- App icon, a cancel button for running jobs, and editing the outline from the app.
