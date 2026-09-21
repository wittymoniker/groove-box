@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo [Groovebox] Windows launcher - runtime verification/provisioning

set "PYEXE="
where python >nul 2>nul && set "PYEXE=python"
if not defined PYEXE where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE goto :PROVISION

set "GBPYFILE=%TEMP%\groovebox-python-%RANDOM%-%RANDOM%.txt"
%PYEXE% "%~dp0scripts\ensure_runtime_dependencies.py" > "%GBPYFILE%"
if errorlevel 1 goto :PROVISION_CLEAN
set /p "GBPY="<"%GBPYFILE%"
del /q "%GBPYFILE%" >nul 2>nul
if not defined GBPY goto :PROVISION
goto :READY

:PROVISION_CLEAN
del /q "%GBPYFILE%" >nul 2>nul
:PROVISION
echo [Groovebox] Provisioning/repairing Windows dependencies...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_deps_windows.ps1"
if errorlevel 1 exit /b %errorlevel%
set "PYEXE="
where python >nul 2>nul && set "PYEXE=python"
if not defined PYEXE where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
  echo [Groovebox] ERROR: Python unavailable after provisioning.
  exit /b 2
)
set "GBPYFILE=%TEMP%\groovebox-python-%RANDOM%-%RANDOM%.txt"
%PYEXE% "%~dp0scripts\ensure_runtime_dependencies.py" > "%GBPYFILE%"
if errorlevel 1 (
  del /q "%GBPYFILE%" >nul 2>nul
  echo [Groovebox] ERROR: required runtime still unavailable after provisioning.
  exit /b 2
)
set /p "GBPY="<"%GBPYFILE%"
del /q "%GBPYFILE%" >nul 2>nul

:READY
"%GBPY%" "%~dp0scripts\provision_first_launch.py"
if errorlevel 1 exit /b %errorlevel%
"%GBPY%" "%~dp0sCode\scripts\ensure-stage0.py" >nul
if errorlevel 1 exit /b %errorlevel%
"%GBPY%" "%~dp0scripts\ensure_native_scode_stage0.py"
if errorlevel 1 exit /b %errorlevel%
"%GBPY%" "%~dp0launch_groovebox.py" %*
set "GBRC=%errorlevel%"
if not "%GBRC%"=="0" (
  echo.
  echo [Groovebox] ERROR: Groovebox exited abnormally with code %GBRC%.
  echo [Groovebox] Crash logs are under %%APPDATA%%\MathematiciansGroovebox\logs
  pause
)
exit /b %GBRC%
