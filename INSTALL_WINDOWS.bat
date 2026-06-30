@echo off
setlocal EnableExtensions

REM =============================================================================
REM COREP Engine Community v6.6.0 - Installation utilisateur Windows
REM Double-clic : cree .venv, installe le projet et prepare les dossiers runtime.
REM =============================================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   COREP Engine Community v6.6.0 - Installation
echo ============================================================
echo.

set "PYTHON_CMD=python"
where py >nul 2>nul
if "%ERRORLEVEL%"=="0" set "PYTHON_CMD=py -3"

%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python 3.11+ introuvable.
    echo Installe Python depuis https://www.python.org/downloads/windows/
    echo Coche "Add python.exe to PATH" pendant l'installation.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creation de l'environnement virtuel .venv ...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [OK] Environnement virtuel deja present.
)

call ".venv\Scripts\activate.bat"

echo [INFO] Mise a jour de pip ...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [INFO] Installation du projet Community ...
python -m pip install -e ".[postgres]"
if errorlevel 1 goto :error

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [INFO] Fichier .env cree depuis .env.example.
    )
)
if not exist "logs" mkdir "logs"
if not exist "output" mkdir "output"

echo.
echo [OK] Installation terminee.
echo Prochaine etape : double-clique sur RUN_GUI_WINDOWS.bat
echo.
pause
exit /b 0

:error
echo.
echo [ERREUR] Installation interrompue. Lis le message au-dessus.
pause
exit /b 1
