@echo off
setlocal EnableExtensions

REM =============================================================================
REM COREP Engine Community v6.6.0 - Bootstrap SQL utilisateur
REM Liste le plan SQL Community et regenere le manifeste SQL.
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

echo.
echo ============================================================
echo   COREP Community - Plan SQL public SA + SA-CCR
echo ============================================================
echo.

python -m corep_crr3.community_bootstrap --list
if errorlevel 1 goto :error

echo.
echo [INFO] Generation du manifeste SQL Community ...
python -m corep_crr3.community_bootstrap --write-manifest
if errorlevel 1 goto :error

echo.
echo [OK] Bootstrap SQL Community verifie.
pause
exit /b 0

:error
echo.
echo [ERREUR] Bootstrap SQL Community interrompu.
pause
exit /b 1
