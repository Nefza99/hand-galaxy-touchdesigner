# TouchDesigner Network Setup

This is the fastest strong-looking build path for the effect.

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

Create `Select CHOP`s or `Rename CHOP`s for these channels:

- `galaxy_main_x`
- `galaxy_main_y`
- `galaxy_main_pinch`
- `galaxy_main_radius`
- `galaxy_main_velocity`
- `galaxy_main_spin`
- `galaxy_main_burst`
- `galaxy_main_energy`
- `galaxy_main_depth`

Then add:

```text
select_main -> math_main -> lag_main -> null_main_ctrl
```

Suggested mapping in `math_main`:

- `x`: from `0..1` to `-0.95..0.95`
- `y`: from `0..1` to `0.55..-0.55`
- `radius`: from `0..1` to `0.08..0.6`
- `velocity`: from `0..2.2` to `0..1`
- `spin`: keep centered, maybe clamp to `-3..3`
- `burst`: clamp to `0..1`
- `energy`: clamp to `0..1`

Use `Lag CHOP` so position is silky but not mushy:

- `x/y`: `0.08 - 0.14`
- `radius`: `0.05 - 0.08`
- `velocity/spin/burst`: `0.04 - 0.08`

## 3. Galaxy Instance Source

Create a `Table DAT` named `galaxy_instances`.

Add a `Text DAT` and paste in:

[dat_scripts/generate_spiral_table.py](dat_scripts/generate_spiral_table.py)

Run:

```python
build(op('galaxy_instances'), count=840, arms=5, turns=7.0)
```

This gives you a strong spiral cloud instead of a flat ring.

## 4. Instancing Rig

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

- Use the generated `tx`, `ty`, `tz` columns as base offsets
- Use `scale`, `pscale`, and `phase` as variation inputs

Drive the final transform with:

- base table offsets
- plus `main/x` and `main/y` as center translation
- plus time-based orbit from `phase`
- plus `spin` for angular speed
- plus `radius` as a multiplier on base offsets

## 5. Motion Recipe

For each instance, combine:

- base spiral position
- orbital rotation over time
- small noise offset scaled by `velocity`
- center pull scaled by `pinch`

The look gets better fast if:

- outer points drift more slowly
- inner points are brighter and larger
- a few instances have longer scales for “streak” particles

## 6. Render and FX

Use a dedicated render branch:

```text
render1 -> level_particles -> blur_particles -> feedback1 -> composite_glow
```

Suggested post chain:

- `level_particles`: push highlights hard
- `blur_particles`: run at reduced resolution if needed
- `feedback1`: trail amount tied to `energy`
- `composite_glow`: `Add`

Then:

```text
null_cam + composite_glow -> composite_final -> out1
```

Recommended controls:

- `energy` -> feedback opacity
- `burst` -> level gain and bloom amount
- `velocity` -> turbulence/noise amplitude
- `pinch` -> inner core brightness
- `radius` -> overall galaxy spread
- `spin` -> rotation speed

## 7. Easy “Awesome” Upgrades

Once the MVP works, add these in order:

1. A central core sprite that flares on `burst`
2. Secondary hand as a color-shift or second attractor
3. Depth-based scale or blur modulation from `depth`
4. A masked glow pass that only blooms high-value particles
5. Trails rendered at half resolution for cheaper persistence

## 8. Performance Guardrails

- Keep the blur branch below full resolution
- Stay around `600-1000` instances for the first version
- Smooth control channels instead of increasing particle count
- If FPS dips, reduce feedback resolution before reducing everything else
