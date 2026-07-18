@echo off
echo ===================================================
echo A.R.I.A. - Automated Road Inspection & Accountability
echo Windows Startup Script
echo ===================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Model Weights...
.\.venv\Scripts\python.exe -m scripts.download_model

echo.
echo [2/3] Starting FastAPI Backend (Port 8000)...
start "ARIA Backend" cmd /c ".\.venv\Scripts\python.exe -m uvicorn aria.api.app:app --reload --port 8000"

echo.
echo [3/3] Starting Frontend (Port 3000)...
cd frontend
if not exist "node_modules" (
    echo Installing frontend dependencies...
    cmd /c npm install
)
start "ARIA Frontend" cmd /c "npm run dev"

echo.
echo ===================================================
echo A.R.I.A. Services have been launched in new windows.
echo Frontend URL: http://localhost:3000
echo Backend API:  http://localhost:8000/docs
echo ===================================================
pause
