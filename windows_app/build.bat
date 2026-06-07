@echo off
REM Build script pour 3DS Hunter - genere un .exe Windows autonome
cd /d "%~dp0"

echo ============================================
echo  3DS Hunter v1.1.0 - Build Windows EXE
echo ============================================
echo Dossier de travail : %CD%
echo.

if not exist "requirements.txt" (
    echo [ERREUR] requirements.txt introuvable.
    pause
    exit /b 1
)

if not exist "main.py" (
    echo [ERREUR] main.py introuvable.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Telecharge Python 3.10+ sur https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] Echec installation dependances.
    pause
    exit /b 1
)

echo.
echo Nettoyage pandas/numpy si presents...
python -m pip uninstall -y pandas numpy >nul 2>nul

echo.
echo [2/5] Installation de Chromium pour Deep Scan (~150 MB, premiere fois seulement)...
python -m playwright install chromium
if errorlevel 1 (
    echo [AVERTISSEMENT] Echec install Chromium. Le Deep Scan ne fonctionnera pas.
    echo Tu pourras installer plus tard via le bouton Deep Scan dans l'app.
    timeout /t 3
)

echo.
echo [3/5] Nettoyage anciens builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "3DS_Hunter.spec" del "3DS_Hunter.spec"

echo.
echo [4/5] Compilation PyInstaller (2-5 min)...
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
    --hidden-import playwright ^
    --hidden-import playwright.sync_api ^
    --exclude-module pandas ^
    --exclude-module numpy ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --collect-all customtkinter ^
    --collect-all fake_useragent ^
    main.py

if errorlevel 1 (
    echo [ERREUR] La compilation a echoue.
    pause
    exit /b 1
)

echo.
echo [5/5] Termine !
echo.
echo ============================================
echo  Build reussi !
echo  Executable : %CD%\dist\3DS_Hunter.exe
echo.
echo  NOTE : Playwright Chromium est telecharge dans
echo  %%USERPROFILE%%\AppData\Local\ms-playwright\
echo  Le .exe l'utilisera depuis cet emplacement.
echo ============================================
echo.

explorer dist
pause
