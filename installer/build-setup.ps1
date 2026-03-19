param(
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$installerRoot = $PSScriptRoot
$payloadRoot = Join-Path $installerRoot "payload"
$stageRoot = Join-Path $payloadRoot "app_stage"
$payloadZip = Join-Path $payloadRoot "hand-galaxy-payload.zip"
$dotnetRoot = Join-Path $installerRoot ".dotnet"
$dotnetInstall = Join-Path $installerRoot "dotnet-install.ps1"
$project = Join-Path $installerRoot "SetupBootstrapper\\SetupBootstrapper.csproj"
$publishDir = Join-Path $installerRoot "dist"

Write-Host "Preparing installer payload..."
Remove-Item $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $payloadZip -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $stageRoot, $payloadRoot, $publishDir | Out-Null

Copy-Item (Join-Path $root "README.md") (Join-Path $stageRoot "README.md")
Copy-Item (Join-Path $root "requirements.txt") (Join-Path $stageRoot "requirements.txt")
Copy-Item (Join-Path $root "requirements-virtualcam.txt") (Join-Path $stageRoot "requirements-virtualcam.txt")
Copy-Item (Join-Path $root "src") (Join-Path $stageRoot "src") -Recurse
Copy-Item (Join-Path $root "touchdesigner") (Join-Path $stageRoot "touchdesigner") -Recurse

Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $payloadZip -CompressionLevel Optimal

if (-not (Test-Path $dotnetInstall)) {
    Write-Host "Downloading dotnet-install.ps1..."
    Invoke-WebRequest -Uri "https://dot.net/v1/dotnet-install.ps1" -OutFile $dotnetInstall -UseBasicParsing
}

if (-not (Test-Path (Join-Path $dotnetRoot "dotnet.exe"))) {
    Write-Host "Installing local .NET SDK..."
    & powershell -ExecutionPolicy Bypass -File $dotnetInstall -Channel 8.0 -InstallDir $dotnetRoot
}

$dotnet = Join-Path $dotnetRoot "dotnet.exe"
Write-Host "Publishing SETUP.exe..."
& $dotnet publish $project `
    -c $Configuration `
    -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:PublishTrimmed=false `
    -o $publishDir

Write-Host ""
Write-Host "Build complete:"
Write-Host (Join-Path $publishDir "SETUP.exe")

