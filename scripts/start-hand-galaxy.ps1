param(
    [string]$PythonCmd = "",
    [string]$OscHost = "127.0.0.1",
    [int]$OscPort = 7000,
    [switch]$NoPreview,
    [switch]$SendLandmarks,
    [switch]$VirtualCam
)

function Resolve-Python {
    param([string]$Preferred)

    $candidates = @()
    if ($Preferred) { $candidates += $Preferred }
    $candidates += @("py", "python", "python3")

    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {
            return $cmd.Source
        }
    }

    return $null
}

$root = Split-Path -Parent $PSScriptRoot
$python = Resolve-Python -Preferred $PythonCmd

if (-not $python) {
    throw "No local Python installation was found. Install Python 3.10+ and re-run this script."
}

$venvPath = Join-Path $root ".venv"
$venvPython = Join-Path $venvPath "Scripts\\python.exe"

if (-not (Test-Path $venvPython)) {
    & $python -m venv $venvPath
}

$requirements = if ($VirtualCam) {
    Join-Path $root "requirements-virtualcam.txt"
} else {
    Join-Path $root "requirements.txt"
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r $requirements
& (Join-Path $PSScriptRoot "download-hand-model.ps1")

$env:PYTHONPATH = Join-Path $root "src"
$runArgs = @(
    "-m", "hand_galaxy.main",
    "--osc-host", $OscHost,
    "--osc-port", $OscPort
)

if ($NoPreview) { $runArgs += "--no-preview" }
if ($SendLandmarks) { $runArgs += "--send-landmarks" }
if ($VirtualCam) { $runArgs += "--virtual-cam" }

& $venvPython @runArgs

