# build_exe.ps1
# Compiles the GUI launcher into a standalone HandGalaxy.exe using PyInstaller.
# Run from the project root after setup.bat has been completed.
#
# Output:  dist\HandGalaxy.exe   (portable, no Python needed on target machine)
#
# Requirements:  PyInstaller is installed into .venv automatically by this script.

param(
    [switch]$OneFile,     # --onefile (larger, no folder) vs --onedir (default, faster start)
    [switch]$NoConsole    # hide the console window entirely
)

$ErrorActionPreference = "Stop"
$root   = Split-Path -Parent $PSScriptRoot
$python = "$root\.venv\Scripts\python.exe"
$pip    = "$root\.venv\Scripts\pip.exe"

if (-not (Test-Path $python)) {
    Write-Error "venv not found. Run setup.bat first."
    exit 1
}

Write-Host "Installing PyInstaller into venv..."
& $pip install pyinstaller --quiet

Write-Host "Building exe..."

$spec = @"
# -*- mode: python -*-
block_cipher = None

a = Analysis(
    ['$($root.Replace('\','\\'))\\installer\\launcher_gui.py'],
    pathex=['$($root.Replace('\','\\'))\\src'],
    binaries=[],
    datas=[
        ('$($root.Replace('\','\\'))\\assets', 'assets'),
        ('$($root.Replace('\','\\'))\\touchdesigner', 'touchdesigner'),
    ],
    hiddenimports=['hand_galaxy'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='HandGalaxy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=$(if ($NoConsole) { 'False' } else { 'True' }),
    icon=None,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas, strip=False,
    upx=True, upx_exclude=[], name='HandGalaxy',
)
"@

$specPath = "$root\HandGalaxy.spec"
$spec | Out-File -FilePath $specPath -Encoding UTF8

$pyinstallerArgs = @(
    "-m", "PyInstaller",
    "--distpath", "$root\dist",
    "--workpath", "$root\build_pyinstaller",
    "--noconfirm",
    $specPath
)
if ($OneFile) { $pyinstallerArgs += "--onefile" }

& $python @pyinstallerArgs

if (Test-Path "$root\dist\HandGalaxy\HandGalaxy.exe") {
    Write-Host ""
    Write-Host "========================================="
    Write-Host "  BUILD COMPLETE"
    Write-Host "  Executable: dist\HandGalaxy\HandGalaxy.exe"
    Write-Host "  Distribute the entire dist\HandGalaxy\ folder."
    Write-Host "========================================="
} else {
    Write-Error "Build failed - HandGalaxy.exe not found in dist\."
}

# Clean spec file
Remove-Item $specPath -ErrorAction SilentlyContinue
