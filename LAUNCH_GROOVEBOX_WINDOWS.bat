@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [Groovebox] Windows launcher - automatic first-run provisioning

rem Resolve a usable Python first. If absent, let the bundled dependency installer
rem install it via winget, then re-resolve it before launch.
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
  where python >nul 2>nul && set "PYEXE=python"
)

if not exist ".groovebox_provisioned_windows" goto :PROVISION
if not exist "bin\ffmpeg.exe" goto :PROVISION
if not exist "bin\ffprobe.exe" goto :PROVISION
if not defined PYEXE goto :PROVISION
goto :AFTER_PROVISION

:PROVISION
echo [Groovebox] Provisioning Windows dependencies automatically...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_deps_windows.ps1"
if errorlevel 1 (
  echo [Groovebox] ERROR: automatic Windows dependency provisioning failed.
  exit /b 2
)

set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
  where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
  echo [Groovebox] ERROR: Python is still unavailable after provisioning.
  exit /b 2
)

%PYEXE% "%~dp0scripts\provision_first_launch.py"
if errorlevel 1 exit /b %errorlevel%
> ".groovebox_provisioned_windows" echo provisioned

:AFTER_PROVISION
if not defined PYEXE (
  where py >nul 2>nul && set "PYEXE=py -3"
  if not defined PYEXE where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
  echo [Groovebox] ERROR: Python is unavailable.
  exit /b 2
)

%PYEXE% "%~dp0launch_groovebox.py" %*
set "GBRC=%errorlevel%"
if not "%GBRC%"=="0" (
  echo.
  echo [Groovebox] ERROR: Groovebox exited abnormally with code %GBRC%.
  echo [Groovebox] Crash logs are under:
  echo [Groovebox]   %%APPDATA%%\MathematiciansGroovebox\logs
  echo [Groovebox] Open LATEST_CRASH_LOG.txt first.
  echo.
  echo [Groovebox] This window will stay open so the error cannot disappear.
  pause
)
exit /b %GBRC%
