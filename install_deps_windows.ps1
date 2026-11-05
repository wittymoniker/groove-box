param([switch]$SkipWinget,[switch]$SkipChoco)
$ErrorActionPreference = "Stop"
$env:PYTHONHOME = $null
$env:PYTHONPATH = $null
$env:PYTHONPYCACHEPREFIX = $null
Write-Host "==> Groovebox installer: Windows"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BIN = Join-Path $ROOT "bin"
New-Item -ItemType Directory -Force -Path $BIN | Out-Null

function Add-ToUserPath([string]$dir) {
    $cur = [Environment]::GetEnvironmentVariable("Path", "User")
    if (($cur -split ";") -notcontains $dir) {
        $new = if ([string]::IsNullOrEmpty($cur)) { $dir } else { "$cur;$dir" }
        [Environment]::SetEnvironmentVariable("Path", $new, "User")
    }
}
Add-ToUserPath $BIN

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    if ($SkipWinget) { throw "Python not found and -SkipWinget was supplied." }
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
if (Get-Command py -ErrorAction SilentlyContinue) { $py = (Get-Command py).Source; $pyArgs = @('-3') }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = (Get-Command python).Source }
else { throw "Python is unavailable after installation." }
if (-not $pyArgs) { $pyArgs = @() }

if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue) -and -not (Get-Command link.exe -ErrorAction SilentlyContinue)) {
    if (-not $SkipWinget -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "==> Installing Visual Studio C++ Build Tools for Rust/C++ linking"
        winget install --id Microsoft.VisualStudio.2022.BuildTools -e --silent --accept-package-agreements --accept-source-agreements --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
    } else {
        Write-Warning "MSVC Build Tools not detected; Rust cdylib linking may require Visual Studio C++ Build Tools."
    }
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (-not $SkipWinget) { winget install --id Gyan.FFmpeg -e --silent --accept-package-agreements --accept-source-agreements }
    elseif (-not $SkipChoco -and (Get-Command choco -ErrorAction SilentlyContinue)) { choco install ffmpeg -y }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
foreach ($tool in @("ffmpeg.exe","ffprobe.exe","ffplay.exe")) {
    $base = $tool.Replace('.exe','')
    $cmd = Get-Command $base -ErrorAction SilentlyContinue
    $src = if ($cmd) { $cmd.Source } else { $null }
    if (-not $src) {
        $src = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter $tool -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    }
    if ($src) { Copy-Item -Force $src (Join-Path $BIN $tool) }
}

$Selected = & $py @pyArgs "$ROOT\scripts\ensure_runtime_dependencies.py" --force-install
if ($LASTEXITCODE -ne 0 -or -not $Selected) { throw "Groovebox Python/browser runtime provisioning failed." }
$Selected = ($Selected | Select-Object -Last 1).Trim()
& $Selected "$ROOT\scripts\provision_first_launch.py"
if ($LASTEXITCODE -ne 0) { throw "Local FFmpeg/ffprobe provisioning failed." }
& $Selected -c "import numpy, scipy, cffi, sounddevice, PIL; import PyQt6.QtCore, PyQt6.QtMultimedia, PyQt6.QtMultimediaWidgets; print('Groovebox required Qt/Multimedia runtime OK')"
if ($LASTEXITCODE -ne 0) { throw "Groovebox complete Python/Qt runtime verification failed." }
& $Selected -c "import subprocess, sys; subprocess.run([sys.executable, '-c', 'import PyQt6.QtWebEngineWidgets'], check=True, timeout=30)"
if ($LASTEXITCODE -ne 0) { Write-Warning "Optional browser probe failed; main audio/editor runtime remains available." }
& $Selected "$ROOT\scripts\ensure_native_scode_stage0.py"
if ($LASTEXITCODE -ne 0) { throw "Native sCode stage-0 verification failed." }
& $Selected "$ROOT\scripts\ensure_rust_toolchain.py" --install
if ($LASTEXITCODE -ne 0) { Write-Warning "Optional Rust toolchain unavailable; fallback remains available." }
& $Selected "$ROOT\scripts\build_rust_accel.py"
if ($LASTEXITCODE -ne 0) { Write-Warning "Optional Rust accelerator build failed; fallback remains available." }
Write-Host "==> Done. Launch with LAUNCH_GROOVEBOX_WINDOWS.bat"
