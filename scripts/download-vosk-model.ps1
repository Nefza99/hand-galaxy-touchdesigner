# download-vosk-model.ps1
# Downloads the Vosk small English model (~40 MB) to models/vosk/
# Run from the project root in PowerShell.

param(
    [string]$ModelUrl = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    [string]$ModelDir = "models\vosk"
)

$ErrorActionPreference = "Stop"
$zipPath   = Join-Path $ModelDir "vosk-model-small-en-us-0.15.zip"
$finalDir  = Join-Path $ModelDir "vosk-model-small-en-us-0.15"

if (Test-Path $finalDir) {
    Write-Host "Vosk model already present at '$finalDir'. Nothing to do."
    exit 0
}

New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

Write-Host "Downloading Vosk small English model (~40 MB)..."
Write-Host "URL: $ModelUrl"
Invoke-WebRequest -Uri $ModelUrl -OutFile $zipPath -UseBasicParsing

Write-Host "Extracting..."
Expand-Archive -Path $zipPath -DestinationPath $ModelDir -Force
Remove-Item $zipPath

if (Test-Path $finalDir) {
    Write-Host "Vosk model ready at '$finalDir'."
} else {
    Write-Error "Extraction failed - expected folder '$finalDir' not found."
    exit 1
}
