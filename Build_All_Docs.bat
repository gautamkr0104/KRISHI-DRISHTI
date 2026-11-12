@echo off
setlocal
cd /d "%~dp0"

echo ======================================================================
echo   KRISHI-DRISHTI :: 1-CLICK BUILD ALL SUBMISSION DOCS & ARCHIVES
echo ======================================================================
echo.

set PY="C:\Users\DELL\krishi_pdf_env\Scripts\python.exe"
%PY% scratch\build_and_sync_all.py
if %ERRORLEVEL% equ 0 (
    echo [OK] All documents and release archives generated cleanly in uploading_documents!
) else (
    echo [FAIL] Document compilation failed.
)
pause
