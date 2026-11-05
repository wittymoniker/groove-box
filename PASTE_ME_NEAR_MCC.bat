@echo off
rem Builds MCC_GALLERY\index.html for the .MCC files in this folder.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 PASTE_ME_NEAR_MCC.py "%~dp0" & goto :eof)
python PASTE_ME_NEAR_MCC.py "%~dp0"
pause
