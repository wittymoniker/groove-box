# =============================================================================
# Groovebox dependency installer - Windows
# -----------------------------------------------------------------------------
# Installs every host-app / exported-game dependency and the ffmpeg codec suite
# into a local bin folder on your user PATH (Windows has no /bin; this is the
# Windows equivalent the codec resolver also searches by PATH).
#
#   Powershell -ExecutionPolicy Bypass -File install_deps_windows.ps1
# =============================================================================
param(
    [switch]$SkipWinget,
    [switch]$SkipChoco
)
$ErrorActionPreference = "Continue"

Write-Host "==> Groovebox installer: Windows"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BIN = Join-Path $ROOT "bin"
New-Item -ItemType Directory -Force -Path $BIN | Out-Null

function Add-ToUserPath([string]$dir) {
    $cur = [Environment]::GetEnvironmentVariable("Path", "User")
    if (($cur -split ";" ) -notcontains $dir) {
        $new = if ([string]::IsNullOrEmpty($cur)) { $dir } else { "$cur;$dir" }
        [Environment]::SetEnvironmentVariable("Path", $new, "User")
        Write-Host "  added to user PATH: $dir"
    }
}
Add-ToUserPath $BIN

# --- Python -------------------------------------------------------------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing Python 3.12 via winget..."
    if (-not $SkipWinget) {
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    } else {
        throw "Python not found and --SkipWinget given."
    }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) {
    $wpy = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Recurse -Filter python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($wpy) { $env:Path = $wpy.DirectoryName + ";" + $env:Path; $py = $wpy.FullName }
}
if (-not $py) { throw "Python is required - re-run after installing Python 3.9+." }

# --- native sCode bootstrap compiler --------------------------------------
if (-not (Get-Command cl -ErrorAction SilentlyContinue) -and -not (Get-Command clang -ErrorAction SilentlyContinue) -and -not (Get-Command gcc -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing LLVM/clang for native sCode bootstrap..."
    if (-not $SkipWinget) {
        winget install --id LLVM.LLVM --silent --accept-package-agreements --accept-source-agreements
        $llvm = "C:\Program Files\LLVM\bin"
        if (Test-Path $llvm) { $env:Path = $llvm + ";" + $env:Path }
    }
}

# --- ffmpeg codec suite --------------------------------------------------
Write-Host "==> Installing ffmpeg codec suite..."
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (-not $SkipWinget) {
        winget install --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements
    } elseif (-not $SkipChoco -and (Get-Command choco -ErrorAction SilentlyContinue)) {
        choco install ffmpeg -y
    }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
foreach ($tool in @("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")) {
    $src = (Get-Command $tool.Replace(".exe","") -ErrorAction SilentlyContinue).Source
    if (-not $src) {
        $src = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter $tool -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    }
    if ($src) {
        Copy-Item -Force $src (Join-Path $BIN $tool)
        Write-Host "  codec -> $BIN\$tool"
    }
}

# --- pip dependencies ----------------------------------------------------
Write-Host "==> Installing Python packages..."
& $py -m pip install --upgrade pip wheel
& $py -m pip install numpy PyQt6 sounddevice Pillow

Write-Host "==> Verify:"
& $py -c "import numpy, PyQt6.QtCore, sounddevice, PIL; print('python deps OK')"
& (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source -hide_banner -version | Select-Object -First 1
Write-Host "==> Done."
Write-Host "==> Host dependency provisioning complete."
Write-Host "    The launcher will now verify the matching native sCode stage-0 automatically."
