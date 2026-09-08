@echo off
set SCRIPT=%~dp0groovebox_mechanical_audit.py
if "%~1"=="" (
  py "%SCRIPT%" .
) else (
  py "%SCRIPT%" "%~1"
)
pause
