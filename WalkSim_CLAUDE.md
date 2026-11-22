# WalkSim

First-person walking simulator in **Godot 4.3+** (Forward+, ACES Filmic tonemapping, volumetric fog).
Project path (Mac): `/Users/waynequarmby/Godot/WalkSim`

Workflow: creative direction and architecture come from Gemini chats. Implementation is done by a Grok bot with
access to the local environment, plus Claude Code with the Godot MCP (`npx @coding-solo/godot-mcp`).
This file is the shared brief. Keep the "Work so far" section current.

## Vision

- Tone: **tactile, lived-in architecture suspended in hostile voids**, cold teal / rain / concrete against warm amber / brass.
  Influences: BioShock, Prey (2017), Guillermo del Toro, Blade Runner 2049, Black Mirror, Neuromancer, Cyberpunk 2077,
  Nightmare Alley, The Shape of Water, Interstellar, Mind Flayer scale from Stranger Things.
- **Architectural storytelling**: every space had a clear, mundane purpose before things went wrong; micro-stories in props
  (half-eaten meals, logbooks, mugs, open suitcases). Lighting does most of the work.
- **Cosmic horror, not monsters**: something otherworldly in the distance that never affects the player and can never be
  reached. Scale, silence and indifference. Never over-explained.
- No combat. Walk, look, interact (E).

## Structure

A central hub plus 10 biomes, designed so more can be added indefinitely.

### Hub: The Event Horizon Lounge (own biome)
- Grand dim 1920s Art Deco lounge + 1970s analog listening post: mahogany, velvet, brass, reel-to-reel tape banks, in a
  riveted iron-and-glass conservatory dome.
- View: a colossal slowly churning golden-amber **Gargantua-style black hole** accretion disk fills the dome. Dust motes
  drift very slowly.
- Mechanic: copper coils siphon the black hole's energy into a central **analog cartridge console**. Slot a brass
  tape cartridge, the hub lighting shifts to that biome's palette, and the bulkhead door unseals to that world.
- Adding a biome = add a `BiomeDefinition` `.tres`; the hub scans `res://biomes/` (and mounted `.pck`s) and spawns a
  cartridge on the rack automatically. Godot can export modular `.pck` add-on packs.

### The 10 biomes (each has a locked "distant presence" outside)
1. **Post-Human Porcelain Museum** (#30). Everyday 21st-century relics on pedestals, featureless porcelain mannequins. Outside: impossible fractal void, inverted gravity, ambiguous depth. Modular/procedural loops.
2. **Astral Sleeper Train** (#29). 1920s dining, 1970s sleeper, 1980s neon bar, ending at a glass observation dome. Outside: miles-long ribbon of dark geometric rings parallel to the train; in nebula light they part to reveal something coiled inside. Procedural carriage chain.
3. **Frozen Luxury Cruise Ship** (#20). Art Deco liner tilted 15 degrees in pack ice. Outside: three impossibly tall black obelisks pulsing pale-green aurora outward. Hybrid.
4. **Fog-Bound North Sea Oil Rig** (#16). Fog wall, foghorn every 90s, warm mess hall with half-drunk mugs. Outside: massive pale-obsidian form gliding beneath the rig, groaning the legs. Hybrid.
5. **Orbital Botanical Ring** (#12). Zero-g greenhouse, overgrown hydroponics, floating water sphere. Outside: amber light web spreading across the planet below. Modular/procedural.
6. **Sunken Victorian Conservatory** (#3). Cracked wrought-iron dome holding back the abyssal ocean, bioluminescent willow. Outside: slow constellation of pale violet lights, flank of something mountain-sized. Static hero room.
7. **Midnight Desert Motel & Laundromat** (#26). Neon VACANCY, rain-slick asphalt, three unlocked rooms as frozen vignettes. Outside: red upside-down mist, matte-black inverted pyramid hovering. Static.
8. **Abyssal Hydrothermal Outpost** (Ocean #1). Pressure-sphere research station, black smoker outside the viewport. Outside: tectonic-scale shape drifting past the floodlight edge. Hybrid.
9. **Gas Giant Aerostat Lounge** (Space #6). Art Deco promenade under a buoyancy envelope, ochre clouds, violet storms. Outside: city-sized translucent jellyfish-like entity in the storm. Static.
10. **Pulsar Relay Observatory**. Brutalist telemetry bunker on an asteroid, catwalk to a glass pod. A telescope points *away* from the pulsar. Every 20s the beam sweeps and for 2s reveals a miles-wide silhouette in the dark void. Static.

Palettes, per-biome layouts, soundscapes and storytelling hooks were specified in the Gemini chat. The full detail lives
in the source PDF/chat; ask for it if a biome is being built.

## Technical architecture

```
res://
  core/
    player/PlayerController.tscn   # CharacterBody3D, smooth headbob, raycast interact (E), crosshair dot, speed 3.0
    resources/BiomeDefinition.gd   # custom Resource
    systems/SceneManager.gd        # autoload: async load, 1.5s fade-to-black, Hub <-> Biome
    systems/CosmicDirector.gd      # base class for procedural exterior behaviour
  biomes/
    hub_event_horizon/  EventHorizonLounge.tscn, GargantuaBackdrop.tscn, CartridgeConsole.gd
    01_astral_train/    astral_train.tres, AstralTrainGenerator.tscn, AstralCosmicDirector.gd,
                        modules/ Car_1920s_Dining, Car_1970s_Sleeper, Car_1980s_NeonBar, Vestibule_Connector, Car_ObservationDome
```

`BiomeDefinition` (Resource): `id: StringName`, `display_name`, `cartridge_label`, `hub_ambient_tint: Color = #d98a36`,
`hub_light_energy: float = 1.2`, `level_scene_path` (`*.tscn`), `ambient_preview_audio: AudioStream`.
Also needs a locked-cosmic-asset reference (e.g. `MotelInvertedPyramid.tscn`).

**Rule: identity is locked, behaviour is procedural.** What the exterior phenomenon *is* never changes per biome.
`CosmicDirector` varies *how and when* it appears: weighted random windows (e.g. 45-110s, no fixed timer), randomised
heading/depth/speed/intensity, audio pitch shifts, and optional gaze-aware triggers (fires when the player looks away
or turns back to a window).

Build approach: hybrid. Static hand-crafted hero rooms plus modular/procedural connectors. Cosmic horror is
procedural everywhere.

### Hub spec
Octagonal/circular lounge, radius 14m, height 12m. Zones: Observation Rim, Siphon Dais (centre), Bulkhead Alcove (rear).
Nodes: `EventHorizonLounge/` Architecture (StaticBody3D), Props_ArtDeco, SiphonDais (CopperCoils emissive pulse synced to hum, CartridgeRack, AnalogConsole Area3D), BulkheadDoor, Audio_HubAmbience (sub-bass hum, faint vinyl crackle).
Palette: accretion/key light `#FF9E3D` (DirectionalLight3D through dome ribs), practical lamps `#FFD27D`, mahogany `#2B1810`,
brass `#8C6D3F` (metallic 0.85, rough 0.35), velvet teal `#14363A`, exterior void `#040508`. Dust motes GPUParticles3D `time_scale 0.25`.
Gargantua backdrop: unlit black sphere r=400m at z=-800m, two intersecting emissive torus meshes (disk + lensed halo),
scrolling noise + Fresnel shader `#FF9E3D` to `#FFF3D6`, no raymarching.

### Astral Train spec (Biome 01)
Linear along -Z; modules have EntrySocket/ExitSocket Marker3D. Vestibule start (rear door = return to hub), chain of carriages
from 3 era pools with Vestibule_Connector between, never the same era twice in a row, cap with hand-built `Car_ObservationDome`.
Palettes: 1920s lamps `#FFB84D`, carpet `#4A1219`; 1970s panel `#4E311F`, curtains `#C48B28`; 1980s neon `#D92B8A` / `#24D9E6`;
dome seats `#101828`, nebula `#1A0F2E` / `#2D6A73`.
`AstralCosmicDirector`: ring ribbon at x=+120m; train static, starfield scrolls; nebula pocket cycles 35-80s (`#3A7D8C` / `#6E2C5E`);
reveal: rings part along a sine curve 4-6s showing a coiled silhouette, then snap back; low metallic resonance, duck interior jazz.

## Work so far

Grok built a first vertical slice (Hub + Astral Train, 8 carriages) from the spec above. **Result: not impressive.**
Gemini's diagnosis (agreed by the user):
1. Code-built geometry is sterile: primitives, flat colours, no PBR. Code is good for systems, poor at set dressing.
2. 8 sparse carriages is a treadmill. 2-3 tightly packed, cluttered cars are far more atmospheric.
3. The payoff did not escalate: the nebula and rings are visible from every window, so the dome is not a reveal. Hide the reveal until the dome, or change the scale (blinds mostly drawn, dome looks straight *up*).

(Grok bot's own workings and file state: **TODO, user to supply**.)

## Direction going forward

- Grok/Claude write the **systems** (console, scene loader, directors); **art comes from real assets**: free PBR textures from Poly Haven / AmbientCG, vintage props from Sketchfab (check licences). Blender for custom props.
- Lean on lighting and post: ambient near zero, SDFGI or VoxelGI, volumetric fog, tight warm spotlights with real shadows, film grain + vignette + colour-grading LUT.
- Build **one tiny dense diorama first** (e.g. the Motel lot plus one room, or one heavily cluttered 1920s carriage where every table tells a story), then scale.
- Open choice offered by Gemini: (a) upgrade the visual pipeline with a concrete Godot 4 lighting/shader/PBR checklist, or (b) redesign the Astral Train as a tight 3-car experience with interactive storytelling props. Not yet decided.

## Open items
- Decide (a) vs (b) above.
- Get Grok's implementation notes and current repo state into this file.
- Source-chat detail not captured here (some PDF text was clipped): full per-biome blueprints for #12, #3, #26, #1, #6.
