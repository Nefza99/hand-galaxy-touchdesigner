# OSC Channel Map

All addresses arrive over UDP OSC on port `7000`.

## System

- `/galaxy/system/timestamp_ms`
- `/galaxy/system/frame_width`
- `/galaxy/system/frame_height`
- `/galaxy/system/active_hands`

## Main Alias

Use these first for the MVP.

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
- `pinch_active`
- `open`
- `just_pinched`
- `just_released`
- `trail_len`

If `--send-landmarks` is enabled, each hand also sends:

- `/galaxy/<slot>/landmark/<n>/x`
- `/galaxy/<slot>/landmark/<n>/y`
- `/galaxy/<slot>/landmark/<n>/z`
- `/galaxy/<slot>/trail/<n>/x`
- `/galaxy/<slot>/trail/<n>/y`

## Suggested TouchDesigner Mappings

- `x`: map `0..1` to your render-space X range
- `y`: invert and map `0..1` to your render-space Y range
- `pinch`: use for inner brightness and compression
- `radius`: use for orbit radius and overall scale
- `velocity`: use for turbulence, noise amount, and streak length
- `spin`: use for angular speed or UV rotation
- `burst`: use for pulse gain, particle emission spikes, and feedback hits
- `energy`: use for trail persistence and bloom intensity
- `depth`: reserve for depth layering or segmentation later

