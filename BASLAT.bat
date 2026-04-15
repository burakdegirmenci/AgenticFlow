@echo off
setlocal EnableDelayedExpansion
title AgenticFlow Launcher
cd /d "%~dp0"

:MENU
cls
echo.
echo  ============================================================
echo    AgenticFlow - Ticimax Workflow ^& Automation Platformu
echo  ============================================================
echo.
echo    1) Backend + Frontend baslat (ikisi ayri pencerede)
echo    2) Sadece backend baslat (bu pencere)
echo    3) Sadece frontend baslat (bu pencere)
echo    4) Browser'da UI ac (http://127.0.0.1:5173)
echo    5) Backend API docs ac (http://127.0.0.1:8000/docs)
echo    6) Backend bagimliliklari yeniden kur
echo    7) Frontend bagimliliklari yeniden kur
echo    0) Cikis
echo.
set /p choice="   Secim: "

if "%choice%"=="1" goto BOTH
if "%choice%"=="2" goto BACKEND
if "%choice%"=="3" goto FRONTEND
if "%choice%"=="4" goto OPEN_UI
if "%choice%"=="5" goto OPEN_DOCS
if "%choice%"=="6" goto REINSTALL_BACKEND
if "%choice%"=="7" goto REINSTALL_FRONTEND
if "%choice%"=="0" goto END
goto MENU

:BOTH
echo.
echo [AgenticFlow] Backend penceresi aciliyor...
start "AgenticFlow Backend" cmd /k "%~dp0start_backend.bat"
timeout /t 3 /nobreak >nul
echo [AgenticFlow] Frontend penceresi aciliyor...
start "AgenticFlow Frontend" cmd /k "%~dp0start_frontend.bat"
timeout /t 5 /nobreak >nul
echo [AgenticFlow] Browser aciliyor...
start "" "http://127.0.0.1:5173"
echo.
echo [AgenticFlow] Iki servis ayri pencerelerde calisiyor.
pause
goto MENU

:BACKEND
call start_backend.bat
goto MENU

:FRONTEND
call start_frontend.bat
goto MENU

:OPEN_UI
start "" "http://127.0.0.1:5173"
goto MENU

:OPEN_DOCS
start "" "http://127.0.0.1:8000/docs"
goto MENU

:REINSTALL_BACKEND
cd backend
if exist .deps_installed del .deps_installed
if exist venv (
    echo [AgenticFlow] Venv siliniyor...
    rmdir /s /q venv
)
cd ..
echo [AgenticFlow] Venv yeniden kurulacak, start_backend ile tekrar baslat.
pause
goto MENU

:REINSTALL_FRONTEND
cd frontend
if exist node_modules (
    echo [AgenticFlow] node_modules siliniyor...
    rmdir /s /q node_modules
)
cd ..
echo [AgenticFlow] node_modules yeniden kurulacak, start_frontend ile tekrar baslat.
pause
goto MENU

:END
endlocal
