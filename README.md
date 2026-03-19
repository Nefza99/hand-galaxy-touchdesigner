# Hand Galaxy v2.2.0 for TouchDesigner

Real-time hand tracking, speech, pitch, amplitude, semantic colour themes, animated media, and MIDI output wired into TouchDesigner via OSC.

## What’s New in v2.2

- Gesture-triggered spawning: pinch over the prompted animal image to spawn it onto your hand
- Hand-controlled media: spawned images follow hand position, scale, and motion
- Rolling speech banner: final spoken lines drift across the HUD
- Amplitude channel: mic loudness now drives its own visual lane beside pitch
- Phoneme visualisation: Vosk partials feed a live phoneme-family ribbon
- Independent left/right colour zones: each hand has its own semantic theme and OSC colour bus
- Semantic colour themes: spoken keyword categories tint the effect state
- GIF and sprite-sheet media support
- Custom keyword JSON packs in [`assets/keywords/README.md`](assets/keywords/README.md)
- MIDI output for pitch and gesture hardware control
- Setup fixes: the Windows setup path now installs the media and MIDI helpers correctly and avoids the old batch redirection bug

## Quick Start

### Windows setup

1. Run `setup.bat`
2. Let it create `.venv`, install dependencies, download the MediaPipe and Vosk models, and create launchers
3. Start with `Launch-Auto.bat`
4. Optional: add `--midi` to enable MIDI output

### PowerShell

```powershell
.\scripts\start-hand-galaxy.ps1
.\scripts\start-hand-galaxy.ps1 -Midi
```

### Manual

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install "vosk>=0.3.45" "pyaudio>=0.2.14"
.venv\Scripts\pip install "python-rtmidi>=1.5.8"
$env:PYTHONPATH = "$PWD\src"
python -m hand_galaxy.main
```

## Core Interaction Flow

1. Speak a keyword such as `cat`, `bee`, or a custom JSON keyword
2. The prompt image appears in the centre of the frame
3. Pinch over that prompt to spawn the media onto your left or right hand
4. Move, scale, and throw the spawned image with your hand motion
5. Speech text rolls into the banner while phoneme families and amplitude keep animating the HUD
6. Pitch, amplitude, gesture, speech, spawn, and colour-zone data stream to TouchDesigner over OSC

## Media Support

- Static: `png`, `jpg`, `jpeg`, `webp`, `bmp`, `tif`, `tiff`
- Animated: `gif`
- Sprite sheets: `.json` manifest plus source image

Sprite-sheet manifest example:

```json
{
  "type": "spritesheet",
  "image": "butterfly_sheet.png",
  "frame_width": 256,
  "frame_height": 256,
  "frame_count": 12,
  "fps": 12,
  "loop": true
}
```

## Custom Keywords

Keyword packs are loaded from [`assets/keywords`](assets/keywords). Each file can define categories, theme hues, MIDI note hints, aliases, and asset mappings.

Example:

```json
{
  "categories": [
    {
      "name": "ocean",
      "theme": {
        "hue": 0.55,
        "accent_hue": 0.62,
        "midi_note": 74
      },
      "entries": [
        { "word": "orca", "asset": "whale", "aliases": ["killer whale"] }
      ]
    }
  ]
}
```

## MIDI

Use `--midi` or the PowerShell `-Midi` switch to send:

- note output from live pitch
- CC for amplitude
- CC for hand pinch, position, and gesture energy
- per-hand semantic hue values

If no MIDI backend or hardware port is available, the app stays usable and launches without crashing.

## TouchDesigner

The TouchDesigner hookup docs are here:

- [`NETWORK_SETUP.md`](touchdesigner/NETWORK_SETUP.md)
- [`OSC_CHANNELS.md`](touchdesigner/OSC_CHANNELS.md)

New TD-friendly buses in v2.2 include:

- `/galaxy/left/*` and `/galaxy/right/*`
- `/galaxy/left_zone/*` and `/galaxy/right_zone/*`
- `/galaxy/audio/*`
- `/galaxy/speech/phoneme/*`
- `/galaxy/spawn/count`

## Validation

Validated in this repo with:

- `python -m unittest discover -s tests -v`
- `python -m compileall src tests installer`
- `cmd /c "setup.bat < nul"`
- `cmd /c "Launch-Auto.bat --no-preview --max-seconds 3"`
- `cmd /c "Launch-Auto.bat --midi --no-preview --max-seconds 2"`

Current known limitation:

- `aubio` may still fail to install on some Windows machines; the built-in numpy pitch fallback is used automatically
