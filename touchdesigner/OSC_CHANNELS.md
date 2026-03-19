# OSC Channel Map  v2.1.3

All addresses arrive over UDP OSC on port `7000`.

---

## System

| Address | Type | Notes |
|---|---|---|
| `/galaxy/system/timestamp_ms` | float | MediaPipe timestamp |
| `/galaxy/system/active_hands` | float | 0–2 |
| `/galaxy/system/finger_count` | float | Total extended fingers 0–10 |
| `/galaxy/system/finger_count_primary` | float | Primary hand 0–5 |
| `/galaxy/system/finger_count_secondary` | float | Secondary hand 0–5 |

---

## Speech

| Address | Type | Notes |
|---|---|---|
| `/galaxy/speech/letter_ascii` | float | ASCII of last letter (65=A … 90=Z) |
| `/galaxy/speech/letter_trigger` | float | 1.0 pulse; resets to 0 next frame |
| `/galaxy/speech/animal_trigger` | float | 1.0 pulse on animal/insect |
| `/galaxy/speech/animal_id` | float | Sorted keyword list index |

---

## Effect Colour

| Address | Range | Notes |
|---|---|---|
| `/galaxy/effect/r` | 0–1 | Current effect red |
| `/galaxy/effect/g` | 0–1 | Current effect green |
| `/galaxy/effect/b` | 0–1 | Current effect blue |

---

## Pitch  *(new v2.1)*

| Address | Range | Notes |
|---|---|---|
| `/galaxy/pitch/hz` | 0–1300 | Detected fundamental frequency |
| `/galaxy/pitch/normalised` | 0–1 | Within detected vocal range |
| `/galaxy/pitch/band` | 0–4 | Atmosphere zone (0=void … 4=celestial) |
| `/galaxy/pitch/confidence` | 0–1 | aubio YIN confidence |
| `/galaxy/pitch/velocity` | Hz/s | Rate of change — positive = rising |

---

## Atmosphere  *(new v2.1)*

All parameters are smoothed 0–1 values.  Wire directly to TD effect controls.

| Address | Suggested TD use |
|---|---|
| `/galaxy/atmosphere/feedback` | Feedback TOP opacity |
| `/galaxy/atmosphere/particle_speed` | Orbit/rotation speed multiplier |
| `/galaxy/atmosphere/bloom` | Glow gain / Level TOP brightness |
| `/galaxy/atmosphere/vignette` | Edge crush / dark vignette |
| `/galaxy/atmosphere/shimmer` | Sparkle / noise texture opacity |
| `/galaxy/atmosphere/fog` | Haze / atmospheric scatter |
| `/galaxy/atmosphere/burst_coeff` | Burst emission multiplier |
| `/galaxy/atmosphere/band` | Current band index 0–4 |

### Band → atmosphere mapping (for TD custom logic)

| Band | Value | Name | Colour | Feel |
|---|---|---|---|---|
| 0 | 0.0 | VOID | near-black / indigo | crushing depth, max feedback |
| 1 | 0.25 | DEEP | blue / violet | slow cosmic drift |
| 2 | 0.50 | FLOWING | teal / cyan | balanced natural speech zone |
| 3 | 0.75 | RADIANT | orange / gold | energetic, fast particles |
| 4 | 1.00 | CELESTIAL | white / pale cyan | intense shimmer, full brightness |

---

## Main Hand Alias  (unchanged from v1)

`/galaxy/main/x`, `y`, `pinch`, `radius`, `velocity`, `spin`, `burst`, `energy`, `depth`, `active`, `just_pinched`, `just_released`

## Per-Hand Namespaces

`/galaxy/primary/*` and `/galaxy/secondary/*` — same fields as main.
