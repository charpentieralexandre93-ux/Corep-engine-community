@echo off
setlocal
cd /d "%~dp0"
python scripts\launch_community_gui.py
if errorlevel 1 pause
endlocal
