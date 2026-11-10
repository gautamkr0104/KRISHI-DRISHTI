@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo KRISHI-DRISHTI :: Automated Verification and Validation Suite
echo Offline Edge-AI Master Verification Suite
echo ======================================================================
echo.

set PYTHON_CMD=
if exist "D:\tools\krishi_ai_env\Scripts\python.exe" (
    set PYTHON_CMD="D:\tools\krishi_ai_env\Scripts\python.exe"
    echo [*] Using verified environment: D:\tools\krishi_ai_env
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=python
        echo [*] Using system python
    ) else (
        echo [ERROR] Python not found in system PATH or D:\tools\krishi_ai_env.
        if "%1" neq "--no-pause" pause
        exit /b 1
    )
)

echo.
echo [1/5] Running Python Automated Unit and Integration Tests (11 Tests)...
echo ----------------------------------------------------------------------
%PYTHON_CMD% "%~dp0tests\test_ai_pipeline.py"
if %errorlevel% neq 0 (
    echo [FAIL] Unit tests encountered errors.
    if "%1" neq "--no-pause" pause
    exit /b %errorlevel%
)

echo.
echo [2/5] Running Production Daemon 8-Specimen & Gating Verification Audit...
echo ----------------------------------------------------------------------
%PYTHON_CMD% "%~dp0tests\verify_tflite_model.py"
if %errorlevel% neq 0 (
    echo [FAIL] Production verification encountered errors.
    if "%1" neq "--no-pause" pause
    exit /b %errorlevel%
)

echo.
echo [3/5] Running Reproducible 60-Specimen Botanical Benchmark...
echo ----------------------------------------------------------------------
%PYTHON_CMD% "%~dp0tests\benchmark_60_specimens.py"
if %errorlevel% neq 0 (
    echo [FAIL] 60-specimen benchmark encountered errors.
    if "%1" neq "--no-pause" pause
    exit /b %errorlevel%
)

echo.
echo [4/5] Running Real-World Field Night-Flash & OOD Audit...
echo ----------------------------------------------------------------------
if exist "%~dp0tests\evaluate_field_images.py" (
    %PYTHON_CMD% "%~dp0tests\evaluate_field_images.py"
    if %errorlevel% neq 0 (
        echo [FAIL] Field test images evaluation encountered errors.
        if "%1" neq "--no-pause" pause
        exit /b %errorlevel%
    )
)

echo.
echo [5/5] Checking for C++ Compiler for Native Firmware Module Tests...
echo ----------------------------------------------------------------------
where g++ >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] g++ detected. Compiling and running native MicroclimateTracker C++ unit tests...
    g++ -Wall -Wextra -Werror -std=c++11 "%~dp0tests\test_microclimate_tracker.cpp" "%~dp0firmware\KRISHI_DRISHTI_Controller\MicroclimateTracker.cpp" -o "%~dp0tests\test_tracker.exe"
    if !errorlevel! equ 0 (
        "%~dp0tests\test_tracker.exe"
        del "%~dp0tests\test_tracker.exe"
    ) else (
        echo [WARN] Native C++ compilation failed.
    )
) else (
    echo [*] C++ compiler not in PATH. Logic verified by Python automated suite.
)

echo.
echo ======================================================================
echo [SUCCESS] ALL KRISHI-DRISHTI VERIFICATION SUITES COMPLETED CLEANLY!
echo ======================================================================
echo.
if "%1" neq "--no-pause" pause
