@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

title Hand Galaxy v2.2.0 Setup

cls
echo.
echo  ==============================================================
echo           HAND GALAXY v2.2.0 - SETUP WIZARD
echo    Hand Tracking + Speech + Pitch + Media + MIDI
echo  ==============================================================
echo.

cd /d "%~dp0"

set "PY_CMD="
set "PY_VER="
set "PY_MAJOR="
set "PY_MINOR="

echo  [1/7] Checking Python...

for %%V in (3.12 3.11 3.10) do (
    py -%%V --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=py -%%V"
        goto :python_found
    )
)

python --version >nul 2>&1
if errorlevel 1 goto :python_missing

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)
if !PY_MAJOR! EQU 3 if !PY_MINOR! GEQ 10 if !PY_MINOR! LEQ 12 (
    set "PY_CMD=python"
    goto :python_found
)
if !PY_MAJOR! EQU 3 if !PY_MINOR! GTR 12 goto :python_too_new

goto :python_missing

:python_found
for /f "tokens=2 delims= " %%v in ('%PY_CMD% --version 2^>^&1') do set "PY_VER=%%v"
echo  [OK] Using Python !PY_VER! via %PY_CMD%
goto :python_ready

:python_too_new
echo.
echo  [ERROR] Python !PY_VER! is installed, but this build depends on MediaPipe,
echo          which currently supports Python 3.10-3.12 on PyPI for Windows.
echo.
echo  Please install Python 3.12, then re-run this setup.
echo  If both are installed, this wizard will prefer 3.12 automatically.
echo.
pause
exit /b 1

:python_missing
echo.
echo  [ERROR] Compatible Python not found in PATH.
echo  Please install Python 3.10, 3.11, or 3.12 from python.org
echo  and tick "Add Python to PATH" during install.
echo.
pause
exit /b 1

:python_ready
echo.
echo  [2/7] Creating virtual environment (.venv)...
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set "SEL_MAJOR=%%a"
    set "SEL_MINOR=%%b"
)
set "REBUILD_VENV=0"
if exist ".venv\Scripts\python.exe" (
    for /f "tokens=2 delims= " %%v in ('.venv\Scripts\python.exe --version 2^>^&1') do set "VENV_VER=%%v"
    for /f "tokens=1,2 delims=." %%a in ("!VENV_VER!") do (
        set "VENV_MAJOR=%%a"
        set "VENV_MINOR=%%b"
    )
    if not "!VENV_MAJOR!.!VENV_MINOR!"=="!SEL_MAJOR!.!SEL_MINOR!" (
        echo  [INFO] Existing .venv uses Python !VENV_VER!; rebuilding for !PY_VER! ...
        rmdir /s /q .venv
        set "REBUILD_VENV=1"
    )
)
if not exist ".venv" set "REBUILD_VENV=1"
if "!REBUILD_VENV!"=="1" (
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  [OK] Created .venv
) else (
    echo  [OK] .venv already matches Python !PY_VER! - keeping it.
)

set "PYTHON=.venv\Scripts\python.exe"
if not exist %PYTHON% (
    echo  [ERROR] .venv Python was not created correctly.
    pause
    exit /b 1
)

echo.
echo  [3/7] Installing Python dependencies (may take 1-2 minutes)...
%PYTHON% -m pip install --upgrade pip --quiet
if errorlevel 1 goto pip_error

%PYTHON% -m pip install "mediapipe>=0.10.9" "opencv-python>=4.9.0" "python-osc>=1.8.3" "numpy>=1.26.0" "pillow>=10.3.0" "mido>=1.3.2" --quiet
if errorlevel 1 (
    echo.
    echo  [WARNING] Core packages failed to install quietly.
    echo  Retrying with verbose output...
    %PYTHON% -m pip install "mediapipe>=0.10.9" "opencv-python>=4.9.0" "python-osc>=1.8.3" "numpy>=1.26.0" "pillow>=10.3.0" "mido>=1.3.2"
    if errorlevel 1 goto pip_error
)
echo  [OK] Core dependencies installed.

echo  Repairing MediaPipe matplotlib dependency...
for /d %%D in (".venv\Lib\site-packages\matplotlib-3.10*.dist-info") do (
    echo  [INFO] Removing stale matplotlib metadata: %%~nxD
    rmdir /s /q "%%~fD"
)
%PYTHON% -m pip install "matplotlib>=3.8,<3.10" --ignore-installed --quiet
if errorlevel 1 (
    echo  [WARNING] Quiet matplotlib recovery failed. Retrying with verbose output...
    %PYTHON% -m pip install "matplotlib>=3.8,<3.10" --ignore-installed
    if errorlevel 1 goto pip_error
)
echo  [OK] Matplotlib pin installed.

echo  Installing Vosk (speech recognition)...
%PYTHON% -m pip install "vosk>=0.3.45" --quiet
if errorlevel 1 (
    echo  [WARNING] vosk could not be installed.
    echo  Speech recognition will be disabled.
) else (
    echo  [OK] vosk installed.
)

echo  Installing PyAudio (shared microphone input)...
%PYTHON% -m pip install pipwin --quiet >nul 2>&1
%PYTHON% -m pip install "pyaudio>=0.2.14" --quiet
if errorlevel 1 (
    echo  [INFO] Direct PyAudio install failed. Trying Windows wheel helper...
    %PYTHON% -m pipwin install pyaudio
)
if errorlevel 1 (
    echo  [WARNING] PyAudio could not be installed.
    echo  Speech and pitch microphone features will be disabled.
    echo  Camera / gesture tracking will still work.
) else (
    echo  [OK] PyAudio installed.
)

echo  Installing aubio (pitch detection)...
%PYTHON% -m pip install aubio --quiet >nul 2>&1
if errorlevel 1 (
    echo  [WARNING] aubio could not be installed.
    echo  Hand Galaxy will use the built-in numpy pitch fallback instead.
    echo  You can install aubio later for higher-precision tracking with:
    echo    .venv\Scripts\python.exe -m pip install aubio
) else (
    echo  [OK] aubio installed.
)

echo  Installing optional MIDI backend...
%PYTHON% -m pip install "python-rtmidi>=1.5.8" --quiet
if errorlevel 1 (
    echo  [INFO] python-rtmidi could not be installed.
    echo  MIDI output will stay disabled until a backend is installed later.
) else (
    echo  [OK] python-rtmidi installed.
)

echo  Installing optional virtual camera support...
if exist "requirements-virtualcam.txt" (
    %PYTHON% -m pip install -r requirements-virtualcam.txt --quiet
    if errorlevel 1 (
        echo  [INFO] Optional virtual camera package could not be installed.
        echo  Launch-VirtualCam.bat may not work until it is installed later.
    ) else (
        echo  [OK] Optional virtual camera package installed.
    )
)
goto after_pip

:pip_error
echo.
echo  [ERROR] Python package installation failed.
echo  This is usually one of these:
echo    - unsupported Python version
echo    - a temporary network issue
echo    - a package wheel missing for your machine
echo.
echo  The safest Python for this build is 3.12.
pause
exit /b 1

:after_pip
echo.
echo  [4/7] Downloading MediaPipe hand landmark model (~9 MB)...
if exist "models\hand_landmarker.task" (
    echo  [OK] Model already downloaded.
) else (
    mkdir models 2>nul
    powershell -ExecutionPolicy Bypass -Command ^
        "Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task' -OutFile 'models\hand_landmarker.task' -UseBasicParsing"
    if errorlevel 1 (
        echo  [ERROR] Failed to download hand model. Check internet connection.
        echo  You can retry later by running setup.bat again.
    ) else (
        echo  [OK] Hand model downloaded.
    )
)

echo.
echo  [5/7] Downloading Vosk speech model (~40 MB)...
set "VOSK_DIR=models\vosk\vosk-model-small-en-us-0.15"
if exist "%VOSK_DIR%" (
    echo  [OK] Vosk model already present.
) else (
    mkdir models\vosk 2>nul
    echo  Downloading vosk-model-small-en-us-0.15.zip ...
    powershell -ExecutionPolicy Bypass -Command ^
        "Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip' -OutFile 'models\vosk\model.zip' -UseBasicParsing"
    if errorlevel 1 (
        echo  [WARNING] Vosk model download failed. Speech recognition will be disabled.
        echo  Retry later by re-running setup.bat.
        goto after_vosk
    )
    echo  Extracting...
    powershell -ExecutionPolicy Bypass -Command ^
        "Expand-Archive -Path 'models\vosk\model.zip' -DestinationPath 'models\vosk\' -Force"
    del /q models\vosk\model.zip 2>nul
    if exist "%VOSK_DIR%" (
        echo  [OK] Vosk model ready.
    ) else (
        echo  [WARNING] Extraction may have failed. Check models\vosk\ manually.
    )
)
:after_vosk

echo.
echo  [6/7] Creating launcher files...
(
echo @echo off
echo cd /d "%%~dp0"
echo title Hand Galaxy v2.2.0
echo set PYTHONPATH=%%~dp0src
echo ".venv\Scripts\python.exe" -m hand_galaxy.main %%*
echo if errorlevel 1 pause
) > "Launch.bat"
echo  [OK] Launch.bat created.

(
echo @echo off
echo cd /d "%%~dp0"
echo title Hand Galaxy v2.2.0 ^(Hands Only^)
echo set PYTHONPATH=%%~dp0src
echo ".venv\Scripts\python.exe" -m hand_galaxy.main --no-speech --no-pitch %%*
echo if errorlevel 1 pause
) > "Launch-NoSpeech.bat"
echo  [OK] Launch-NoSpeech.bat created.

(
echo @echo off
echo cd /d "%%~dp0"
echo title Hand Galaxy v2.2.0 ^(No Pitch^)
echo set PYTHONPATH=%%~dp0src
echo ".venv\Scripts\python.exe" -m hand_galaxy.main --no-pitch %%*
echo if errorlevel 1 pause
) > "Launch-NoPitch.bat"
echo  [OK] Launch-NoPitch.bat created.

(
echo @echo off
echo cd /d "%%~dp0"
echo title Hand Galaxy v2.2.0 ^(Minimal^)
echo set PYTHONPATH=%%~dp0src
echo ".venv\Scripts\python.exe" -m hand_galaxy.main --no-speech --no-pitch --no-atmosphere %%*
echo if errorlevel 1 pause
) > "Launch-Minimal.bat"
echo  [OK] Launch-Minimal.bat created.

(
echo @echo off
echo cd /d "%%~dp0"
echo title Hand Galaxy v2.2.0 - Auto Safe
echo set PYTHONPATH=%%~dp0src
echo ".venv\Scripts\python.exe" installer\launch_helper.py %%*
echo if errorlevel 1 pause
) > "Launch-Auto.bat"
echo  [OK] Launch-Auto.bat created.

(
echo @echo off
echo cd /d "%%~dp0"
echo title Hand Galaxy v2.2.0 ^(Virtual Cam^)
echo set PYTHONPATH=%%~dp0src
echo ".venv\Scripts\python.exe" -m hand_galaxy.main --virtual-cam %%*
echo if errorlevel 1 pause
) > "Launch-VirtualCam.bat"
echo  [OK] Launch-VirtualCam.bat created.

(
echo @echo off
echo cd /d "%%~dp0"
echo title Hand Galaxy Launcher
echo set PYTHONPATH=%%~dp0src
echo ".venv\Scripts\python.exe" installer\launcher_gui.py
) > "Launcher.bat"
echo  [OK] Launcher.bat created.

echo.
echo  [7/7] Creating Desktop shortcut...
powershell -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Hand Galaxy.lnk'); " ^
    "$sc.TargetPath = '%~dp0Launcher.bat'; " ^
    "$sc.WorkingDirectory = '%~dp0'; " ^
    "$sc.Description = 'Hand Galaxy v2.2.0'; " ^
    "$sc.Save()" 2>nul
if errorlevel 1 (
    echo  [INFO] Desktop shortcut skipped.
) else (
    echo  [OK] Desktop shortcut created: Hand Galaxy
)

echo.
echo  ==============================================================
echo                         SETUP COMPLETE
echo  ==============================================================
echo.
echo  How to run:
echo    Launcher.bat          - GUI launcher
echo    Launch-Auto.bat       - Recommended safe launcher
echo    Launch.bat            - Full features
echo    Launch-NoSpeech.bat   - Hands only, no mic
echo    Launch-NoPitch.bat    - Speech on, pitch off
echo    Launch-Minimal.bat    - No mic, minimal visuals
echo    Launch-VirtualCam.bat - Virtual camera mode
echo.
echo  Optional:
echo    Launch-Auto.bat --midi         - enable MIDI output
echo    Add custom keyword JSON files to: assets\keywords\
echo    Add GIFs or sprite manifests to the matching asset folders
echo.
echo  Add animal images to: assets\animals\
echo  TouchDesigner setup: see touchdesigner\NETWORK_SETUP.md
echo.
pause
