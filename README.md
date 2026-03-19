# Hand Galaxy v2.1 for TouchDesigner

Real-time hand tracking + live speech recognition + **pitch-driven atmospheric effects** wired into TouchDesigner via OSC.

**Version: `2.1.3`**

---

## What is New in v2.1 — Pitch Update

| Feature | Module |
|---|---|
| Shared audio pipeline — mic used by both speech and pitch simultaneously | audio_pipeline.py |
| Real-time YIN pitch detection via aubio with built-in numpy fallback | pitch_detector.py |
| Adaptive vocal range calibration — self-tunes to your voice in ~30 s | vocal_range_tracker.py |
| Five atmospheric zones driven by vocal pitch band | pitch_effect_mapper.py |
| OpenCV atmospheric overlays: vignette, fog, aurora, corona bloom, sparkle | atmospheric_overlay.py |
| Pitch blended into the effect colour state alongside gesture | effect_colour_state.py (updated) |
| Vertical pitch meter in the HUD | ui_overlay.py (updated) |
| Pitch and atmosphere OSC channels for TouchDesigner | osc_bridge.py (updated) |
| GUI launcher built with tkinter — no extra dependencies | installer/launcher_gui.py |
| Windows setup wizard — double-click setup.bat | setup.bat |
| PyInstaller build script to produce HandGalaxy.exe | installer/build_exe.ps1 |

---

## Quick Start

### Option A — Double-click setup wizard (recommended)

1. Double-click **setup.bat**
2. The 7-step wizard will:
   - Create the Python virtual environment
   - Install core dependencies plus speech packages and the optional aubio backend
   - Download the MediaPipe hand model (~9 MB)
   - Download the Vosk speech model (~40 MB)
   - Create launcher .bat files and a Desktop shortcut
3. Double-click **Launcher.bat**, **Launch-Auto.bat**, or the Desktop shortcut
4. Click **LAUNCH** in the GUI

### Option B — PowerShell launcher

```powershell
.\scripts\start-hand-galaxy.ps1
```

### Option C — Manual run

```powershell
$env:PYTHONPATH = "$PWD\src"
pip install -r requirements.txt
pip install "vosk>=0.3.45" "pyaudio>=0.2.14"   # optional, enables speech + mic features
pip install aubio   # optional, improves pitch tracking if available
python -m hand_galaxy.main
```

If `aubio` is unavailable on your machine, Hand Galaxy will use its built-in
numpy pitch fallback automatically.

---

## Atmospheric Zones — Pitch to Visual Mapping

Vocal pitch frequency drives one of five atmosphere states. The system adapts to your specific voice range automatically.

| Band | Hz Range | Name | Colour | Visual Feel |
|---|---|---|---|---|
| 0 | below 120 Hz | VOID | near-black / deep indigo | Maximum feedback, dark fog tendrils, crushing weight |
| 1 | 120 to 250 Hz | DEEP | violet / midnight blue | Slow cosmic drift, long trails, violet nebula haze |
| 2 | 250 to 500 Hz | FLOWING | teal / cyan | Natural speech zone — aurora shimmer, balanced energy |
| 3 | 500 to 800 Hz | RADIANT | orange / gold | Energetic corona bloom, faster particles, warm light |
| 4 | above 800 Hz | CELESTIAL | white / pale cyan | Crystal sparkle, lens shimmer, full brightness surge |

**Pitch velocity (rising vs falling) also modulates the effect:**
- Rising pitch: brighter, desaturated, burst coefficient spikes, shimmer increases
- Falling pitch: deeper colour, more saturated, heavier trail feedback

---

## Project Layout

```
hand-galaxy-touchdesigner/
  assets/
    animals/               Drop PNG/JPG images here: cat.png, bee.png, etc.
  installer/
    launcher_gui.py        Tkinter GUI launcher
    build_exe.ps1          Build HandGalaxy.exe via PyInstaller
  models/
    hand_landmarker.task   Downloaded by setup.bat
    vosk/                  Downloaded by setup.bat
  scripts/
    start-hand-galaxy.ps1
    download-vosk-model.ps1
  src/hand_galaxy/
    audio_pipeline.py      Shared mic source — NEW v2.1
    pitch_detector.py      Aubio YIN + numpy fallback pitch detection — NEW v2.1
    vocal_range_tracker.py Adaptive range calibration — NEW v2.1
    pitch_effect_mapper.py Pitch to visual parameters — NEW v2.1
    atmospheric_overlay.py OpenCV atmosphere layers — NEW v2.1
    effect_colour_state.py Gesture + pitch blended — UPDATED v2.1
    ui_overlay.py          Pitch meter added — UPDATED v2.1
    osc_bridge.py          Pitch and atmosphere channels — UPDATED v2.1
    config.py              Pitch settings added — UPDATED v2.1
    main.py                Pitch wired into main loop — UPDATED v2.1
    speech_input.py        Uses shared AudioPipeline — UPDATED v2.1
    finger_counter.py      Unchanged from v2.0
    letter_parser.py       Unchanged from v2.0
    animal_insect_parser.py Unchanged from v2.0
    colour_mapper.py       Unchanged from v2.0
    asset_loader.py        Unchanged from v2.0
    gestures.py            Unchanged from v1
    virtual_camera.py      Unchanged from v1
  touchdesigner/
    NETWORK_SETUP.md       Updated with atmosphere nodes
    OSC_CHANNELS.md        Updated with pitch and atmosphere channels
  setup.bat                Windows setup wizard — NEW v2.1
  requirements.txt         Core + speech dependencies
  VERSION.txt
```

---

## Launch Options

```powershell
# Full features
.\scripts\start-hand-galaxy.ps1

# No speech, no pitch — hands only (fastest)
python -m hand_galaxy.main --no-speech --no-pitch

# No atmospheric overlay (keeps pitch colour but removes OpenCV effects)
python -m hand_galaxy.main --no-atmosphere

# Pitch drives 100 percent of the colour — ignore gesture colour
python -m hand_galaxy.main --pitch-weight 1.0

# Gesture drives 100 percent — v1 behaviour, pitch disabled
python -m hand_galaxy.main --no-pitch

# Change image highlight style
python -m hand_galaxy.main --highlight-style rim

# Lower confidence threshold (more sensitive to quiet or soft voices)
python -m hand_galaxy.main --pitch-confidence-thresh 0.40

# Virtual camera for TouchDesigner
python -m hand_galaxy.main --virtual-cam
```

---

## Building a Standalone .exe

After running setup.bat:

```powershell
cd installer
.\build_exe.ps1
```

Output: `dist\HandGalaxy\HandGalaxy.exe`

Distribute the entire `dist\HandGalaxy\` folder. The exe is the GUI launcher and does not bundle the Python runtime for the tracker itself — so the target machine still needs the .venv. For a fully portable build, run setup.bat on the target machine first, then use the exe as the entry point.

---

## Vocal Range Calibration

The system calibrates to your voice automatically over the first ~30 seconds of use.

- Talk, hum, sing, or make any voiced sound
- The tracker collects a rolling buffer of confirmed voiced frames
- It computes the 5th and 95th percentile of your Hz range and adjusts normalisation
- A naturally low voice and a naturally high voice both get the full 0–1 normalised range
- Calibration resets on restart — each session learns fresh

---

## Adding Animal Images

Drop images into `assets/animals/`. Name them after the keyword:

```
assets/animals/cat.png
assets/animals/butterfly.png
assets/animals/bee.png
assets/animals/dragonfly.jpg
```

PNG with transparency works best. JPG is fine. 320x320 or larger recommended.
If an image is missing, a labelled placeholder is shown — the app never crashes on a missing file.

---

## TouchDesigner — New OSC Channels

See `touchdesigner/OSC_CHANNELS.md` for the complete map.

New atmosphere channels to wire directly to effect controls:

```
/galaxy/atmosphere/feedback       → Feedback TOP opacity
/galaxy/atmosphere/bloom          → Level TOP brightness / glow gain
/galaxy/atmosphere/particle_speed → Orbit speed multiplier
/galaxy/atmosphere/shimmer        → Sparkle / noise texture opacity
/galaxy/atmosphere/fog            → Haze density
/galaxy/atmosphere/vignette       → Edge crush
/galaxy/atmosphere/burst_coeff    → Burst emission multiplier
/galaxy/atmosphere/band           → Band index 0-4 for custom logic
/galaxy/pitch/hz                  → Raw Hz for pitch-reactive anything
/galaxy/pitch/normalised          → 0-1 within your vocal range
/galaxy/pitch/velocity            → Hz/s — positive = rising
```

---

## Version 3 Suggestions

- Gesture-triggered spawning: pinch in front of an animal to spawn it at hand position
- Hand-controlled image positioning and scaling
- Spoken sentences forming a rolling text banner
- Volume / amplitude as a separate visual channel alongside pitch
- Phoneme visualisation from Vosk partial results
- Multiple simultaneous colour zones: left hand and right hand independent
- Semantic colour themes by spoken word category
- Animated GIF and sprite sheet support for animal images
- Custom keyword JSON files for any word category
- MIDI output so pitch and gesture drive hardware synths
