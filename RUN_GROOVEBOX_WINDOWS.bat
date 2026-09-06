@echo off
cd /d "%~dp0Groovebox"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py run_groovebox.py
) else (
  python run_groovebox.py
)
pause
