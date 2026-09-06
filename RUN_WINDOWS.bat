@echo off
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py "%~dp0finish_product.py" %*
) else (
  python "%~dp0finish_product.py" %*
)
pause
