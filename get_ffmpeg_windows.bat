@echo off
setlocal

cd /d "%~dp0"

if not exist "bin" mkdir "bin"

echo Downloading FFmpeg for Windows...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$u='https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'; ^
  $o=$env:TEMP+'\groovebox-ffmpeg.zip'; ^
  Invoke-WebRequest -Uri $u -OutFile $o; ^
  Expand-Archive -Force $o $env:TEMP'\groovebox-ffmpeg'; ^
  $d=Get-ChildItem $env:TEMP'\groovebox-ffmpeg' -Directory | Select-Object -First 1; ^
  Copy-Item ($d.FullName+'\bin\ffmpeg.exe') '.\bin\ffmpeg.exe' -Force; ^
  Copy-Item ($d.FullName+'\bin\ffprobe.exe') '.\bin\ffprobe.exe' -Force"

if errorlevel 1 (
    echo.
    echo FFmpeg download failed.
    exit /b 1
)

echo.
echo Installed:
bin\ffmpeg.exe -version
echo.
echo FFmpeg binaries are in:
echo %CD%\bin
