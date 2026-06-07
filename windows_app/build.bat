@echo off
REM Build script pour 3DS Hunter - genere un .exe Windows autonome
REM Usage : double-clic sur build.bat OU `build.bat` dans cmd

echo ============================================
echo  3DS Hunter - Build Windows EXE
echo ============================================
echo.

REM Verifie Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Telecharge Python 3.10+ sur https://www.python.org/downloads/
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
    --add-data "data;data" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import PIL._tkinter_finder ^
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
echo  L'executable se trouve dans : dist\3DS_Hunter.exe
echo ============================================
echo.

REM Ouvre le dossier
explorer dist
pause
