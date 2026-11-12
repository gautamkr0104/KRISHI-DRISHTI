@echo off
setlocal
cd /d "%~dp0"

echo ======================================================================
echo   KRISHI-DRISHTI :: 1-CLICK ESP32 DEV-CONTROLLER FLASHER
echo ======================================================================
echo.

set PORT=COM7
if not "%~1"=="" set PORT=%~1

set ESPTOOL="C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\tools\esptool_py\5.3.1\esptool.exe"
set BUILD_DIR=firmware\KRISHI_DRISHTI_Controller\build\esp32.esp32.esp32

if not exist %ESPTOOL% (
    echo [ERROR] esptool.exe not found at %ESPTOOL%
    pause
    exit /b 1
)

echo Target Port: %PORT%
echo.
echo Flashing ESP32 DevKit V1 Handheld Controller...
%ESPTOOL% -p %PORT% -b 115200 --before default-reset --after hard-reset write-flash -z --flash-mode dio --flash-freq 40m --flash-size 4MB 0x1000 "%BUILD_DIR%\KRISHI_DRISHTI_Controller.ino.bootloader.bin" 0x8000 "%BUILD_DIR%\KRISHI_DRISHTI_Controller.ino.partitions.bin" 0xe000 "%BUILD_DIR%\boot_app0.bin" 0x10000 "%BUILD_DIR%\KRISHI_DRISHTI_Controller.ino.bin"

if %ERRORLEVEL% equ 0 (
    echo.
    echo ======================================================================
    echo   [SUCCESS] ESP32 CONTROLLER FLASHED SUCCESSFULLY!
    echo ======================================================================
) else (
    echo.
    echo ======================================================================
    echo   [FAILED] Could not flash ESP32 Controller on %PORT%.
    echo ======================================================================
)
