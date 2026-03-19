# Hand Galaxy v2.1.3 — Installation Guide

---

## Option 1 — HandGalaxySetup.exe  (Recommended, Windows only)

This is the cleanest path. One file, full guided wizard.

1. Run **`HandGalaxySetup.exe`**
2. Follow the 7-page wizard:
   - Choose install folder (default: `~/Hand Galaxy`)
   - Select components (speech, pitch, shortcuts)
   - The wizard automatically checks for Python 3.10+ and offers to install it if missing
   - Downloads the MediaPipe hand model (~9 MB)
   - Downloads the Vosk speech model (~40 MB) if speech is selected
   - Creates Desktop and Start Menu shortcuts
   - Registers an uninstaller in Windows Add/Remove Programs
3. Click Finish — optionally launches Hand Galaxy immediately

**Building HandGalaxySetup.exe from source:**

If you received the source zip rather than a pre-built exe:

```powershell
# 1. Run setup.bat first to create the venv
setup.bat

# 2. Build the installer exe
.\installer\build_setup_exe.ps1
```

Output: `dist\HandGalaxySetup.exe` — a single portable file to distribute.

---

## Option 2 — setup.bat  (Windows, no PyInstaller needed)

Double-click `setup.bat` from the project folder. Same 7-step process as above but runs in a command window rather than a GUI. Creates all launcher `.bat` files and shortcuts automatically, including `Launch-Auto.bat` for dependency-safe first runs. Does not require PyInstaller.

---

## Option 3 — PowerShell launcher

```powershell
.\scripts\start-hand-galaxy.ps1
```

Handles venv creation, pip install, model download, and launch in one command.

Options:

```powershell
.\scripts\start-hand-galaxy.ps1 -NoSpeech
.\scripts\start-hand-galaxy.ps1 -NoPitch
.\scripts\start-hand-galaxy.ps1 -NoAtmosphere
.\scripts\start-hand-galaxy.ps1 -VirtualCam
.\scripts\start-hand-galaxy.ps1 -HighlightStyle rim
```

---

## Option 4 — Manual install

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install "vosk>=0.3.45" "pyaudio>=0.2.14"   # optional, enables speech + mic features
.venv\Scripts\pip install aubio   # optional, improves pitch tracking
$env:PYTHONPATH = "$PWD\src"
python -m hand_galaxy.main
```

---

## System Requirements

| Requirement | Minimum |
|---|---|
| OS | Windows 10 64-bit or Windows 11 |
| Python | 3.10 or newer (setup wizard can install automatically) |
| RAM | 4 GB (8 GB recommended) |
| Webcam | Any USB or built-in camera |
| Microphone | Any (for speech and pitch features) |
| Disk | 500 MB free (1 GB recommended) |
| Internet | Required during installation for model downloads |

macOS and Linux are supported via Option 3 or 4 (no .exe installer).

---

## What Gets Installed

```
~/Hand Galaxy/              (or your chosen folder)
  .venv/                    Python virtual environment
  src/hand_galaxy/          Python source modules
  models/
    hand_landmarker.task    MediaPipe hand model (~9 MB)
    vosk/
      vosk-model-small-en-us-0.15/   Speech model (~40 MB)
  assets/
    animals/                Drop your PNG/JPG images here
  touchdesigner/
    NETWORK_SETUP.md
    OSC_CHANNELS.md
  Launch-Auto.bat       Recommended safe start
  Launch.bat                Quick start
  Launch-NoSpeech.bat
  Launch-VirtualCam.bat
  Launcher.bat              GUI launcher
  Uninstall.bat             Remove Hand Galaxy
  install_receipt.json      Install record
```

---

## Uninstalling

- **Windows Add/Remove Programs** — search for "Hand Galaxy" and uninstall
- **Uninstall.bat** — double-click in the install folder
- **Manual** — delete the install folder and Desktop/Start Menu shortcuts

---

## After Installing — First Steps

1. Add animal images to `assets\animals\`

   ```
   cat.png   dog.jpg   butterfly.png   bee.png   dragonfly.png
   ```

   Any PNG or JPG works. Transparent PNG looks best with the glow effects.
   If no image exists for a spoken word, a labelled placeholder is shown automatically.

2. Launch Hand Galaxy via `Launcher.bat` (GUI) or `Launch-Auto.bat` (recommended direct launcher)

3. Speak animal names to trigger images. Speak letters (A–Z or NATO: "alpha bravo charlie")
   to see them appear on screen. Use your voice pitch to shift atmosphere zones.

4. For TouchDesigner: open `touchdesigner\NETWORK_SETUP.md` for the full
   node wiring guide and OSC channel map.

---

## Troubleshooting

**Python not found during setup:**
Install Python 3.10-3.12 from https://python.org and tick "Add Python to PATH". Python 3.14 is currently too new for this build because MediaPipe wheels are only listed up to Python 3.12 on PyPI.
Then re-run setup.bat or HandGalaxySetup.exe.

**Microphone not working:**
Run `Launch-NoSpeech.bat` to confirm hand tracking works without the mic.
Then check Windows microphone privacy settings (Settings → Privacy → Microphone).

**Webcam not detected:**
Check camera index: `python -m hand_galaxy.main --camera-index 1`

**Vosk model download fails:**
Download manually from https://alphacephei.com/vosk/models
File: `vosk-model-small-en-us-0.15.zip`
Extract to: `models\vosk\vosk-model-small-en-us-0.15\`

**aubio install fails:**
```powershell
.venv\Scripts\pip install aubio --pre
```
If that still fails, Hand Galaxy will use the built-in numpy pitch fallback automatically. Install `aubio` later if you want the preferred backend.

**TouchDesigner cannot see virtual camera:**
Install OBS Virtual Camera or UnityCapture, then use `Launch-VirtualCam.bat`.
