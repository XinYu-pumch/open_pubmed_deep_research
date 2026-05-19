param(
    [switch]$SkipDependencyCheck
)

$ErrorActionPreference = "Stop"

$WinDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $WinDir
$DistDir = Join-Path $RootDir "dist"
$BuildDir = Join-Path $RootDir "build\build_windows"
$PyinstallerCache = Join-Path $RootDir "build\pyinstaller-cache-windows"
$SpecPath = Join-Path $WinDir "build_windows.spec"
$AppDir = Join-Path $DistDir "OpenPubmedDeepResearch"
$ExePath = Join-Path $AppDir "OpenPubmedDeepResearch.exe"

function Write-Step($Message) {
    Write-Host $Message -ForegroundColor Green
}

function Require-File($Path) {
    if (-not (Test-Path $Path)) {
        throw "Missing required file: $Path"
    }
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Building Open Pubmed Deep Research V1.0 for Windows" -ForegroundColor Cyan
Write-Host "  Output: one-folder distribution with OpenPubmedDeepResearch.exe" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

if ($env:OS -ne "Windows_NT") {
    throw "This build script must be run on Windows."
}

Set-Location $RootDir

$Python = Join-Path $RootDir "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = Join-Path $RootDir ".venv\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Require-File $SpecPath
Require-File (Join-Path $RootDir "app.py")
Require-File (Join-Path $RootDir "core_logic.py")
Require-File (Join-Path $RootDir "config_manager.py")
Require-File (Join-Path $WinDir "app_windows.py")
Require-File (Join-Path $WinDir "workspace_manager.py")
Require-File (Join-Path $WinDir "desktop_windows.py")
Require-File (Join-Path $WinDir "streamlit_server_windows.py")
Require-File (Join-Path $WinDir "convert_same_directory_windows.py")

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:TOKENIZERS_PARALLELISM = "false"
$env:CUDA_VISIBLE_DEVICES = ""

if (-not $SkipDependencyCheck) {
    Write-Step "[1/5] Verifying Python dependencies..."
    $DependencyCheck = @'
import importlib
import sys

required = [
    "PyInstaller",
    "webview",
    "streamlit",
    "chromadb",
    "httpx",
    "requests",
    "bs4",
    "lxml",
    "markdown",
    "docx",
    "pandas",
    "numpy",
    "torch",
    "transformers",
    "surya",
    "pdftext",
    "pypdfium2",
]

missing = []
for module in required:
    try:
        importlib.import_module(module)
    except Exception as exc:
        missing.append(f"{module}: {exc}")

if missing:
    print("Missing build/runtime modules:")
    print("\n".join(missing))
    sys.exit(1)
'@
    $DependencyCheck | & $Python -
}

Write-Step "[2/5] Verifying Windows shim imports..."
$ShimCheck = @"
import os
import sys
root = r"$RootDir"
win = os.path.join(root, "win")
sys.path.insert(0, win)
sys.path.insert(1, root)
import bootstrap_windows
bootstrap_windows.setup_windows_runtime(patch_core=True)
import workspace_manager
import core_logic
assert workspace_manager.get_config_file_path().lower().endswith("pubmedresearch\\config.json")
assert hasattr(core_logic, "run_marker_conversion")
print("Windows shim preflight ok")
"@
$ShimCheck | & $Python -

Write-Step "[3/5] Cleaning previous Windows build artifacts..."
Remove-Item -Recurse -Force $BuildDir, $AppDir, $PyinstallerCache -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $PyinstallerCache | Out-Null

Write-Step "[4/5] Running PyInstaller..."
$env:PYINSTALLER_CONFIG_DIR = $PyinstallerCache
& $Python -m PyInstaller --clean --noconfirm $SpecPath

if (-not (Test-Path $ExePath)) {
    throw "Build failed: executable not found at $ExePath"
}

$ResourceDir = $AppDir
$InternalDir = Join-Path $AppDir "_internal"
if (Test-Path $InternalDir) {
    $ResourceDir = $InternalDir
}

Write-Step "[5/5] Verifying distribution..."
foreach ($name in @("OpenPubmedDeepResearch.exe", "streamlit-server.exe", "same-directory-converter.exe", "marker-converter.exe")) {
    $candidate = Join-Path $AppDir $name
    if (-not (Test-Path $candidate)) {
        throw "Missing bundled executable: $candidate"
    }
}

foreach ($name in @("app.py", "core_logic.py", "config_manager.py", "win", "marker_modified", "marker_config")) {
    $candidate = Join-Path $ResourceDir $name
    if (-not (Test-Path $candidate)) {
        throw "Missing bundled resource: $candidate"
    }
}

Remove-Item -Recurse -Force $BuildDir, $PyinstallerCache -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Build Complete" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Executable: $ExePath"
Write-Host "Distribution folder: $AppDir"
Write-Host "Resource folder: $ResourceDir"
