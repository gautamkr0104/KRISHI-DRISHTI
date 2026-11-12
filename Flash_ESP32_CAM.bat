@echo off
setlocal
cd /d "%~dp0"

echo ======================================================================
echo   KRISHI-DRISHTI :: 1-CLICK ESP32-CAM FAST FLASHER
echo ======================================================================
echo.

set PORT=COM7
if not "%~1"=="" set PORT=%~1

set ESPTOOL="C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\tools\esptool_py\5.3.1\esptool.exe"
set BUILD_DIR=firmware\KRISHI_DRISHTI_Camera\build\esp32.esp32.esp32cam

if not exist %ESPTOOL% (
    echo [ERROR] esptool.exe not found at %ESPTOOL%
    pause
    exit /b 1
)

echo Target Port: %PORT%
echo.
echo ----------------------------------------------------------------------
echo CRITICAL STEPS FOR ESP32-CAM ON FTDI / PROGRAMMER:
echo ----------------------------------------------------------------------
echo  1. Power: Connect FTDI 5V to ESP32-CAM 5V (NOT 3.3V, 3.3V causes brownout)
echo  2. Ground: Connect FTDI GND to ESP32-CAM GND
echo  3. Serial TX/RX (Must be crossed!):
echo     - FTDI TX  to ESP32-CAM U0R (GPIO 3)
echo     - FTDI RX  to ESP32-CAM U0T (GPIO 1)
echo  4. Flash Mode Jumper:
echo     - Connect GPIO 0 (IO0) to GND!
echo  5. Reset the chip:
echo     - Press and release the tiny RST button on the back of the camera module.
echo ----------------------------------------------------------------------
echo.

%ESPTOOL% -p %PORT% -b 115200 --before default-reset --after hard-reset write-flash -z --flash-mode dio --flash-freq 40m --flash-size 4MB 0x1000 "%BUILD_DIR%\KRISHI_DRISHTI_Camera.ino.bootloader.bin" 0x8000 "%BUILD_DIR%\KRISHI_DRISHTI_Camera.ino.partitions.bin" 0xe000 "%BUILD_DIR%\boot_app0.bin" 0x10000 "%BUILD_DIR%\KRISHI_DRISHTI_Camera.ino.bin"

if %ERRORLEVEL% equ 0 (
    echo.
    echo ======================================================================
    echo   [SUCCESS] ESP32-CAM FLASHED SUCCESSFULLY!
    echo   NEXT STEP: Disconnect GPIO 0 from GND and press RST to run!
    echo ======================================================================
) else (
    echo.
    echo ======================================================================
    echo   [FAILED] Could not connect to ESP32-CAM.
    echo ======================================================================
)
echo.
