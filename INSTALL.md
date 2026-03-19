# Hand Galaxy v2.2.0 Installation Guide

## Option 1: `HandGalaxySetup.exe`

Best for Windows users.

1. Run `HandGalaxySetup.exe`
2. Let the wizard install Python support, dependencies, models, launchers, and shortcuts
3. Launch with `Launch-Auto.bat` or the GUI launcher

The setup now installs:

- MediaPipe + OpenCV + OSC
- speech dependencies
- media helpers for GIF and sprite-sheet playback
- MIDI helpers (`mido` plus optional `python-rtmidi`)

## Option 2: `setup.bat`

Run:

```powershell
cmd /c "setup.bat < nul"
```

This validates the full batch installer path non-interactively and creates:

- `Launch.bat`
- `Launch-Auto.bat`
- `Launch-NoSpeech.bat`
- `Launch-NoPitch.bat`
- `Launch-Minimal.bat`
- `Launch-VirtualCam.bat`
- `Launcher.bat`

## Option 3: PowerShell launcher

```powershell
.\scripts\start-hand-galaxy.ps1
.\scripts\start-hand-galaxy.ps1 -Midi
.\scripts\start-hand-galaxy.ps1 -VirtualCam
```

## Option 4: Manual

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install "vosk>=0.3.45" "pyaudio>=0.2.14"
.venv\Scripts\pip install "python-rtmidi>=1.5.8"
$env:PYTHONPATH = "$PWD\src"
python -m hand_galaxy.main
```

## Useful Launch Flags

```powershell
python -m hand_galaxy.main --no-preview
python -m hand_galaxy.main --midi
python -m hand_galaxy.main --midi-port "Your MIDI Port"
python -m hand_galaxy.main --no-speech
python -m hand_galaxy.main --no-pitch
python -m hand_galaxy.main --virtual-cam
python -m hand_galaxy.main --highlight-style aura
```

## Asset Tips

- Put spoken-word media in `assets/animals/`
- Put keyword packs in `assets/keywords/`
- GIFs work directly
- Sprite sheets need a JSON manifest beside the image

## Troubleshooting

**Launch fails inside MediaPipe import**

- Re-run setup so the pinned `matplotlib>=3.8,<3.10` dependency is installed

**`aubio` fails to install**

- The app will fall back to the built-in numpy pitch detector automatically

**MIDI option is enabled but no synth responds**

- Install `python-rtmidi`
- Make sure a hardware or virtual MIDI output port exists before launch

**Speech works poorly or not at all**

- Confirm the Vosk model exists in `models\vosk\vosk-model-small-en-us-0.15`
- Check Windows microphone privacy settings
