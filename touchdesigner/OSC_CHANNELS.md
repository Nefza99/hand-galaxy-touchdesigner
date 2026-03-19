# OSC Channel Map v2.2.0

Default UDP port: `7000`

## Core Hand Data

Per-hand namespaces:

- `/galaxy/left/*`
- `/galaxy/right/*`
- `/galaxy/primary/*`
- `/galaxy/secondary/*`
- `/galaxy/main/*`

Common fields:

- `active`
- `x`, `y`
- `thumb_x`, `thumb_y`
- `index_x`, `index_y`
- `world_x`, `world_y`, `world_z`
- `pinch`, `pinch_raw`
- `radius`
- `velocity`
- `dx`, `dy`
- `spin`
- `burst`
- `energy`
- `depth`
- `angle`
- `just_pinched`
- `just_released`

## Colour and Theme

Global effect:

- `/galaxy/effect/r`
- `/galaxy/effect/g`
- `/galaxy/effect/b`
- `/galaxy/effect/hue`
- `/galaxy/effect/saturation`
- `/galaxy/effect/value`
- `/galaxy/effect/amplitude`

Independent hand zones:

- `/galaxy/left_zone/active`
- `/galaxy/left_zone/hue`
- `/galaxy/left_zone/accent_hue`
- `/galaxy/left_zone/saturation`
- `/galaxy/left_zone/value`
- `/galaxy/left_zone/r`
- `/galaxy/left_zone/g`
- `/galaxy/left_zone/b`
- `/galaxy/left_zone/category`

- `/galaxy/right_zone/active`
- `/galaxy/right_zone/hue`
- `/galaxy/right_zone/accent_hue`
- `/galaxy/right_zone/saturation`
- `/galaxy/right_zone/value`
- `/galaxy/right_zone/r`
- `/galaxy/right_zone/g`
- `/galaxy/right_zone/b`
- `/galaxy/right_zone/category`

## Pitch and Audio

- `/galaxy/pitch/hz`
- `/galaxy/pitch/normalised`
- `/galaxy/pitch/band`
- `/galaxy/pitch/confidence`
- `/galaxy/pitch/velocity`

- `/galaxy/audio/amplitude`
- `/galaxy/audio/peak`
- `/galaxy/audio/db`
- `/galaxy/audio/pulse`
- `/galaxy/audio/active`

## Atmosphere

- `/galaxy/atmosphere/feedback`
- `/galaxy/atmosphere/particle_speed`
- `/galaxy/atmosphere/bloom`
- `/galaxy/atmosphere/vignette`
- `/galaxy/atmosphere/shimmer`
- `/galaxy/atmosphere/fog`
- `/galaxy/atmosphere/burst_coeff`
- `/galaxy/atmosphere/band`
- `/galaxy/atmosphere/theme_category`

## Speech

- `/galaxy/speech/letter_ascii`
- `/galaxy/speech/letter_trigger`
- `/galaxy/speech/animal_trigger`
- `/galaxy/speech/animal_id`
- `/galaxy/speech/partial_length`
- `/galaxy/speech/banner_count`
- `/galaxy/speech/phoneme/token_count`
- `/galaxy/speech/phoneme/vowel`
- `/galaxy/speech/phoneme/plosive`
- `/galaxy/speech/phoneme/fricative`
- `/galaxy/speech/phoneme/nasal`
- `/galaxy/speech/phoneme/liquid`
- `/galaxy/speech/phoneme/glide`
- `/galaxy/speech/phoneme/breath`
- `/galaxy/speech/phoneme/affricate`

## Spawn State

- `/galaxy/spawn/count`

## System

- `/galaxy/system/timestamp_ms`
- `/galaxy/system/frame_width`
- `/galaxy/system/frame_height`
- `/galaxy/system/active_hands`
- `/galaxy/system/finger_count`
- `/galaxy/system/finger_count_primary`
- `/galaxy/system/finger_count_secondary`
