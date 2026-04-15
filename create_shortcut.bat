@echo off
REM Creates a Desktop shortcut to AgenticFlow's BASLAT.bat
REM Usage: cift tikla -> masaustune kisayol olusturur

setlocal
set "SCRIPT_DIR=%~dp0"
set "TARGET=%SCRIPT_DIR%BASLAT.bat"
set "DESKTOP=%USERPROFILE%\Desktop"
set "LINK=%DESKTOP%\AgenticFlow.lnk"

if not exist "%TARGET%" (
    echo [HATA] BASLAT.bat bulunamadi: %TARGET%
    pause
    exit /b 1
)

echo [AgenticFlow] Masaustu kisayolu olusturuluyor...
echo   Hedef:   %TARGET%
echo   Kisayol: %LINK%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $sc = $ws.CreateShortcut('%LINK%'); ^
     $sc.TargetPath = '%TARGET%'; ^
     $sc.WorkingDirectory = '%SCRIPT_DIR%'; ^
     $sc.IconLocation = '%SystemRoot%\System32\SHELL32.dll,137'; ^
     $sc.Description = 'AgenticFlow - Ticimax Workflow Automation'; ^
     $sc.WindowStyle = 1; ^
     $sc.Save()"

if exist "%LINK%" (
    echo.
    echo [AgenticFlow] Kisayol olusturuldu: %LINK%
    echo Masaustundeki "AgenticFlow" simgesine cift tiklayarak baslatabilirsin.
) else (
    echo [HATA] Kisayol olusturulamadi.
    exit /b 1
)

echo.
pause
