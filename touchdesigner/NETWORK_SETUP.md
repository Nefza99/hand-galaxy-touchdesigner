# TouchDesigner Network Setup  v2.2.0

This extends the older guide with:

- left/right independent hand zones
- amplitude and phoneme buses
- spawn count and rolling speech support
- semantic colour zones for custom keyword categories
- all existing pitch and atmosphere channels

---

## New OSC Channels (v2.2)

Python sends these every frame on port 7000.

### Pitch

```
/galaxy/pitch/hz            raw fundamental frequency in Hz
/galaxy/pitch/normalised    0-1 within the user's vocal range
/galaxy/pitch/band          0-4 atmosphere zone index
/galaxy/pitch/confidence    0-1 aubio YIN confidence
/galaxy/pitch/velocity      Hz/s — positive = rising pitch
```

### Atmosphere (pre-mapped, ready to wire)

```
/galaxy/atmosphere/feedback        0-1   trail persistence
/galaxy/atmosphere/particle_speed  0-1   orbit speed multiplier
/galaxy/atmosphere/bloom           0-1   glow / brightness
/galaxy/atmosphere/vignette        0-1   dark edge crush
/galaxy/atmosphere/shimmer         0-1   sparkle intensity
/galaxy/atmosphere/fog             0-1   haze density
/galaxy/atmosphere/burst_coeff     0-1   burst emission boost
/galaxy/atmosphere/band            0-4   zone index
```

### New in v2.2

```
/galaxy/audio/amplitude            0-1   loudness lane
/galaxy/audio/pulse                0-1   transient energy
/galaxy/speech/banner_count        count of active sentence strips
/galaxy/speech/phoneme/*           per-family phoneme intensity
/galaxy/spawn/count                active spawned media count
/galaxy/left_zone/*                left-hand semantic colour state
/galaxy/right_zone/*               right-hand semantic colour state
```

---

## Minimal v2.1 Node Additions

### 1. Atmosphere Select CHOP

Create **Select CHOP** named `select_atmosphere`:
- Channels: all `/galaxy/atmosphere/*` channels

```
select_atmosphere  →  lag_atmosphere  →  null_atmosphere_ctrl
```

`lag_atmosphere` settings: 0.06 on all channels — matches Python smoothing speed.

### 2. Pitch Select CHOP

Create **Select CHOP** named `select_pitch`:
- Channels: all `/galaxy/pitch/*` channels

```
select_pitch  →  null_pitch_ctrl
```

No lag needed — Python already smooths pitch.

### 3. Wire Atmosphere to Galaxy Controls

Replace hardcoded values in your existing network:

| Was hardcoded | Now driven by |
|---|---|
| Feedback TOP opacity | `null_atmosphere_ctrl[galaxy_atmosphere_feedback]` |
| Level TOP brightness | `null_atmosphere_ctrl[galaxy_atmosphere_bloom]` |
| Orbit speed Math | `null_atmosphere_ctrl[galaxy_atmosphere_particle_speed]` |
| Burst gain | `null_atmosphere_ctrl[galaxy_atmosphere_burst_coeff]` |

In a **Script CHOP** or **DAT Execute**:

```python
feedback = op('null_atmosphere_ctrl')['galaxy_atmosphere_feedback']
bloom    = op('null_atmosphere_ctrl')['galaxy_atmosphere_bloom']
speed    = op('null_atmosphere_ctrl')['galaxy_atmosphere_particle_speed']

op('feedback1').par.top    = ...   # use feedback value
op('level1').par.brightness = bloom * 2.0 - 1.0
```

### 4. Band-Conditional Effects (optional)

Wire `band` channel to a **Switch COMP** or use in a DAT Execute for
per-band TD logic:

```python
band = int(op('null_atmosphere_ctrl')['galaxy_atmosphere_band'])

band_colours = {
    0: (0.05, 0.0,  0.12),   # void    — near black/indigo
    1: (0.10, 0.02, 0.35),   # deep    — violet
    2: (0.05, 0.60, 0.55),   # flowing — teal
    3: (0.95, 0.55, 0.05),   # radiant — orange
    4: (0.85, 0.95, 1.00),   # celestial — near white cyan
}
r, g, b = band_colours.get(band, (0.5, 0.5, 0.5))
op('constant1').par.colorr = r
op('constant1').par.colorg = g
op('constant1').par.colorb = b
```

### 5. Pitch HUD in TD (optional)

The Python preview already draws a pitch meter. If you want it in TD too:

Create **Text TOP** named `text_pitch`:

```python
hz   = op('null_pitch_ctrl')['galaxy_pitch_hz']
band = int(op('null_pitch_ctrl')['galaxy_pitch_band'])
names = ['VOID', 'DEEP', 'FLOW', 'RADI', 'CELE']
op('text_pitch').par.text = f"{int(hz)}Hz  [{names[band]}]"
```

---

## Atmosphere Behaviour Reference

| Band | feedback | bloom | particle_speed | shimmer | fog | vignette |
|---|---|---|---|---|---|---|
| 0 VOID | 0.90 | 0.15 | 0.10 | 0.0 | 0.70 | 0.85 |
| 1 DEEP | 0.78 | 0.35 | 0.28 | 0.05 | 0.40 | 0.55 |
| 2 FLOWING | 0.60 | 0.55 | 0.55 | 0.15 | 0.10 | 0.20 |
| 3 RADIANT | 0.45 | 0.78 | 0.75 | 0.35 | 0.03 | 0.05 |
| 4 CELESTIAL | 0.30 | 1.00 | 1.00 | 1.00 | 0.0 | 0.0 |

All values are smoothed in Python before transmission so transitions feel organic.
Pitch velocity spikes shimmer and bloom on rising, deepens colour on falling.

---

## Full Node List (v2.1 additions highlighted)

| Node | Type | Purpose |
|---|---|---|
| cam_in | Video Device In TOP | Webcam or virtual camera |
| oscin1 | OSC In CHOP | All OSC data from Python |
| select_main | Select CHOP | Main hand control channels |
| lag_main | Lag CHOP | Smooth hand position |
| null_main_ctrl | Null CHOP | Clean hand output |
| select_fingers | Select CHOP | Finger count |
| null_finger_ctrl | Null CHOP | Finger count output |
| select_speech | Select CHOP | Letter and animal OSC events |
| null_speech_ctrl | Null CHOP | Speech event output |
| select_effect_colour | Select CHOP | Effect RGB channels |
| null_effect_colour | Null CHOP | Effect colour output |
| **select_atmosphere** | **Select CHOP** | **All atmosphere params — NEW** |
| **lag_atmosphere** | **Lag CHOP** | **Smooth atmosphere transitions — NEW** |
| **null_atmosphere_ctrl** | **Null CHOP** | **Atmosphere output — NEW** |
| **select_pitch** | **Select CHOP** | **Pitch hz/norm/band/confidence/velocity — NEW** |
| **null_pitch_ctrl** | **Null CHOP** | **Pitch output — NEW** |
| galaxy_instances | Table DAT | Spiral instance data |
| geo_particles | Geo COMP | Instanced particles |
| render1 | Render TOP | Galaxy render |
| level_particles | Level TOP | Brightness driven by bloom |
| blur_particles | Blur TOP | Soft glow |
| feedback1 | Feedback TOP | Trail driven by feedback |
| composite_glow | Composite TOP | Additive glow |
| text_finger_count | Text TOP | Finger number HUD |
| animal_image | Movie File In TOP | Animal image |
| text_letter_display | Text TOP | Letter HUD |
| composite_final | Composite TOP | Final mix |
| out1 | Out TOP | Output |
