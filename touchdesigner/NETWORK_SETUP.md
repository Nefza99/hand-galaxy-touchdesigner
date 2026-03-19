# TouchDesigner Network Setup

This is the fastest strong-looking build path for the upgraded effect pack.

## 1. Camera Branch

Use one of these:

- `videodevicein1` pointed at your normal webcam
- `videodevicein1` pointed at the virtual camera produced by the Python app

Rename it to `cam_in`.

Then:

```text
cam_in -> null_cam
```

## 2. OSC Branch

Create:

```text
oscin1 -> null_osc_raw
```

Set `oscin1`:

- Network Port: `7000`
- Protocol: UDP

Create `Select CHOP`s or `Rename CHOP`s for these channels first:

- `galaxy_main_x`
- `galaxy_main_y`
- `galaxy_main_pinch`
- `galaxy_main_radius`
- `galaxy_main_velocity`
- `galaxy_main_spin`
- `galaxy_main_burst`
- `galaxy_main_energy`
- `galaxy_main_hue`
- `galaxy_main_accent_hue`
- `galaxy_main_shimmer`
- `galaxy_main_ribbon`
- `galaxy_main_flare`
- `galaxy_main_vortex`
- `galaxy_main_turbulence`
- `galaxy_main_halo`
- `galaxy_main_pulse`
- `galaxy_fusion_bridge`
- `galaxy_fusion_bloom`
- `galaxy_fusion_converge`

Then add:

```text
select_main -> math_main -> lag_main -> null_main_ctrl
```

Suggested mapping in `math_main`:

- `x`: from `0..1` to `-0.95..0.95`
- `y`: from `0..1` to `0.55..-0.55`
- `radius`: from `0..1` to `0.08..0.64`
- `velocity`: from `0..2.2` to `0..1`
- `spin`: keep centered, maybe clamp to `-3..3`
- `burst`, `energy`, `shimmer`, `ribbon`, `flare`, `vortex`, `turbulence`, `halo`, `pulse`: clamp to `0..1`
- `hue`, `accent_hue`: leave in `0..1`
- `fusion_bridge`, `fusion_bloom`, `fusion_converge`: clamp to `0..1`

Use `Lag CHOP` so position is silky but not mushy:

- `x/y`: `0.08 - 0.14`
- `radius`: `0.05 - 0.08`
- `velocity/spin`: `0.04 - 0.08`
- `burst/flare`: `0.02 - 0.05`
- `halo/pulse/ribbon/shimmer`: `0.05 - 0.09`

## 3. Palette DAT

Create a `Table DAT` named `galaxy_palettes`.

Add a `Text DAT` and paste in:

[dat_scripts/generate_palette_table.py](dat_scripts/generate_palette_table.py)

Run:

```python
build(op('galaxy_palettes'))
```

This gives you six strong palette families you can blend with `main/palette` or bypass completely and use the direct `color_r/g/b` OSC channels.

## 4. Galaxy Instance Source

Create a `Table DAT` named `galaxy_instances`.

Add a `Text DAT` and paste in:

[dat_scripts/generate_spiral_table.py](dat_scripts/generate_spiral_table.py)

Run:

```python
build(op('galaxy_instances'), count=1080, arms=6, turns=7.6)
```

The upgraded table gives you more variation columns:

- `core`
- `spark`
- `ribbon`
- `dust`

Use those to split particles into a brighter core, streak set, and faint dust layer without building three separate systems from scratch.

## 5. Instancing Rig

Create:

```text
tableDAT -> datto1 -> null_inst_source
circle1 or sphere1 -> geo_particles
cam1
light1
render1
```

Recommended source geometry:

- `circle1` with low divisions if you want soft sprite-like points
- `sphere1` if you want chunkier stars

In `geo_particles`, enable instancing from the table data:

- Use `tx`, `ty`, `tz` as base offsets
- Use `pscale`, `scale`, `phase`, and `spark` as variation inputs
- Use `core` to make a brighter inner set
- Use `ribbon` to stretch a subset of particles into streaks
- Use `dust` to fade a far, low-alpha layer

Drive the final transform with:

- base table offsets
- plus `main/x` and `main/y` as center translation
- plus time-based orbit from `phase`
- plus `spin` for angular speed
- plus `radius` as a multiplier on base offsets

## 6. Color Recipe

You now have three easy color paths:

1. Direct RGB:
   Use `main/color_r`, `main/color_g`, and `main/color_b` to drive the material color directly.
2. Hue Pair:
   Use `main/hue` and `main/accent_hue` to mix two gradients in a Ramp TOP or GLSL MAT.
3. Palette Lookup:
   Use `main/palette` to blend between rows in `galaxy_palettes`.

The nicest look usually comes from mixing 1 and 2:

- material base from direct RGB
- highlight band from `accent_hue`
- palette only for larger scene mood shifts

## 7. Motion Recipe

For each instance, combine:

- base spiral position
- orbital rotation over time
- `turbulence` as small noise offset
- `vortex` as inward pull
- `ribbon` as streak length
- `shimmer` as sparkle density
- `pulse` as slow gain wobble

The look gets better fast if:

- outer points drift more slowly
- inner points are brighter and larger
- `spark` particles respond harder to `shimmer`
- `ribbon` particles stretch more when `velocity` rises

## 8. Render and FX

Use a dedicated render branch:

```text
render1 -> level_particles -> blur_particles -> feedback1 -> composite_glow
```

Suggested post chain:

- `level_particles`: push highlights hard
- `blur_particles`: run at reduced resolution if needed
- `feedback1`: trail amount tied to `energy` and `ribbon`
- `composite_glow`: `Add`

Then:

```text
null_cam + composite_glow -> composite_final -> out1
```

Recommended controls:

- `energy` -> feedback opacity
- `halo` -> blur radius
- `flare` -> core white-hot gain
- `burst` -> one-frame pulse gain
- `velocity` -> turbulence amplitude
- `pinch` -> inner core brightness
- `radius` -> overall galaxy spread
- `spin` -> rotation speed
- `pulse` -> subtle global exposure wobble

## 9. Fusion Upgrades

Once the one-hand rig feels good, add a two-hand branch:

```text
fusion_ctrl -> beam_geo / midpoint_core / portal_mask
```

Map:

- `fusion/x`, `fusion/y` -> midpoint position
- `fusion/bridge` -> beam opacity and thickness
- `fusion/bloom` -> midpoint flare gain
- `fusion/converge` -> portal size or merge-state
- `fusion/vortex` -> twist deformation
- `fusion/chaos` -> noise instability

This is where the “summoning a galaxy between two hands” look really appears.

## 10. Fast Preset Looks

Try these first:

1. `Aurora Bloom`: high `halo`, medium `ribbon`, cooler palette rows
2. `Solar Flare`: high `flare`, high `burst`, warmer palette rows
3. `Neon Prism`: higher `shimmer`, brighter accent hue
4. `Binary Portal`: heavy use of the `fusion/*` branch

More notes live in [EFFECT_RECIPES.md](EFFECT_RECIPES.md).

## 11. Performance Guardrails

- Keep the blur branch below full resolution
- Stay around `800-1300` instances for the main pass
- Smooth control channels instead of brute-forcing more particles
- If FPS dips, reduce feedback resolution before reducing everything else
- Split bright core and dust into two lighter passes before attempting a giant monolithic network
