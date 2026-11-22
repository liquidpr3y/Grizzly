# WalkSim — Event Horizon: Project Notes

A complete record of the Godot walking-simulator work done for Wayne Quarmby, written on Sunday 22 November 2026 (Europe/London). The project was parked mid-pass that evening, at Wayne's request, so this file is the hand-off document for when work resumes.

**Current playable copy on the Mac:** `~/Godot/WalkSim`  
**What that copy is:** the Art Deco Event Horizon Lounge (baked lighting) plus the Astral Sleeper Train vertical slice, and the extra Fog-Bound North Sea Oil Rig. It is the 21 November 2026 "hubdeco" build. It does **not** include the later, unfinished pass for CC0 furniture, a much bigger Gargantua, a brighter bulkhead or less bar glare.

**Authoritative box project:** `/workspace/ws2` (Godot 4.7.2, Forward+). An older phase-1 tree remains at `/workspace/walksim` and should not be treated as current.

No project files were changed while writing these notes.

---

## 1. Concept and Wayne's rules

WalkSim is a first-person walking simulator: a hub lounge plus ten cosmic-horror worlds, drawn from Wayne's Gemini world-building brief. The player never fights or solves puzzles. They walk, look, and listen. Cosmic horror stays unreachable and incomprehensible, seen only at a distance — through glass, water, fog, or kilometres of void.

Wayne's rules, held through the build:

- **Procedural atmosphere in all 11 levels** (the hub and the ten worlds). Events use jittered, Poisson-style intervals, never an obvious fixed timer.
- **No rooms changing behind the player.** Procedural layouts are generated once per visit and then stay put. Re-rolling happens only on re-entry, or from Pause → Regenerate.
- **Each level is a finite snapshot of about 10 minutes or less**, dense with visual storytelling, never an endless generator.
- **Cosmic horror is unreachable.** The player can never get to the presence.
- **Keep it modular** so new levels are easy to add.
- **"Keep everything as the brief has described."**

### 1.1 The eleven places

Categories were agreed with Wayne before the vertical-slice rewrite: static (hand-laid vignettes), modular (assembled once per visit from seeded modules), and hybrid (hand-built landmarks plus seeded connective layout). The names, cosmic hooks and categories below are from the Gemini brief as recorded in the phase-1 environment definitions.

| Brief no. | Place | Type | Brief / cosmic hook |
|---|---|---|---|
| Hub | The Event Horizon Lounge | static | A grand, dim 1920s Art Deco lounge and 1970s analog listening post — mahogany, velvet, brass and humming reel-to-reel banks — in a riveted iron-and-glass dome. A colossal golden-amber accretion disk fills the view and washes the room in permanent sunset light. |
| 01 | The Post-Human Porcelain Museum | modular | Pale galleries of porcelain figures in a museum with broken physics, ending in a single devastating observation window. Outside, an endless pale fog-void where impossibly tall, featureless porcelain silhouettes drift past the horizon. |
| 02 | The Astral Sleeper Train | modular | Dining cars, sleeper cabins and a 270-degree observation dome on a train idling through a starfield. A miles-long ribbon of dark geometric rings runs parallel; occasionally something more shows behind them. |
| 03 | The Frozen Luxury Cruise Ship | hybrid | A gala liner frozen into Antarctic pack ice, tilted 15 degrees: ballroom, promenade, engine room, a frost-encased chandelier over a cracked pool. Three impossibly tall black obelisks lean at identical angles on the ice; a pale-green aurora pulses outward from them. |
| 04 | The Fog-Bound North Sea Oil Rig | hybrid | Grated catwalks in white fog, tea still warm in the mess, a derrick vanishing under a pulsing red beacon. A pale-obsidian mass wider than the rig glides silently beneath the swells. It never breaches. The legs groan. |
| 05 | The Orbital Botanical Ring | modular | A gently curving ring corridor of overgrown hydroponic bays and sterile observation decks around a zero-g willow atrium. On the planet's night side, a perfectly geometric web of amber light slowly spreads across a continent. |
| 06 | The Sunken Victorian Conservatory | static | An iron-and-glass botanical garden on the ocean floor: vaulted nave, rusted catwalks, brass gas-lamps and a bioluminescent willow. A slow-moving constellation of pale violet lights, too symmetrical to be fish, briefly reveals the flank of something mountain-sized. |
| 07 | The Midnight Desert Motel & Laundromat | static | A U-shaped motel lot in a black desert: buzzing VACANCY neon, a fluorescent laundromat, three unlocked rooms frozen like vignettes. Under a churning crimson mist, a colossal matte-black inverted pyramid hovers, edged by silent red lightning. |
| 08 | The Abyssal Hydrothermal Outpost | hybrid | Claustrophobic pressure spheres and bolted tunnels ending in an acrylic bay facing a roaring black-smoker vent. Vague, tectonic-scale movement in the dark beyond the floodlights; the sonar pings something colossal. |
| 09 | The Gas Giant Aerostat Lounge | static | An Art Deco promenade under a buoyancy envelope above endless ochre cloud bands; every departure DELAYED INDEFINITELY. A city-sized translucent jellyfish drifts through the violet storm. |
| 10 | The Pulsar Relay Observatory | static | A brutalist telemetry bunker in an asteroid shard, an exposed catwalk, and a glass observation pod. The pulsar beam sweeps every 20 seconds; for two seconds it illuminates the miles-wide silhouette of something colossal and motionless in the void. |

### 1.2 Numbering in the current project

The **current** tree (`/workspace/ws2`, and the copy on the Mac) resorted the folders when the vertical slice was built, so cartridge numbers no longer match the Gemini brief:

| Current folder / cartridge | Brief number (use this as the intended identity) |
|---|---|
| `biomes/01_astral_train` — "01 · ASTRAL" | Brief **02** |
| `biomes/02_north_sea_oil_rig` — "02 · RIG" | Brief **04** |
| `biomes/03_porcelain_museum` — "03 · SEALED" | Brief **01** |
| `biomes/04_frozen_cruise_ship` — "04 · SEALED" | Brief **03** |
| `biomes/05` … `10` | Same as the brief (05–10) |

The eight unbuilt worlds are present only as sealed `BiomeDefinition` `.tres` files (descriptions and hub tints, no level scene). `BiomeDefinition` also dropped the phase-1 `cosmic_hook`, `palette` and `build_type` fields; those live in this document and in `/workspace/walksim/environments/*/def.tres`. When new worlds are built, restore the brief numbering and hooks unless Wayne says otherwise.

---

## 2. The vertical-slice spec

After the first primitive prototype, Wayne supplied a full vertical-slice spec for the **hub plus the Astral Train**. The current architecture follows that spec. The slice is a closed loop of about ten minutes:

1. Spawn in the Event Horizon Lounge, looking toward the Siphon Dais, the chandelier, and Gargantua in the viewport.
2. Take a brass cartridge from the rack on the dais (E). The centre crosshair dot turns amber over anything usable.
3. Slot it into the reel-to-reel AnalogConsole. The lounge tint shifts toward the biome's colour, coils and the tint ring respond, and the rear bulkhead unseals.
4. Walk through the bulkhead threshold to board the Astral Train. Carriages are generated once per visit and never change behind you.
5. Slide each vestibule door open with E and walk the cars to the Observation Dome.
6. From the dome, watch the ribbon of interlocking dark rings at **x = +120 m**. Every **35–80 s** a nebula pocket washes the windows in **#3A7D8C** or **#6E2C5E**. At its peak the rings part for **4–6 s** and a colossal dark tendrilled silhouette shows behind them, about **900 m** away. It never approaches. Interior audio ducks under a metallic resonance, then the rings close and the nebula fades.
7. Return home via the rear bulkhead of the first vestibule, or the brass eject slot in the dome.

**Controls:** WASD move at 3 m/s, Shift sprint (5 m/s), mouse look, E interact, Esc pause (Resume / Return to Lounge / Regenerate / Quit).

**Playable today:** the Lounge, the Astral Train, and the Oil Rig as an extra hybrid biome beyond the slice. Everything else is a sealed cartridge.

Wayne later asked for much higher visual fidelity (Prey 2017 meets BioShock for the lounge) and said building everything from scratch was burning usage, so the next visual work should prefer free CC0 models and textures.

---

## 3. Architecture

Godot project name: **WalkSim - Event Horizon**. Main scene: `res://biomes/hub_event_horizon/EventHorizonLounge.tscn`. Autoloads: `Sfx`, `HUD`, `SceneManager`. Viewport 1600×900. Features: Godot 4.7, Forward Plus.

### 3.1 Folder layout (current tree)

```
core/player/PlayerController.tscn/.gd   CharacterBody3D, 3 m/s walk, head bob, E raycast, carry
core/resources/BiomeDefinition.gd       class_name BiomeDefinition (one .tres per biome)
core/systems/SceneManager.gd            autoload: biome discovery, async load, 1.5 s fades, safe mode
core/systems/CosmicDirector.gd          base class for every biome's jittered (Poisson) event layer
core/systems/Sfx.gd, Build.gd           procedural audio (Interior bus for ducking); primitive builders
core/ui/HUD.gd                          crosshair dot, prompts, titles, fade, pause menu
core/shaders/                           Metal-safe shaders (see §5)
core/textures/                          CC0 Poly Haven PBR sets + generated marble/brass/grime
core/interaction/Interactable.gd
biomes/hub_event_horizon/               Lounge scene, builders, cartridges, bulkhead, director
biomes/01_astral_train/                 train generator, director, five module scenes
biomes/02_north_sea_oil_rig/            extra playable hybrid biome
biomes/03..10_*/                        sealed BiomeDefinition .tres only
addons/lightmap_baker/                  editor plugin for command-line LightmapGI baking
tools/Bake.tscn, bake.gd, Autotest.gd, aabb.gd
assets/polyhaven/                       CC0 models downloaded for the parked pass (not yet in the Lounge scene)
```

The older phase-1 tree (`/workspace/walksim`) used `environments/`, an `EnvironmentDef` resource, a hard-coded `LevelRegistry`, `scripts/scene_loader.gd` and `AtmosphereDirector`. That layout was replaced by the scan-based biome system above and should not be extended.

### 3.2 BiomeDefinition fields

`core/resources/BiomeDefinition.gd`:

| Field | Role |
|---|---|
| `id` | StringName, e.g. `&"astral_train"` |
| `display_name` | Title shown on the HUD and door label |
| `cartridge_label` | Short rack label, e.g. `"01 · ASTRAL"` or `"07 · SEALED"` |
| `description` | Longer flavour text |
| `hub_ambient_tint` | Colour the Lounge shifts toward when this cartridge is slotted. Default `#d98a36` |
| `hub_light_energy` | Energy for practicals after slotting. Default `1.2` |
| `level_scene_path` | Path to the level `.tscn`. Empty means the cartridge is sealed |
| `ambient_preview_audio` | Optional AudioStream |
| `sort_order` | Rack / scan order |

There is **no registry to edit**. The Lounge scans `res://biomes/` and any mounted `.pck` packs.

### 3.3 SceneManager

Autoload. Moves between the hub and biomes with a **1.5 s** fade to black, a threaded load of the target scene, a swap, and a fade back in.

- Hub constant: `res://biomes/hub_event_horizon/EventHorizonLounge.tscn`
- `go_to_biome(def)`, `return_to_hub()`, `reload_current()`
- `scan_biomes()` mounts packs then walks `res://biomes/*` for `.tres` / `.res` (and `.remap` in exported builds), keeps every `BiomeDefinition`, and sorts by `sort_order`
- Packs are mounted from `user://biome_packs/` and `<executable>/biome_packs/`
- `safe_mode` is on when the user passes `--safe`, or when the renderer is Compatibility (`gl_compatibility`). `apply_safe()` then disables glow, shadows, volumetric fog, SSAO, SSR and SDFGI (volumetric fog is replaced with cheaper ordinary fog)

### 3.4 CosmicDirector

Base class for every biome's atmosphere layer. Subclass it (as `HubCosmicDirector` and `AstralCosmicDirector` do) and override `_setup_events()`.

- Events fire on an exponential (Poisson) inter-arrival around a mean, with multiplicative jitter, clamped to min/max. Nothing runs on a fixed clock.
- `"major"` events (silhouettes, lightning, fog thinning) keep a randomised breathing gap (`major_gap`, default 10–25 s) between each other.
- Helpers: `random_trajectory()`, `envelope()`, `bell()`, `thin_fog()`, `cue()` (procedural `Sfx` plus a `cue_fired` signal for real audio later).
- Things it moves are always unreachable.

### 3.5 Hub cartridge loop

Runtime script: `EventHorizonLounge.gd`.

- On ready, `_fill_rack()` asks `SceneManager.scan_biomes()` and spawns one `Cartridge` per definition on `CartridgeRack/SlotOrigin` (5 across, then down).
- Slotting into `AnalogConsole/CartridgeSlot` emits `cartridge_inserted`. Practical lights in the `practical` group tween toward the biome tint, the `TintRing` and `coil` group follow, the indicator lamp goes green, the door label takes the biome name, reel speed rises, and `BulkheadDoor.unseal()` runs.
- Crossing `BulkheadThreshold` while the door is open calls `SceneManager.go_to_biome(selected)`.
- Lighting is baked; only the tint light, indicator and emissives change at runtime.

Required node names and groups (scripts look these up — do not rename):

- Lounge: `AnalogConsole/CartridgeSlot`, `CartridgeRack/SlotOrigin`, `BulkheadDoor`, `BulkheadThreshold`, `IndicatorLamp`, `IndicatorLight`, `DoorLabel`, `ThresholdGlow`, `TintRing`, `LightmapGI`, `WorldEnvironment`, `GargantuaBackdrop`
- Gargantua: `AccretionDisk`, `LensedHalo`, `TransitShape`, and (after the deco pass) `BlackHole`
- Groups: `practical`, `reel`, `coil`
- Train: `EntrySocket` / `ExitSocket`, `SlidingDoor`, `ClinkSource`, `JazzSource`, `ReturnSlot`, groups `car_light` and `optional`

**HubCosmicDirector events** (lamp flicker was removed so it could not fight the baked lighting):

| Event | Mean | Range | What it does |
|---|---|---|---|
| `silhouette_transit` (major) | 150 s | 60–400 s, first 40–120 s | A hidden shape drifts across the disk, scaled to the black hole |
| `disk_flare` (major) | 55 s | 20–160 s | Accretion / halo shader `flare` parameter swells for 3–8 s |
| `tape_cue` | 50 s | 15–150 s | A click |
| `deep_swell` | 90 s | 30–240 s | A low groan |

### 3.6 Train module chain

`AstralTrainGenerator.gd` builds the train **once per visit** from a seed (`fixed_seed == 0` means a new layout every visit) and then leaves it alone.

Order along −Z:

1. A start `Vestibule_Connector` whose rear bulkhead returns to the Lounge
2. **5–8 carriages** drawn from three era pools, **never the same era twice in a row**, each joined by a vestibule with a sliding door
3. Always the hand-crafted `Car_ObservationDome`

Era pools (add variety by dropping another `.tscn` into a pool):

- `1920s` — `Car_1920s_Dining.tscn`
- `1970s` — `Car_1970s_Sleeper.tscn`
- `1980s` — `Car_1980s_NeonBar.tscn`

Each module is a `TrainModule` root with `EntrySocket` and `ExitSocket` (`Marker3D`). The generator snaps each module's Exit to the next Entry. Props in the `optional` group are shown or hidden at random on each visit (`randomize_props`). The universe (starfield, nebula, debris) scrolls toward +Z at **38 m/s**; the train itself is stationary.

`ModuleBuilder.gd` + `TrainSceneBuilder.gd` are the bake-time builders for those scenes. Hand-tune the saved `.tscn` files in the editor; re-running the default bake overwrites them.

### 3.7 Astral director: timings and palettes

`AstralCosmicDirector.gd`:

- Ribbon of interlocking, slowly rotating dark rings at **x = +120 m**, weaving above and below the carriage line (holders spaced 26 m, two rings per link, rim colour around `(0.55, 0.4, 0.9)`).
- Nebula pocket every **weighted-random 35–80 s**. Window / sky / `NebulaLight` ramp to one of `POCKET_COLORS`: **`#3a7d8c`** or **`#6e2c5e`**. Ramp up 5–8 s, hold 4–6 s, ramp down 5–9 s (faster when tests call `trigger_reveal()`).
- At the peak the rings part on a sine for the hold, centred near the player's Z. A rim-lit tendrilled silhouette (body radius 210, 11 tendrils) becomes visible at roughly **x = 900 m**. It never moves closer. Interior bus ducks **−20 dB**. Then the rings close and the pocket fades.
- Minor events: `rail_clatter` (mean 2.6 s, 1.2–6), `glass_clink` (14 s, 4–45, from `ClinkSource` nodes), `light_flicker` (45 s, 15–150, `car_light` group), `frame_groan` (110 s, 45–300).

---

## 4. Tooling

### 4.1 Scene baker — `tools/Bake.tscn` + `tools/bake.gd`

```text
godot --path . res://tools/Bake.tscn
```

**Warning:** this regenerates code-built scenes and **overwrites hand edits**.

- Default (or `-- --only=gargantua` / `-- --only=train`): rebuilds `GargantuaBackdrop.tscn` and the train modules / generator. The Lounge is **not** rebuilt, because it is hand-tunable and carries a baked lightmap.
- `-- --only=hub`: rebuilds `EventHorizonLounge.tscn` from `HubBuilder.gd` + `DecoKit.gd` (and also rebuilds Gargantua). **Lighting must then be re-baked.**

### 4.2 Lightmap baker — `addons/lightmap_baker/`

Godot 4.7 has no script API for `LightmapGI.bake`, so a small editor plugin drives the editor's own **Bake Lightmaps** button.

```text
godot -e --path . -- --bake-lighting
godot -e --path . -- --bake-lighting=res://some/scene.tscn
```

Default scene: the Lounge. It opens the editor, finds `LightmapGI`, emits the button, saves, and quits. Lightmap data is `EventHorizonLounge.lmbake` plus `EventHorizonLounge.exr`.

`LightmapGI` must be a **direct child of the scene root** — it bakes its parent's subtree. Quality in the builder: medium, 3 bounces, denoiser on, interior, custom environment colour, probe subdiv 8, `texel_scale` 1.0.

On the box a bake takes about 3–5 minutes; the Mac `.command` comment says about a minute on Apple GPUs. (An earlier note said 3–5 minutes on the Mac as well — treat that as a range.)

### 4.3 `Bake Hub Lighting.command`

On the Mac, after hand-editing the Lounge (moving lamps or furniture), double-click:

```text
~/Godot/WalkSim/Bake Hub Lighting.command
```

That is:

```bash
/Applications/Godot.app/Contents/MacOS/Godot -e --path . -- --bake-lighting
```

Moving things without re-baking leaves old shadows behind but does no other harm. Inside the editor you can also select `LightmapGI` and click **Bake Lightmaps**.

### 4.4 Autotest and lookdev

```text
godot --path . -- --autotest [--fast] [--shots=/dir] [--lookdev] [--lookdev-only]
```

The test walks the whole loop: hub → take the Astral cartridge → slot it → bulkhead opens → threshold → train → every vestibule door → Observation Dome → nebula pocket + reveal (rings part, silhouette visible, interior ducked) → rear bulkhead → hub → oil rig → hub. It prints `[autotest] PASS/FAIL` lines and exits non-zero on failure.

- `--fast` teleports between doors instead of walking the carriages.
- `--shots=/dir` writes screenshots when not headless (default `/tmp/ws2_shots`).
- `--lookdev` first poses eight Lounge cameras (L1–L8) and six walk frames (W0–W5) to inspect lighting and flicker. Views: spawn, bar, lounge seating, pit, bulkhead, dais close, ceiling, wall detail, then a slow walk from `(1.5, 0.05, 8.0)`.
- `--lookdev-only` quits after those shots.
- `--ssao` (Lounge runtime, not autotest) turns SSAO on. It is off by default and untested on Metal.
- `--safe` is the safe-mode flag (see §5).

On the box, `/workspace/hubcycle.sh <outdir>` was used to run lookdev cycles during the deco polish.

### 4.5 Launchers

All live in the project root and `cd` to that folder, then invoke `/Applications/Godot.app/Contents/MacOS/Godot`:

| File | What it does |
|---|---|
| `Launch WalkSim (Metal).command` | Forward+ on Metal — the default, try this first |
| `Launch WalkSim (Safe Metal).command` | Metal Forward+ plus `-- --safe` (no volumetric fog, glow or shadows) |
| `Launch WalkSim (Vulkan).command` | MoltenVK, Forward+ |
| `Launch WalkSim (Compatibility).command` | OpenGL / `gl_compatibility` (safe mode turns on automatically) |

If the Mac GPU times out, use those fallbacks in that order. You can also open `project.godot` in Godot and press F5.

---

## 5. Metal crash investigation and fixes

Early Play-in-window runs on Wayne's Mac (Apple M5 Pro, Godot 4.7.2 stable) hit **"rendering driver timed out."**

Causes, from the Godot tracker:

- **[godot#119436](https://github.com/godotengine/godot/issues/119436):** the Godot 4.7 Metal driver times out on any GPU frame longer than 1 second.
- **[godot#115893](https://github.com/godotengine/godot/issues/115893):** MSAA can also freeze the Metal driver.

Fixes applied and still in force:

- **MSAA off**, **FXAA on** (`anti_aliasing/quality/screen_space_aa=1` in `project.godot`).
- **Cheap sky lighting pass:** sky radiance size **32 px**, and the hub sky is static (`PROCESS_MODE_QUALITY`, no `TIME`), so it is not re-rendered every frame.
- **SSAO, SSR and SDFGI off** by default. SSAO can be opted into with `-- --ssao` but has not been proven on Metal.
- **Shader loops limited to 4 or fewer**, and no `while` loops in shaders.
- **`pow` and divides clamped** against NaN (MSAA / far-horizon extrapolation was a known source of `pow` of a negative).
- Gargantua is **not** a live raymarcher in the running game. The deco backdrop is a black sphere plus torus meshes with `gargantua_ring.gdshader` (two fixed octaves of noise, radial gradient, Fresnel).
- Volumetric fog volume size/depth is kept modest (48) in project settings, and the Lounge disables volumetric fog entirely.
- **`--safe`** (and Compatibility automatically): no volumetric fog, glow or shadows, and SSAO/SSR/SDFGI forced off.

Logs on the Mac, if a timeout comes back:

```text
~/Library/Application Support/Godot/app_userdata/WalkSim - Event Horizon/logs/godot.log
```

Any new Gargantua work must stay inside these limits. The parked "much bigger black hole" plan is a **pre-rendered** texture on a quad, not a heavier live shader.

---

## 6. Hub flicker and the Art Deco rebuild

### 6.1 Flicker diagnosis

Wayne reported that the Lounge looked acceptable on spawn in a static room, but as soon as he moved, shadows and light flickered everywhere. The cause was four things at once:

1. A **low-angle realtime directional "sun"** (Gargantua light) with cascaded shadow maps (PSSM) that **re-fitted every time the camera moved**. Head bob made this worse.
2. **Volumetric fog** temporal reprojection, which smears frames together and shimmers while walking.
3. A **sky shader driven by `TIME`**, so radiance was re-rendered every frame and the lighting from it kept shifting.
4. A **scripted `lamp_flicker` event** on practicals, adding to the swimming look.

### 6.2 The fix

The Lounge now uses **baked lighting** (`LightmapGI`) so nothing is recalculated while you walk:

- Every lamp, sconce, the chandelier and the amber window key light are **`BAKE_STATIC`**. They are baked into `EventHorizonLounge.exr` and cost nothing at runtime.
- There are **no realtime directional shadows**.
- Two **ReflectionProbes** (`LoungeProbe`, `BarProbe`) use **`UPDATE_ONCE`**.
- The only dynamic lights are the dais tint light and the bulkhead indicator, and neither casts shadows. Cartridge meshes are GI-dynamic so they can be picked up.
- Window light shafts are **cheap additive meshes** (`light_shaft.gdshader`), not volumetric fog.
- The hub sky has no `TIME` and a 32 px radiance map, rendered once.
- `lamp_flicker` was removed from `HubCosmicDirector` (the `_flicker` function remains in the file but is not registered).

In six lookdev walk frames (W0–W5) rendered on the box, the light stayed steady.

### 6.3 Art Deco restyle (Prey 2017 meets BioShock)

The Lounge was rebuilt in code (`HubBuilder.gd` + `DecoKit.gd`) and saved as `EventHorizonLounge.tscn`. Layout in metres, **−Z faces Gargantua**:

- Hall **18 × 22 m**, coffered ceiling **7.2 m** with a stepped recess and a crystal chandelier over the Siphon Dais.
- Marble floors with brass inlay and a chevron runner from the bulkhead to the dais.
- Observation pit (z < −6.5, 0.45 m lower) in front of a stepped Deco viewport (about 13 m wide in the **deployed** scene).
- Bar along the left wall with bottles; leather lounge groups on the right; reel-to-reel bank rear right.
- Brass coil pillars around the central dais and the cartridge console / rack.
- Bulkhead portal in the rear wall (+Z) → tunnel → threshold.
- Story props (including a suitcase and hat by the bulkhead — someone meant to leave), grime decals, and a draped dust sheet over one chair.
- Tonemap: AGX, exposure 1.15, soft glow, very light exponential fog (density 0.006). Key light colour `#ff9e3d`, energy 2.4, bake-static, aimed in through the viewport.
- Player spawn: `(0, 0.05, 7.6)`, facing the dais, chandelier, then Gargantua.

**Deployed Gargantua** (still the one on the Mac): `BlackHole` at `(0, 227, −1700)`, **scale 0.5**, black unshaded sphere radius 400, nearly edge-on accretion torus and a vertical lensed halo, using `gargantua_ring.gdshader`. Wayne has since said this is still much too small (see §10).

Polish rounds on the box, before deploy:

- Round 1: first deco render (`/tmp/ld1`), full autotest PASS in Forward+.
- Round 2: softer generated marble, dimmer `frosted_dim`, coil energy 0.9, Gargantua y 227 / scale 0.42, marble specular 0.85 (`/tmp/ld2`).
- Round 3 (the shipped look): marble `metallic_specular` **0.65**, darker `frosted_dim` (energy 0.38), draped dust sheet, Gargantua scale **0.5**. `/tmp/ld3` walk frames were stable.

Known look issues called out at deploy, **not yet fixed** in the shipped scene:

- The **bulkhead end is quite dark**.
- There is **strong glare on the floor near the bar**.

### 6.4 Textures and credits

`core/textures/CREDITS.txt`: all textures in that folder are **CC0 (public domain) from [Poly Haven](https://polyhaven.com)**. Sets (1k JPG: albedo, normal GL, roughness):

- `black_walnut_veneer_01`, `rosewood_veneer1`, `marble_01` (the shipped marble materials actually use the **generated** marble, not this set), `brown_leather`, `velour_velvet`, `quatrefoil_jacquard_fabric`, `plastered_wall_04`, `metal_plate`

Procedurally generated for this project, in `core/textures/generated/` (see `/workspace/tools_gen/marble.py`): cream / black / green marble albedo and roughness, brass roughness, grime stain and streak decals, and grey-tinted velvet / jacquard used as tintable bases.

DecoKit materials built from those: walnut, mahogany, three marbles (clearcoat, `metallic_specular` 0.65), brass / brass_dark / copper, leather, oxblood, velvet, rug_red / rug_teal, plaster, iron, mirror, frosted / frosted_dim, amber_strip, window glass, shelf glass.

Lookdev and contact-sheet screenshots from the shipped deco pass: `/workspace/hub_screens/` (L1–L8, W0–W5, `contact_sheet.png`, plus a Compatibility spawn shot). Earlier previews: `/workspace/hub_preview/`.

---

## 7. Version history and archives

Times below are Europe/London.

| When (UK) | What | Where |
|---|---|---|
| Thu 20 Nov 2026, 20:26 | **Phase 1** zip: primitive hub + Astral Train + Oil Rig, `environments/` architecture, no external assets | Box: `/workspace/walksim_phase1.zip` (root folder `walksim/`). Unpacked tree still at `/workspace/walksim`. Mac copy: `~/Godot/walksim_phase1.zip` |
| Thu 20 Nov 2026, evening | Re-architecture to the vertical-slice spec (`biomes/`, `BiomeDefinition` scan, `SceneManager`, `CosmicDirector`, launchers, Metal-safety work) | Current descendant is `/workspace/ws2` |
| Thu 20 Nov 2026, 22:16 | **Vertical-slice** zip | Box: `/workspace/walksim_vslice.zip` (root folder `WalkSim/`). Mac copy: `~/Godot/walksim_vslice.zip` |
| Fri 21 Nov 2026, afternoon | Art Deco Lounge + baked lighting, three lookdev rounds | `/workspace/ws2` |
| Fri 21 Nov 2026, 16:13 | **hubdeco** zip built after final tests | Box: `/workspace/walksim_hubdeco.zip` (root folder `WalkSim/`, ~60 MB) |
| Fri 21 Nov 2026, after 16:13 | Deployed to the Mac. Previous vslice copy backed up first. Mac headless autotest passed | **Live project:** `~/Godot/WalkSim` **Backup of the previous vslice:** `~/Godot/WalkSim_backup_vslice` **Zip copies on the Mac:** `~/Godot/walksim_hubdeco.zip`, `~/Godot/walksim_vslice.zip`, `~/Godot/walksim_phase1.zip` |
| Fri 21 Nov 2026, ~21:11–21:18 | "Round B" started: CC0 models, bigger viewport in `HubBuilder.gd`, offline black-hole textures and shaders | Only on the box, in `/workspace/ws2`. **Not baked, not deployed.** The Mac still has Friday afternoon's deco Lounge |
| Sun 22 Nov 2026, evening | Wayne asked to park the work | Left as above |

A full Godot 4.7.2 Linux editor also lives on the box at `/workspace/Godot_v4.7.2-stable_linux.x86_64` (and a `/workspace/godot.zip`).

---

## 8. Testing done, and its limits

**On the box (Linux, Godot 4.7.2):**

- After the deco bake, final autotests were recorded as **PASS**: headless 24 checks, Forward+ 24, Compatibility 27.
- Lookdev L1–L8 and walk frames W0–W5 were inspected visually; lighting did not swim between walk frames.

**On the Mac:**

- A **headless** autotest of the deployed hubdeco build was run and reported **24 PASS, 0 FAIL**.
- The deco Lounge and the flicker fix have **not been seen on Wayne's Metal GPU in a window**. Confirmation of "does it still flicker, and how does it feel" is still outstanding.
- Wayne **did** play an earlier, pre-deco build in a window: he found the graphics basic (correct — it was the gameplay-loop prototype, primitive meshes only) and reported the flicker that the bake was meant to fix.

Until Wayne launches `Launch WalkSim (Metal).command` and reports back, treat Metal-in-a-window as unproven for the deco lighting and for any later Gargantua change.

---

## 9. Usage notes and prioritisation

During the deco rebuild a usage check (same week, before the Friday 27 November 2026, 11:22 UK reset) showed about **32.5%** of that week's allowance used. There is no on-demand overspend: when the allowance runs out, work stops until the reset. Hub rebuilds are expensive (build, screenshot, adjust, repeat).

Agreed priority, still the plan when work resumes:

1. **Finish the Lounge** and get a version Wayne is happy with onto the Mac (flicker confirmed gone in a window, black hole at the right scale, bulkhead and bar glare addressed, real CC0 furniture rather than more primitive modelling).
2. **Give the Astral Train the same visual treatment**, so the one complete loop looks good.
3. **Then the other nine worlds**, roughly one or two a week after weekly resets. Suggested next worlds after the train: **07 Desert Motel**, then **10 Pulsar Observatory** (both static vignettes).

To keep usage down: test each build and give one batch of feedback rather than many small rounds; prefer CC0 models and textures over modelling from scratch; keep Metal-safe lighting baked where a space is static.

---

## 10. Parked and pending work

Wayne asked to park mid-pass on Sunday 22 November 2026 (Europe/London). The Mac was left on the Friday afternoon deco Lounge. The box project `/workspace/ws2` has **partial, unbaked, undeployed** "Round B" changes from later on Friday 21 November (~21:11–21:18 UK). Resume from the box, not by assuming the Mac is current.

### 10.1 What Round B set out to do

Wayne's brief for this pass:

- Fetch **external CC0 textures and models** (Poly Haven, Kenney, ambientCG, Quaternius, and similar) instead of spending usage modelling from scratch.
- Make **Gargantua much, much bigger** — filling most of the window, towering over the room, with the feeling of "how is it possible to be this close to a supermassive black hole and not be torn apart" — **without** bringing back a heavy live shader that would crash Metal.
- In the same pass, **lift the dark bulkhead end** and **reduce the glare near the bar**.

None of those three visual goals has been delivered to the Mac.

### 10.2 Partial changes already in `/workspace/ws2`

**CC0 models downloaded, not integrated.** `/workspace/ws2/assets/polyhaven/` holds **18** Poly Haven 1k glTF models, about 40 MB, fetched with `/workspace/tools_gen/ph_dl.py` (Poly Haven API, `gltf/1k`). They are **not** referenced by `HubBuilder.gd` or instanced in `EventHorizonLounge.tscn`. Import `light_baking` was pre-set: large furniture **2** (static, UV2 for the lightmap), small props **3** (dynamic).

| light_baking = 2 (static / UV2) | light_baking = 3 (dynamic) |
|---|---|
| `bar_chair_round_01`, `Ottoman_01`, `GreenChair_01`, `coffee_table_round_01`, `vintage_grandfather_clock_01`, `sofa_03`, `mid_century_lounge_chair` | `tea_set_01`, `brass_vase_01`, `marble_bust_01`, `vintage_radio_transceiver`, `wine_bottles_01`, `brass_goblets`, `CashRegister_01`, `mantel_clock_01`, `potted_plant_02`, `fancy_picture_frame_01`, `vintage_suitcase` |

`tools/aabb.gd` is a headless helper that prints each model's mesh count and world AABB, for placement. It was added in this pass.

**Wider viewport in `HubBuilder.gd` only.** The builder was edited so the stepped (ziggurat) opening is as large as the wall allows, with slimmer mullions, a single low transom, a larger glass quad (15.4 × 7.1 m), and clocks pushed out to x = ±8.5. The comment in the file is "Gargantua has to loom." **This has not been baked.** The saved `EventHorizonLounge.tscn` and the Mac still have the older, smaller opening (outer step 6.5 × 5.0, glass 13 × 6.5 m). Lighting, bar and bulkhead energies were **not** changed in this edit, so the dark bulkhead and bar glare are still outstanding even in the builder.

**Offline Gargantua started, not wired in.**

- `/workspace/tools_gen/blackhole.py` — an offline Schwarzschild ray tracer. Usage: `python3 blackhole.py <out_dir> <W> <H> <R_OBS> <INC_deg> <R_OUT>`. Chosen parameters recorded in the progress scratch: observer radius **~8**, inclination **2°**, outer disk **7.5**, **140°** horizontal FOV pinhole, intending a quad at distance **D = 1200**.
- Generated textures (21:17–21:18 UK, 21 Nov), **not used by the running backdrop**: `core/textures/gargantua/gargantua_color.png`, `gargantua_hit.png`, `gargantua_glow.png`, `disk_streaks.png`.
- New shaders, **not used by `GargantuaBuilder.gd`**: `core/shaders/gargantua_lensed.gdshader`, `core/shaders/gargantua_glow.gdshader`.
- `GargantuaBuilder.gd` and the baked `GargantuaBackdrop.tscn` are still the Friday-afternoon torus-and-ring setup at **scale 0.5**.

`EventHorizonLounge.exr` / `.lmbake` / `.tscn` timestamps remain **16:06–16:07 UK, 21 November** — the deployed deco bake. Rebuilding the hub from the current `HubBuilder.gd` without a new lightmap bake would drop the baked lighting.

### 10.3 Still to do, in order

1. Integrate the CC0 models (and any further textures) into the Lounge; keep large pieces lightmap-static.
2. Finish a Metal-safe **huge** Gargantua: prebaked texture (or an equally cheap unshaded/quad setup), filling the window, overwhelming scale, no heavy per-frame raymarch. Widen the viewport (already sketched in the builder) as part of that.
3. Lift the dark bulkhead end; reduce the glare near the bar (floor reflection / exposure / bar lights / shaft strength — whatever the lookdev shows).
4. `godot --path . res://tools/Bake.tscn -- --only=hub`, then re-bake lighting, then full autotest (headless, Forward+, Compatibility) and lookdev shots.
5. Backup the Mac copy, deploy, and wait for Wayne to test **in a Metal window**.
6. Astral Train visual pass (same CC0-first approach).
7. Remaining worlds, starting with **07 Desert Motel** and **10 Pulsar Observatory**. Keep each one a dense ≤10-minute snapshot, with procedural atmosphere and unreachable cosmic horror, matching the brief in §1.1.

---

## 11. How to resume

1. **Do not start from the Mac tree as if it were latest.** Copy or work in `/workspace/ws2` on the box. The Mac `~/Godot/WalkSim` is the 21 November 16:13 UK hubdeco build. The previous vslice is already at `~/Godot/WalkSim_backup_vslice`.
2. Re-read this file, `/workspace/ws2/README.md`, and the short scratch log `/workspace/walksim_hub_progress.md`.
3. Continue Round B in `/workspace/ws2` as in §10.3. Do not run `-- --only=hub` until you are ready to re-bake lighting in the same sitting.
4. After a green autotest, zip the project (include `.godot` minus shader cache/editor junk, and the `.exr` / `.lmbake` lightmaps). On the Mac, back up the current `~/Godot/WalkSim` first, then replace it, and run a headless autotest there.
5. Ask Wayne to launch **`Launch WalkSim (Metal).command`** and report flicker, scale of the black hole, bulkhead darkness, bar glare, and how the furniture feels. Fall back through Safe Metal → Vulkan → Compatibility if the driver times out.
6. Only then start the train visual pass.

**Handy commands** (from the project root, box or Mac):

```bash
# Rebuild Lounge scenes from HubBuilder + DecoKit (overwrites the .tscn)
godot --path . res://tools/Bake.tscn -- --only=hub

# Re-bake Lounge lightmaps (editor; use the .command on the Mac)
godot -e --path . -- --bake-lighting

# Full loop test
godot --path . -- --autotest
godot --path . -- --autotest --lookdev --shots=/tmp/lookdev
godot --path . -- --autotest --lookdev-only --shots=/tmp/lookdev

# Measure downloaded Poly Haven model bounds
godot --path . --headless --script res://tools/aabb.gd
```

Wayne's Godot is 4.7.2 stable. The box editor is `/workspace/Godot_v4.7.2-stable_linux.x86_64`.
