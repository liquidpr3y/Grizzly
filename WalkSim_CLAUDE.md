# WalkSim: Event Horizon

First-person walking simulator in **Godot 4.7.2** (Forward+, Metal on Apple M5 Pro). A hub lounge plus ten cosmic-horror worlds.
Project (Mac): `~/Godot/WalkSim`. Detailed hand-off from the Grok bot: `WalkSim_Project_Notes.md` (keep it next to this file and read it before touching code).

Sources: design brief from Gemini chats; implementation by a Grok bot working in its own sandbox (`/workspace/ws2`);
Claude Code with the Godot MCP (`npx @coding-solo/godot-mcp`) can now work on the Mac.

> **Which copy is current?** The Mac `~/Godot/WalkSim` is the 21 Nov 16:13 "hubdeco" build (Art Deco Lounge, baked lighting, Astral Train, Oil Rig).
> The Grok sandbox `/workspace/ws2` has later **unbaked, undeployed** "Round B" changes (CC0 models, wider viewport, offline black-hole textures).
> Those exist only on Grok's side, so get them from the user (zip) or redo them on the Mac.

## Vision and rules

- Tone: tactile, lived-in architecture suspended in hostile voids; warm amber/brass against cold teal/rain/concrete.
  Influences: BioShock, Prey (2017), del Toro, Blade Runner 2049, Black Mirror, Neuromancer, Interstellar, Mind Flayer scale.
- No combat or puzzles: walk, look, listen, interact (E). Architectural storytelling and micro-stories in props.
- **Cosmic horror is unreachable**: seen only at a distance through glass, water, fog or void; never approaches, never explained.
- **Procedural atmosphere in all 11 levels**: events use jittered Poisson-style intervals, never an obvious fixed timer.
- **No rooms change behind the player.** Layouts are generated once per visit; re-roll only on re-entry or Pause > Regenerate.
- **Each level is a finite snapshot of about 10 minutes or less**, dense, never an endless generator.
- Keep it modular so new levels drop in. "Keep everything as the brief has described."
- The user wants **much higher visual fidelity** and wants to **spend less usage**: prefer free CC0 models/textures (Poly Haven, ambientCG, Kenney, Quaternius; check licences) over modelling from scratch. Code for systems, real assets for art. Lighting and post do most of the work.

## The eleven places

Hub: **Event Horizon Lounge** (static). A dim 1920s Art Deco lounge and 1970s analog listening post in an iron-and-glass dome; a colossal golden-amber accretion disk (Gargantua) fills the view. Copper coils feed an analog cartridge console; slotting a brass cartridge shifts the lounge tint and unseals the bulkhead.

| Brief no. | Place | Type | Cosmic hook |
|---|---|---|---|
| 01 | Post-Human Porcelain Museum | modular | Endless pale fog-void; impossibly tall featureless porcelain silhouettes drift past |
| 02 | Astral Sleeper Train | modular | Ribbon of dark geometric rings parallel to the train; something coiled behind them |
| 03 | Frozen Luxury Cruise Ship | hybrid | Three huge black obelisks on the ice; pale-green aurora pulses outward from them |
| 04 | Fog-Bound North Sea Oil Rig | hybrid | Pale-obsidian mass wider than the rig glides beneath the swells; legs groan |
| 05 | Orbital Botanical Ring | modular | Geometric amber light web slowly spreading across the planet's night side |
| 06 | Sunken Victorian Conservatory | static | Violet light constellation reveals a mountain-sized flank |
| 07 | Midnight Desert Motel & Laundromat | static | Red mist; matte-black inverted pyramid hovering, edged by red lightning |
| 08 | Abyssal Hydrothermal Outpost | hybrid | Tectonic-scale movement past the floodlights; sonar pings something colossal |
| 09 | Gas Giant Aerostat Lounge | static | City-sized translucent jellyfish in the storm; flights DELAYED INDEFINITELY |
| 10 | Pulsar Relay Observatory | static | 20s beam sweep; for 2s reveals a miles-wide silhouette in the void |

**Numbering trap:** current folders were re-sorted: `01_astral_train` = brief 02, `02_north_sea_oil_rig` = brief 04,
`03_porcelain_museum` = brief 01, `04_frozen_cruise_ship` = brief 03; 05-10 match. Restore brief numbering and hooks when building new worlds.
Unbuilt worlds exist only as sealed `BiomeDefinition` `.tres` files (no level scene).

## Architecture (current)

Main scene `res://biomes/hub_event_horizon/EventHorizonLounge.tscn`. Autoloads: `Sfx`, `HUD`, `SceneManager`. Viewport 1600x900.

```
core/player/       PlayerController (CharacterBody3D, 3 m/s, Shift 5, head bob, E raycast)
core/resources/    BiomeDefinition.gd (id, display_name, cartridge_label, description, hub_ambient_tint #d98a36,
                   hub_light_energy 1.2, level_scene_path (empty = sealed), ambient_preview_audio, sort_order)
core/systems/      SceneManager (autoload: scans res://biomes/ and mounted .pck, async load, 1.5s fades, safe mode),
                   CosmicDirector (base class, Poisson events), Sfx, Build
core/ui/HUD.gd     crosshair, prompts, fade, pause menu (Resume / Return to Lounge / Regenerate / Quit)
core/shaders/      Metal-safe shaders;  core/textures/ CC0 Poly Haven sets + generated marble/brass/grime
biomes/hub_event_horizon/, 01_astral_train/, 02_north_sea_oil_rig/, 03..10_*/ (sealed)
addons/lightmap_baker/   editor plugin driving LightmapGI bake from the command line
tools/  Bake.tscn, bake.gd, Autotest.gd, aabb.gd
assets/polyhaven/  18 CC0 glTF models (Grok sandbox only; not yet used in the Lounge)
```

There is no registry: adding a biome = drop a `BiomeDefinition` `.tres` under `res://biomes/`; the rack spawns its cartridge.
**Do not rename** node names or groups that scripts look up (full list in the notes, section 3.5): e.g. `AnalogConsole/CartridgeSlot`,
`CartridgeRack/SlotOrigin`, `BulkheadDoor`, `BulkheadThreshold`, `LightmapGI`, `GargantuaBackdrop`; groups `practical`, `reel`, `coil`, `car_light`, `optional`.

Astral Train: generator builds once per visit from a seed: start vestibule (rear bulkhead returns to hub), **5-8 carriages** from three era pools
(1920s Dining, 1970s Sleeper, 1980s NeonBar; never the same era twice in a row) joined by sliding-door vestibules, always ending in `Car_ObservationDome`.
Ring ribbon at x=+120m; nebula pocket every 35-80s (`#3a7d8c` / `#6e2c5e`); rings part 4-6s revealing a silhouette at ~x=900m; interior bus ducks -20 dB.

## Hard-won technical constraints

- **Metal timeouts** ("rendering driver timed out", godot#119436, #115893): MSAA off, FXAA on; SSAO/SSR/SDFGI off; shader loops <=4, no `while`; clamp `pow`/divides;
  sky radiance 32px and static; modest volumetric fog volume (the Lounge disables it). Any GPU frame >1s kills the driver.
- **Gargantua must not be a live raymarcher.** Planned big version = prebaked texture on a quad. Current = black sphere + torus meshes with `gargantua_ring.gdshader`.
- **Hub flicker was caused by** realtime directional shadows re-fitting while walking, volumetric fog reprojection, a `TIME`-driven sky, and a scripted lamp flicker.
  Fixed with baked `LightmapGI` (lamps `BAKE_STATIC`, `UPDATE_ONCE` reflection probes, no realtime directional shadows, additive light-shaft meshes). Keep static spaces baked.
- `LightmapGI` must be a direct child of the scene root. Bake: `godot -e --path . -- --bake-lighting` (Mac: `Bake Hub Lighting.command`).
- `godot --path . res://tools/Bake.tscn` **overwrites hand edits** of code-built scenes; `-- --only=hub` rebuilds the Lounge and then **lighting must be re-baked**.
- Test: `godot --path . -- --autotest [--fast] [--lookdev]` (24 checks pass headless on the Mac build). Launchers on the Mac: Metal, Safe Metal, Vulkan, Compatibility (`--safe`).
- Mac logs: `~/Library/Application Support/Godot/app_userdata/WalkSim - Event Horizon/logs/godot.log`.

## Status

- Hub (Art Deco, baked) + Astral Train + Oil Rig are playable on the Mac. Eight other worlds are sealed cartridges.
- **Not yet confirmed:** the deco Lounge and flicker fix have not been seen in a Metal window on the user's GPU.
- **Known look issues in the shipped build:** Gargantua far too small; bulkhead end too dark; strong floor glare near the bar; furniture is primitive.
- Round B (Grok sandbox only): 18 CC0 Poly Haven models downloaded but unused; wider viewport sketched in `HubBuilder.gd` (not baked);
  offline Schwarzschild ray tracer `tools_gen/blackhole.py` and textures/shaders for a prebaked Gargantua generated but not wired in.

## Next steps (agreed priority)

1. Finish the Lounge: integrate CC0 furniture (large pieces lightmap-static), huge Metal-safe prebaked Gargantua filling the window, lift the bulkhead end, cut bar glare; rebuild hub, **re-bake**, autotest, lookdev.
2. Back up the Mac copy, deploy, have the user test in a **Metal window** and report flicker, black-hole scale, darkness, glare, furniture feel.
3. Give the Astral Train the same visual pass. Gemini's critique of the first build: 8 sparse cars are a treadmill (prefer 2-3 dense cars with story props),
   and the reveal should not be visible from every window before the dome.
4. Then the other worlds, about 1-2 per week: **07 Desert Motel**, then **10 Pulsar Observatory**.

Working style: test each build and give one batch of feedback rather than many small rounds (usage is limited and there is no overspend).
