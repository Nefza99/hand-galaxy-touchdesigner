# Hand Galaxy for TouchDesigner

Real-time hand tracking in Python with MediaPipe, streaming expressive OSC controls into TouchDesigner for a glowing, feedback-heavy galaxy effect.

## What You Get

- Live webcam hand tracking with MediaPipe Hand Landmarker in `LIVE_STREAM` mode
- Smoothed `midpoint`, `pinch`, `velocity`, `spin`, `burst`, `energy`, and `depth` channels over OSC
- Support for one or two hands
- Optional virtual camera output so TouchDesigner can still ingest a live feed while Python owns the physical webcam
- A TouchDesigner build guide, OSC map, and DAT helper script for procedural galaxy instances

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
    NETWORK_SETUP.md
    OSC_CHANNELS.md
    dat_scripts/
      generate_spiral_table.py
```

## Quick Start

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

The MVP TouchDesigner rig only needs the `main` alias:

- `/galaxy/main/x`
- `/galaxy/main/y`
- `/galaxy/main/pinch`
- `/galaxy/main/radius`
- `/galaxy/main/velocity`
- `/galaxy/main/spin`
- `/galaxy/main/burst`
- `/galaxy/main/energy`
- `/galaxy/main/depth`
- `/galaxy/main/just_released`

There are also `/galaxy/primary/*` and `/galaxy/secondary/*` paths for two-hand interaction.

Full channel details live in [touchdesigner/OSC_CHANNELS.md](touchdesigner/OSC_CHANNELS.md).

## Camera Strategy

If Python opens the webcam directly, TouchDesigner usually cannot read the same physical camera at the same time. You have three workable paths:

1. Use the Python preview only while building the interaction.
2. Enable `--virtual-cam` and point TouchDesigner `Video Device In TOP` at the virtual camera.
3. Use a second camera device for TD.

## TouchDesigner Build

Use [touchdesigner/NETWORK_SETUP.md](touchdesigner/NETWORK_SETUP.md) as the wiring guide.

The short version:

1. Bring OSC in on port `7000`.
2. Smooth and map `main/x`, `main/y`, `main/pinch`, `main/velocity`, `main/spin`.
3. Generate a spiral instance table with the helper DAT script.
4. Instance particles around the tracked center.
5. Add blur, level, feedback, and additive composite.
6. Feed `burst` into emission, glow gain, or feedback mix for the magic hit.

## Recommended First Pass

- One hand only
- Virtual camera on
- `640-900` instances
- `1-2` low-res blur passes
- feedback amount tied to `energy`
- burst tied to release, not continuous pinch

## Tuning Notes

- Lower camera resolution first if latency climbs.
- Smooth the OSC controls, not the camera image.
- `pinch` is normalized so closed is near `1.0`.
- `radius` is already shaped for visible scale changes.
- `spin` comes from thumb/index angular change, which feels better than simple left-right speed for swirling particles.
