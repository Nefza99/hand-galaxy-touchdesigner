param(
    [string]$ModelUrl = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    [string]$OutputPath = ""
)

$root = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $root "models\\hand_landmarker.task"
}

$outDir = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force $outDir | Out-Null

if (Test-Path $OutputPath) {
    Write-Host "Model already exists at $OutputPath"
    exit 0
}

$ProgressPreference = "SilentlyContinue"
Write-Host "Downloading MediaPipe hand model..."
Invoke-WebRequest -Uri $ModelUrl -OutFile $OutputPath -UseBasicParsing
Write-Host "Saved model to $OutputPath"

