@echo off
REM Build script pour 3DS Hunter - genere un .exe Windows autonome
REM Force le repertoire courant a celui du script (resout les pbs de double-clic)
cd /d "%~dp0"

echo ============================================
echo  3DS Hunter - Build Windows EXE
echo ============================================
echo Dossier de travail : %CD%
echo.

REM Verifie que requirements.txt est present
if not exist "requirements.txt" (
    echo [ERREUR] requirements.txt introuvable dans : %CD%
    echo Assure-toi que build.bat est bien dans le dossier 'windows_app'
    echo a cote de main.py et requirements.txt
    pause
    exit /b 1
)

REM Verifie que main.py est present
if not exist "main.py" (
    echo [ERREUR] main.py introuvable.
    pause
    exit /b 1
)

REM Verifie Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Telecharge Python 3.10+ sur https://www.python.org/downloads/
    echo IMPORTANT : coche "Add Python to PATH" pendant l'installation.
    pause
    exit /b 1
)

echo [1/4] Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] Echec de l'installation des dependances.
    pause
    exit /b 1
)

REM Desinstalle pandas/numpy s'ils trainent d'une installation precedente
echo.
echo Nettoyage pandas/numpy (non utilises) ...
python -m pip uninstall -y pandas numpy >nul 2>nul

echo.
echo [2/4] Nettoyage des anciens builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "3DS_Hunter.spec" del "3DS_Hunter.spec"

echo.
echo [3/4] Compilation avec PyInstaller (cela peut prendre 2-3 min)...
python -m PyInstaller ^
    --name "3DS_Hunter" ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --add-data "data;data" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import PIL._tkinter_finder ^
    --hidden-import openpyxl ^
    --hidden-import lxml ^
    --hidden-import lxml._elementpath ^
    --hidden-import bs4 ^
    --hidden-import fake_useragent ^
    --exclude-module pandas ^
    --exclude-module numpy ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --collect-all customtkinter ^
    --collect-all fake_useragent ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERREUR] La compilation a echoue.
    pause
    exit /b 1
)

echo.
echo [4/4] Termine !
echo.
echo ============================================
echo  Build reussi !
echo  L'executable : %CD%\dist\3DS_Hunter.exe
echo ============================================
echo.

REM Ouvre le dossier
explorer dist
pause
