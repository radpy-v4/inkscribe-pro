@echo off
chcp 65001 >nul
echo ========================================================
echo   InkScribe Pro - Otomatik Derleme Scripti (PyInstaller)
echo ========================================================
echo.

REM 1. Python ve Sanal Ortam Kontrolü
set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
    echo [i] Yerel .venv sanal ortami kullaniliyor...
    set "PYTHON_CMD=.venv\Scripts\python.exe"
)

%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
    echo [X] HATA: Python bulunamadi! Lutfen Python'in kurulu ve PATH'e ekli oldugundan emin olun.
    pause
    exit /b 1
)

REM 2. Birim Testleri Calistir
echo [1/4] Birim testleri calistiriliyor...
%PYTHON_CMD% -m unittest tests/test_logic.py
if errorlevel 1 (
    echo [X] HATA: Testler basarisiz oldu! Derleme durduruldu.
    pause
    exit /b 1
)
echo [✓] Tum testler basariyla gecti.
echo.

REM 3. PyInstaller Kontrolu
echo [2/4] PyInstaller kontrol ediliyor...
%PYTHON_CMD% -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [i] PyInstaller yukleniyor...
    %PYTHON_CMD% -m pip install pyinstaller
)

REM 4. Temizlik (Eski build kalintilari)
echo [3/4] Eski derleme kalintilari temizleniyor...
if exist "build" rmdir /s /q "build"

REM 5. Derleme Islemi
echo [4/4] TabletNotAlici.exe derleniyor (TabletNotAlici.spec)...
%PYTHON_CMD% -m PyInstaller --noconfirm --clean TabletNotAlici.spec
if errorlevel 1 (
    echo.
    echo [X] HATA: Derleme sirasinda bir hata olustu!
    pause
    exit /b 1
)

echo.
echo ========================================================
if exist "dist\TabletNotAlici.exe" (
    echo [OK] TEBRIKLER! Derleme basariyla tamamlandi.
    echo [OK] Cikti: dist\TabletNotAlici.exe
    for %%I in ("dist\TabletNotAlici.exe") do echo [OK] Dosya Boyutu: %%~zI bayt
) else (
    echo [X] HATA: dist\TabletNotAlici.exe bulunamadi!
)
echo ========================================================
echo.
pause
