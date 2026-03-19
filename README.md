# Hand Galaxy for TouchDesigner

Real-time hand tracking in Python with MediaPipe, streaming expressive OSC controls into TouchDesigner for a glowing, feedback-heavy galaxy effect.

Current release version: `1.1.0`

## What You Get

- Live webcam hand tracking with MediaPipe Hand Landmarker in `LIVE_STREAM` mode
- Smoothed OSC controls for position, pinch, velocity, spin, burst, glow, ribbons, shimmer, turbulence, and pulse
- Rich color telemetry per hand: `hue`, `accent_hue`, `color_r/g/b`, `palette`, `saturation`, `value`
- A two-hand `fusion` bus for portal beams, midpoint blooms, chaos, and convergence effects
- Optional virtual camera output so TouchDesigner can still ingest a live feed while Python owns the physical webcam
- TouchDesigner build docs, palette/effect recipes, and DAT helper scripts for procedural galaxy instances

## Project Layout

```text
hand-galaxy-touchdesigner/
  models/
  scripts/
    download-hand-model.ps1
    start-hand-galaxy.ps1
  src/hand_galaxy/
    config.py
    gestures.py
    main.py
    osc_bridge.py
    virtual_camera.py
  touchdesigner/
    EFFECT_RECIPES.md
    NETWORK_SETUP.md
    OSC_CHANNELS.md
    dat_scripts/
      generate_palette_table.py
      generate_spiral_table.py
```

## Quick Start

If you downloaded the GitHub Release installer:

1. Run `HandGalaxyTouchDesigner-Setup-v1.1.0.exe`.
2. After install, double-click `Hand Galaxy` on your Desktop.
3. Press `1` for the easiest first run in camera-preview mode.
4. Press `2` only if you already have `OBS Virtual Camera` or `UnityCapture` installed for TouchDesigner.

If you are running from source:

1. Install Python 3.10+.
2. Open PowerShell in this folder.
3. Run:

```powershell
.\scripts\start-hand-galaxy.ps1
```

That script will:

- create `.venv`
- install dependencies
- download the official MediaPipe hand model
- launch the tracker on `127.0.0.1:7000`

If you want TouchDesigner to read a virtual camera from the Python app:

```powershell
.\scripts\start-hand-galaxy.ps1 -VirtualCam
```

If you want the tracker with no preview window:

```powershell
.\scripts\start-hand-galaxy.ps1 -NoPreview
```

## Manual Run

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m pip install -r requirements.txt
python -m hand_galaxy.main --osc-host 127.0.0.1 --osc-port 7000
```

Optional virtual camera dependencies:

```powershell
python -m pip install -r requirements-virtualcam.txt
python -m hand_galaxy.main --virtual-cam
```

## Core OSC Controls

The MVP rig still starts with the `main` alias:

- `/galaxy/main/x`
- `/galaxy/main/y`
- `/galaxy/main/pinch`
- `/galaxy/main/radius`
- `/galaxy/main/velocity`
- `/galaxy/main/spin`
- `/galaxy/main/burst`
- `/galaxy/main/energy`
- `/galaxy/main/hue`
- `/galaxy/main/accent_hue`
- `/galaxy/main/shimmer`
- `/galaxy/main/ribbon`
- `/galaxy/main/flare`
- `/galaxy/main/vortex`
- `/galaxy/main/turbulence`
- `/galaxy/main/halo`
- `/galaxy/main/pulse`

There are also `/galaxy/primary/*`, `/galaxy/secondary/*`, and `/galaxy/fusion/*` paths for two-hand interaction.

Full channel details live in [touchdesigner/OSC_CHANNELS.md](touchdesigner/OSC_CHANNELS.md).

## Camera Strategy

If Python opens the webcam directly, TouchDesigner usually cannot read the same physical camera at the same time. You have three workable paths:

1. Use the Python preview only while building the interaction.
2. Enable `--virtual-cam` and point TouchDesigner `Video Device In TOP` at the virtual camera.
3. Use a second camera device for TD.

Note: the release installer includes `pyvirtualcam`, but Windows still needs a virtual-camera backend such as `OBS Virtual Camera` or `UnityCapture` before TouchDesigner mode can open a virtual device.

## TouchDesigner Build

Use [touchdesigner/NETWORK_SETUP.md](touchdesigner/NETWORK_SETUP.md) as the wiring guide.

Then use:

- [touchdesigner/OSC_CHANNELS.md](touchdesigner/OSC_CHANNELS.md) for the full OSC map
- [touchdesigner/EFFECT_RECIPES.md](touchdesigner/EFFECT_RECIPES.md) for ready-made visual directions
- [touchdesigner/dat_scripts/generate_spiral_table.py](touchdesigner/dat_scripts/generate_spiral_table.py) for richer particle layouts
- [touchdesigner/dat_scripts/generate_palette_table.py](touchdesigner/dat_scripts/generate_palette_table.py) for palette DATs

## Recommended First Pass

- One hand only
- `780-1200` instances
- `1-2` low-res blur passes
- `hue/accent_hue` driving color
- `halo` driving bloom radius
- `ribbon` driving trail persistence
- `burst` and `flare` driving central hit flashes
- `fusion/bridge` reserved for the two-hand upgrade

## Tuning Notes

- Lower camera resolution first if latency climbs.
- Smooth the OSC controls, not the camera image.
- `pinch` is normalized so closed is near `1.0`.
- `spin` comes from thumb/index angular change, which feels better than simple left-right speed for swirling particles.
- `hue` and `accent_hue` are intentionally broad so you can move across a lot of the color wheel without switching systems.
- `fusion/*` is where the more dramatic “portal between hands” looks start to happen.
