@echo off
REM run_aria.bat — A.R.I.A. System Launcher (Windows)
REM Run from inside the aria/ directory.
REM Uses the project's .venv Python interpreter.

SET PYTHON=python
SET UVICORN=uvicorn
SET STREAMLIT=streamlit

echo.
echo ============================================================
echo    A.R.I.A.  -- Autonomous Road Infrastructure Auditor
echo    Bengaluru Municipal Road Defect Enforcement  v1.0
echo ============================================================
echo.

echo [1/3] Initialising database...
%PYTHON% db\schema.py
%PYTHON% db\seed.py
echo.

echo [2/3] Setting up model weights...
%PYTHON% pipeline\setup_model.py
echo.

echo [3/3] Starting FastAPI server in background...
start "ARIA-FastAPI" %UVICORN% api.main:app --host 0.0.0.0 --port 8000 --reload
timeout /t 3 /nobreak >nul

echo.
echo    FastAPI  : http://localhost:8000
echo    API docs : http://localhost:8000/docs
echo.
echo Starting Streamlit dashboard (press Ctrl+C to stop)...
echo    Dashboard: http://localhost:8501
echo.

%STREAMLIT% run dashboard\app.py --server.port 8501
