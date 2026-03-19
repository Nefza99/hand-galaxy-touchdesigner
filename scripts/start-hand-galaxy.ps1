# start-hand-galaxy.ps1  v2.2.0
param(
    [switch]$VirtualCam,
    [switch]$NoPreview,
    [switch]$NoSpeech,
    [switch]$NoPitch,
    [switch]$NoAtmosphere,
    [switch]$Midi,
    [switch]$SkipModelDownload,
    [string]$HighlightStyle = "glow",
    [string]$MidiPort       = "",
    [float]$PitchWeight     = 0.6,
    [double]$MaxSeconds     = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

function Invoke-NativeQuiet {
    param([scriptblock]$Command)
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command 2>$null | Out-Null
    } catch {}
    finally {
        $ErrorActionPreference = $previousPreference
    }
    return $LASTEXITCODE
}

function Get-CompatiblePython {
    foreach ($ver in @('3.12','3.11','3.10')) {
        try {
            & py -$ver --version *> $null
            if ($LASTEXITCODE -eq 0) { return @('py', "-$ver") }
        } catch {}
    }
    try {
        $out = (& python --version) 2>&1
        if ($out -match 'Python\s+3\.(10|11|12)\.') { return @('python') }
        if ($out -match 'Python\s+3\.(1[3-9]|[2-9][0-9])\.') {
            throw "Python version too new for current MediaPipe wheels: $out"
        }
    } catch {}
    throw 'No compatible Python 3.10-3.12 installation was found.'
}

$pycmd = Get-CompatiblePython

$selectedVersion = if ($pycmd[0] -eq 'py') { (& py $pycmd[1] --version) } else { (& python --version) }
$rebuildVenv = $false
if (Test-Path '.venv\Scripts\python.exe') {
    $venvVersion = (& .venv\Scripts\python.exe --version) 2>&1
    if ($venvVersion -ne $selectedVersion) {
        Write-Host "Existing .venv uses $venvVersion; rebuilding for $selectedVersion ..."
        Remove-Item '.venv' -Recurse -Force
        $rebuildVenv = $true
    }
} else {
    $rebuildVenv = $true
}
if ($rebuildVenv) {
    Write-Host 'Creating virtual environment...'
    if ($pycmd.Length -gt 1) {
        & $pycmd[0] $pycmd[1] -m venv .venv
    } else {
        & $pycmd[0] -m venv .venv
    }
}

$python = '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw '.venv Python was not created correctly.' }

Write-Host 'Installing / updating dependencies...'
& $python -m pip install --upgrade pip --quiet
& $python -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { throw 'Core dependency installation failed.' }
Get-ChildItem '.venv\Lib\site-packages\matplotlib-3.10*.dist-info' -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
& $python -m pip install "matplotlib>=3.8,<3.10" --ignore-installed --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Pinned matplotlib repair failed on the quiet pass. Retrying...'
    & $python -m pip install "matplotlib>=3.8,<3.10" --ignore-installed
    if ($LASTEXITCODE -ne 0) { throw 'Matplotlib compatibility install failed.' }
}

Write-Host 'Installing / updating speech dependencies...'
$status = Invoke-NativeQuiet { & $python -m pip install "vosk>=0.3.45" --quiet }
if ($status -ne 0) {
    Write-Warning 'Vosk could not be installed. Speech will be auto-disabled if needed.'
}

Write-Host 'Installing / updating microphone bridge...'
$null = Invoke-NativeQuiet { & $python -m pip install pipwin --quiet }
$status = Invoke-NativeQuiet { & $python -m pip install "pyaudio>=0.2.14" --quiet }
if ($status -ne 0) {
    Write-Host 'Direct PyAudio install failed. Trying pipwin wheel helper...'
    $status = Invoke-NativeQuiet { & $python -m pipwin install pyaudio }
}
if ($status -ne 0) {
    Write-Warning 'PyAudio could not be installed. Speech and pitch will be auto-disabled if needed.'
}

Write-Host 'Installing optional high-precision pitch backend...'
$status = Invoke-NativeQuiet { & $python -m pip install aubio --quiet }
if ($status -ne 0) {
    Write-Warning 'aubio could not be installed. The built-in numpy pitch fallback will be used.'
}

Write-Host 'Installing media helpers...'
$status = Invoke-NativeQuiet { & $python -m pip install "pillow>=10.3.0" "mido>=1.3.2" --quiet }
if ($status -ne 0) {
    Write-Warning 'Pillow and/or mido could not be installed automatically.'
}

if ($Midi) {
    Write-Host 'Installing optional MIDI backend...'
    $status = Invoke-NativeQuiet { & $python -m pip install "python-rtmidi>=1.5.8" --quiet }
    if ($status -ne 0) {
        Write-Warning 'python-rtmidi could not be installed. MIDI mode may be unavailable.'
    }
}

if ($VirtualCam -and (Test-Path 'requirements-virtualcam.txt')) {
    $status = Invoke-NativeQuiet { & $python -m pip install -r requirements-virtualcam.txt --quiet }
    if ($status -ne 0) {
        Write-Warning 'Virtual camera package could not be installed. Virtual cam mode may be unavailable.'
    }
}

if (-not $SkipModelDownload) {
    & powershell -ExecutionPolicy Bypass -File 'scripts\download-hand-model.ps1'
}
if (-not $NoSpeech -and -not $SkipModelDownload) {
    & powershell -ExecutionPolicy Bypass -File 'scripts\download-vosk-model.ps1'
}

$env:PYTHONPATH = "$root\src"
$argsList = @()
if ($VirtualCam)   { $argsList += '--virtual-cam' }
if ($NoPreview)    { $argsList += '--no-preview' }
if ($NoSpeech)     { $argsList += '--no-speech' }
if ($NoPitch)      { $argsList += '--no-pitch' }
if ($NoAtmosphere) { $argsList += '--no-atmosphere' }
if ($Midi)         { $argsList += '--midi' }
if ($MidiPort) {
    $argsList += '--midi-port'
    $argsList += $MidiPort
}
if ($MaxSeconds -gt 0) {
    $argsList += '--max-seconds'
    $argsList += "$MaxSeconds"
}
$argsList += '--highlight-style'; $argsList += $HighlightStyle
$argsList += '--pitch-weight';    $argsList += "$PitchWeight"

Write-Host ''
Write-Host '================================================'
Write-Host '  Hand Galaxy v2.2.0 - starting'
Write-Host "  Speech:    $(if ($NoSpeech) { 'off' } else { 'on' })"
Write-Host "  Pitch:     $(if ($NoPitch)  { 'off' } else { "on  (weight $PitchWeight)" })"
Write-Host "  Atmosphere:$(if ($NoAtmosphere) { 'off' } else { 'on' })"
Write-Host "  MIDI:      $(if ($Midi) { $(if ($MidiPort) { "on  ($MidiPort)" } else { 'on' }) } else { 'off' })"
Write-Host "  Highlight: $HighlightStyle"
Write-Host '================================================'
Write-Host ''

& $python installer\launch_helper.py @argsList
Pop-Location
