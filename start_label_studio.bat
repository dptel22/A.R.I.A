@echo off
setlocal

set "ARIA_ROOT=%~dp0"
set "LABEL_STUDIO_BASE_DATA_DIR=%ARIA_ROOT%.label-studio-data"
set "LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true"
set "LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=%ARIA_ROOT%data\demo"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process label-studio -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq '%ARIA_ROOT%.venv\Scripts\label-studio.exe' } | Stop-Process -Force"

cd /d C:\tmp
"%ARIA_ROOT%.venv\Scripts\label-studio.exe" start --port 8080
