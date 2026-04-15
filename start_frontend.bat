@echo off
setlocal
cd /d "%~dp0frontend"

if not exist node_modules (
    echo [AgenticFlow] Frontend bagimliliklari kuruluyor...
    call npm install
    if errorlevel 1 (
        echo [HATA] npm install basarisiz.
        pause
        exit /b 1
    )
)

echo [AgenticFlow] Frontend baslatiliyor: http://127.0.0.1:5173
call npm run dev
endlocal
