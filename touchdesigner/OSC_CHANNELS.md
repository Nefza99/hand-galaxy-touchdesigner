# OSC Channel Map

All addresses arrive over UDP OSC on port `7000`.

## System

- `/galaxy/system/timestamp_ms`
- `/galaxy/system/frame_width`
- `/galaxy/system/frame_height`
- `/galaxy/system/active_hands`

## Main Alias

Use these first for the fastest build.

- `/galaxy/main/active`
- `/galaxy/main/x`
- `/galaxy/main/y`
- `/galaxy/main/pinch`
- `/galaxy/main/radius`
- `/galaxy/main/velocity`
- `/galaxy/main/spin`
- `/galaxy/main/burst`
- `/galaxy/main/energy`
- `/galaxy/main/depth`
- `/galaxy/main/hue`
- `/galaxy/main/accent_hue`
- `/galaxy/main/color_r`
- `/galaxy/main/color_g`
- `/galaxy/main/color_b`
- `/galaxy/main/palette`
- `/galaxy/main/shimmer`
- `/galaxy/main/ribbon`
- `/galaxy/main/flare`
- `/galaxy/main/vortex`
- `/galaxy/main/turbulence`
- `/galaxy/main/halo`
- `/galaxy/main/pulse`
- `/galaxy/main/just_pinched`
- `/galaxy/main/just_released`
- `/galaxy/main/pinch_active`
- `/galaxy/main/open`

## Per-Hand Namespaces

Each hand is also sent under:

- `/galaxy/primary/*`
- `/galaxy/secondary/*`

Shared fields under those namespaces:

- `active`
- `handedness`
- `score`
- `x`
- `y`
- `x_raw`
- `y_raw`
- `thumb_x`
- `thumb_y`
- `index_x`
- `index_y`
- `wrist_x`
- `wrist_y`
- `world_x`
- `world_y`
- `world_z`
- `pinch_raw`
- `pinch`
- `radius`
- `velocity`
- `dx`
- `dy`
- `spin`
- `burst`
- `energy`
- `depth`
- `angle`
- `hue`
- `accent_hue`
- `saturation`
- `value`
- `color_r`
- `color_g`
- `color_b`
- `palette`
- `shimmer`
- `ribbon`
- `flare`
- `vortex`
- `turbulence`
- `halo`
- `pulse`
- `pinch_active`
- `open`
- `just_pinched`
- `just_released`
- `trail_len`

## Fusion Namespace

Two-hand interaction is sent under:

- `/galaxy/fusion/active`
- `/galaxy/fusion/x`
- `/galaxy/fusion/y`
- `/galaxy/fusion/distance`
- `/galaxy/fusion/angle`
- `/galaxy/fusion/converge`
- `/galaxy/fusion/symmetry`
- `/galaxy/fusion/bridge`
- `/galaxy/fusion/bloom`
- `/galaxy/fusion/vortex`
- `/galaxy/fusion/chaos`
- `/galaxy/fusion/pulse`
- `/galaxy/fusion/hue`
- `/galaxy/fusion/accent_hue`
- `/galaxy/fusion/color_r`
- `/galaxy/fusion/color_g`
- `/galaxy/fusion/color_b`

## Optional Landmark Output

If `--send-landmarks` is enabled, each hand also sends:

- `/galaxy/<slot>/landmark/<n>/x`
- `/galaxy/<slot>/landmark/<n>/y`
- `/galaxy/<slot>/landmark/<n>/z`
- `/galaxy/<slot>/trail/<n>/x`
- `/galaxy/<slot>/trail/<n>/y`

## Suggested TouchDesigner Mappings

- `x`, `y`: tracked render center
- `pinch`: core intensity and particle compression
- `radius`: overall spread and orbit multiplier
- `velocity`: turbulence, streak length, and particle drift
- `spin`: angular orbit speed or UV rotation
- `burst`: one-shot flashes, particle spikes, and feedback hits
- `energy`: trail persistence and bloom intensity
- `hue`, `accent_hue`: base and secondary color control
- `color_r/g/b`: direct RGB drive for material or TOP color
- `palette`: select or blend between palette rows
- `shimmer`: sparkle density, twinkle masks, or spec hits
- `ribbon`: trail thickness, line opacity, or longer streak particles
- `flare`: core flare size and white-hot highlight gain
- `vortex`: inward pull, swirl power, or corkscrew deformation
- `turbulence`: noise amount, displace strength, or field chaos
- `halo`: blur radius, outer glow size, and aura scale
- `pulse`: low-frequency gain wobble or rhythmic scale pulse
- `fusion/bridge`: beam opacity between hands
- `fusion/bloom`: midpoint orb intensity
- `fusion/converge`: drive portals or merge-state transitions
- `fusion/chaos`: destabilize shapes when hands fight each other
