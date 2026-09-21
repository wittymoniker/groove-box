param([switch]$SkipWinget,[switch]$SkipChoco)
$ErrorActionPreference = "Stop"
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
if (Get-Command python -ErrorAction SilentlyContinue) { $py = (Get-Command python).Source }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = (Get-Command py).Source; $pyArgs = @('-3') }
else { throw "Python is unavailable after installation." }
if (-not $pyArgs) { $pyArgs = @() }

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
& $Selected -c "import numpy, scipy, cffi, sounddevice, PIL; import PyQt6.QtCore, PyQt6.QtWebEngineWidgets; print('Groovebox Python/browser runtime OK')"
if ($LASTEXITCODE -ne 0) { throw "Groovebox runtime verification failed." }
& $Selected "$ROOT\scripts\ensure_native_scode_stage0.py"
if ($LASTEXITCODE -ne 0) { throw "Native sCode stage-0 verification failed." }
Write-Host "==> Done. Launch with LAUNCH_GROOVEBOX_WINDOWS.bat"
