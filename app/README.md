# Grizzly for Mac

The native SwiftUI front end. It starts the Python engine (`grizzly serve`) from your Grizzly checkout and talks to it over the engine's local HTTP API on `127.0.0.1`. That's the same model Ollama's app uses: a native shell around a local inference server.

```
Grizzly.app (SwiftUI)  ──HTTP 127.0.0.1:8642──▶  grizzly serve (Python: MLX writer, mflux, mlx-video)
      │                                                  │
      └── starts / stops the engine process ─────────────┘
```

## Run it

Requirements: macOS 14 or later, Xcode 16 or later, and the engine already installed in your checkout (`uv pip install -e '.[mac,server,video]'` from the repo root, as in the main README).

Pick one way to run it:

- **Xcode (recommended while developing):** `open app/Package.swift`, pick the **Grizzly** scheme and **My Mac**, then press ⌘R.
- **Terminal:** `cd app && swift run Grizzly`
- **Double-clickable app:** `app/scripts/make-app.sh`, then `open app/build/Grizzly.app`

On first launch the app looks for the engine in `~/Grizzly/.venv`. If your checkout is somewhere else, use **Settings → Choose…** or the button on the "engine isn't running" screen. If an engine is already running on the port (for example `grizzly serve` in a terminal), the app uses it instead of starting its own. Quitting the app stops the engine it started, so model memory is released.

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

GrizzlyCore builds and is tested on Linux too: `GRIZZLY_ENGINE_DIR=/path/to/Grizzly swift test`. The SwiftUI target compiles only on macOS; elsewhere it builds to a stub.

## Not done yet

- **Bundling the engine inside the .app.** Today the app runs the engine from your checkout's `.venv`. Shipping to other people needs a relocatable Python, the MLX packages and ffmpeg inside `Grizzly.app/Contents/Resources`, plus a first-launch model download manager, Developer ID signing and notarisation.
- App icon, a cancel button for running jobs, and editing the outline from the app.
