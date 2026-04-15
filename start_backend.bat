@echo off
setlocal
cd /d "%~dp0backend"

if not exist venv\Scripts\python.exe (
    echo [AgenticFlow] Virtualenv bulunamadi, olusturuluyor...
    python -m venv venv
    if errorlevel 1 (
        echo [HATA] Python bulunamadi veya venv olusturulamadi.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

if not exist .deps_installed (
    echo [AgenticFlow] Bagimliliklar kuruluyor...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [HATA] Bagimliliklar kurulamadi.
        pause
        exit /b 1
    )
    type nul > .deps_installed
)

if not exist .env (
    echo [UYARI] .env dosyasi yok. .env.example'dan kopyalaniyor...
    copy .env.example .env >nul
    echo [UYARI] Lutfen .env dosyasini acip ANTHROPIC_API_KEY ve MASTER_KEY degerlerini doldur.
)

echo [AgenticFlow] Backend baslatiliyor: http://127.0.0.1:8000
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
endlocal
