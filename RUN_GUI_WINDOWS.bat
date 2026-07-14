@echo off
setlocal EnableExtensions

REM =============================================================================
REM COREP Engine Community v6.10.0 - Lancement GUI utilisateur
REM =============================================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [ERREUR] Installation non trouvee.
    echo Double-clique d'abord sur INSTALL_WINDOWS.bat.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

python scripts\launch_community_gui.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERREUR] Le GUI Community s'est arrete avec le code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%
