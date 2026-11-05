@echo off
setlocal EnableExtensions
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONPYCACHEPREFIX="
cd /d "%~dp0"
echo [Groovebox] Windows launcher - runtime verification/provisioning

call :SELECT_PYTHON
if not defined PYEXE goto :PROVISION

set "GBPYFILE=%TEMP%\groovebox-python-%RANDOM%-%RANDOM%.txt"
"%PYEXE%" %PYARGS% "%~dp0scripts\ensure_runtime_dependencies.py" > "%GBPYFILE%"
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
call :SELECT_PYTHON
if not defined PYEXE (
  echo [Groovebox] ERROR: Python unavailable after provisioning.
  exit /b 2
)
set "GBPYFILE=%TEMP%\groovebox-python-%RANDOM%-%RANDOM%.txt"
"%PYEXE%" %PYARGS% "%~dp0scripts\ensure_runtime_dependencies.py" > "%GBPYFILE%"
if errorlevel 1 (
  del /q "%GBPYFILE%" >nul 2>nul
  echo [Groovebox] ERROR: required runtime still unavailable after provisioning.
  exit /b 2
)
set /p "GBPY="<"%GBPYFILE%"
del /q "%GBPYFILE%" >nul 2>nul

:READY
if not defined GBPY exit /b 2
if not exist "%GBPY%" (
  echo [Groovebox] ERROR: Runtime checker returned a missing Python executable.
  exit /b 2
)
"%GBPY%" "%~dp0scripts\provision_first_launch.py"
if errorlevel 1 exit /b %errorlevel%
"%GBPY%" "%~dp0scripts\ensure_native_scode_stage0.py"
if errorlevel 1 exit /b %errorlevel%
if "%GROOVEBOX_REBUILD_NATIVE%"=="1" goto :BUILD_OPTIONAL_RUST
if exist "%~dp0native\groovebox_rust_accel.dll" goto :START_APP
:BUILD_OPTIONAL_RUST
"%GBPY%" "%~dp0scripts\ensure_rust_toolchain.py" --install
if errorlevel 1 echo [Groovebox] WARNING: Rust setup failed; C++/NumPy fallback remains available.
"%GBPY%" "%~dp0scripts\build_rust_accel.py"
if errorlevel 1 echo [Groovebox] WARNING: Rust accelerator build failed; continuing.
:START_APP
set "GROOVEBOX_RUNTIME_VERIFIED_PYTHON=%GBPY%"
"%GBPY%" "%~dp0launch_groovebox.py" %*
set "GBRC=%errorlevel%"
if not "%GBRC%"=="0" (
  echo.
  echo [Groovebox] ERROR: Groovebox exited abnormally with code %GBRC%.
  echo [Groovebox] Crash logs are under %%APPDATA%%\MathematiciansGroovebox\logs
  pause
)
exit /b %GBRC%

:SELECT_PYTHON
set "PYEXE="
set "PYARGS="
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYEXE=%~dp0.venv\Scripts\python.exe"
  exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
  set "PYEXE=py"
  set "PYARGS=-3"
  exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 set "PYEXE=python"
exit /b 0
