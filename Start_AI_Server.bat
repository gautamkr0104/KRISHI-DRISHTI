@echo off
setlocal
cd /d "%~dp0ai_engine"

echo ======================================================================
echo   KRISHI-DRISHTI :: LOCAL OFFLINE AI ENGINE SERVER
echo ======================================================================
echo.
echo Launching local HTTP server for offline MobileNetV3 WASM engine...
echo URL: http://localhost:8000/krishi_ai_server.html
echo.
set "PY_CMD=python"
if exist "C:\Users\DELL\krishi_pdf_env\Scripts\python.exe" set "PY_CMD=C:\Users\DELL\krishi_pdf_env\Scripts\python.exe"

%PY_CMD% -m http.server 8000
