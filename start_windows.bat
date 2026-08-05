@echo off
echo ===================================================
echo A.R.I.A. - Automated Road Inspection & Accountability
echo Windows Startup Script
echo ===================================================
echo.

cd /d "%~dp0"

set "PYTHON_RUNTIME=%CD%\.python-runtime\cpython-3.11.14-windows-x86_64-none\python.exe"
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "ARIA_API_KEY=test-api-key"

echo [0/5] Stopping existing A.R.I.A. listeners on ports 3000 and 8000...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = @(3000, 8000); netstat -ano | ForEach-Object { if ($_ -match '^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$' -and $ports -contains [int]$matches[1]) { $matches[2] } } | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
echo.

echo [1/5] Checking Python Virtual Environment...
if not exist "%VENV_PYTHON%" (
    echo Creating virtual environment from bundled Python runtime...
    "%PYTHON_RUNTIME%" -m venv .venv
)
"%VENV_PYTHON%" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo Existing virtual environment is broken. Recreating it...
    "%PYTHON_RUNTIME%" -m venv .venv --clear
)

echo.
echo [2/5] Installing Backend Dependencies...
"%VENV_PYTHON%" -m pip install -r requirements.txt

echo.
echo [3/5] Checking Model Weights...
.\.venv\Scripts\python.exe -m scripts.download_model

echo.
echo [4/5] Starting FastAPI Backend (Port 8000)...
start "ARIA Backend" cmd /c "set ARIA_API_KEY=%ARIA_API_KEY%&& .\.venv\Scripts\python.exe -m uvicorn aria.api.app:app --reload --port 8000"

echo.
echo [5/5] Starting Frontend (Port 3000)...
cd frontend
(
    echo VITE_ARIA_API_URL="http://localhost:8000"
    echo VITE_ARIA_API_KEY="test-api-key"
) > .env.local
if not exist "node_modules" (
    echo Installing frontend dependencies...
    cmd /c npm install
)
start "ARIA Frontend" cmd /c "npm run dev -- --strictPort"

echo.
echo ===================================================
echo A.R.I.A. Services have been launched in new windows.
echo Frontend URL: http://localhost:3000
echo Backend API:  http://localhost:8000/docs
echo ===================================================
pause
