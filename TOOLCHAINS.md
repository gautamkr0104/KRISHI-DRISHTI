# TOOLCHAINS.md — Local Toolchain & Build Manual

Exact commands and compiler options for every subsystem of KRISHI-DRISHTI. Paths below are relative to the repository root; substitute your own Python interpreter and serial port.

---

## 1. Python Environment

### Requirements
* **Python:** 3.10 or newer
* **Packages:** `ai-edge-litert` (or `tflite-runtime`), `numpy`, `Pillow`, `pyserial`
* Optional, only for regenerating documents: `pymupdf`, `python-docx`, `reportlab`

### Setup
```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# source .venv/bin/activate        # Linux / macOS
pip install ai-edge-litert numpy Pillow pyserial
```

### Running Python Scripts
Run all scripts from the repository root so relative asset paths resolve:
```bash
python tests/validate_hardware_field_captures.py
python tests/benchmark_60_specimens.py
python ai_engine/export_and_evaluate.py
```

---

## 2. Embedded ESP32 & Arduino Toolchain

### Required Tools
* **arduino-cli** (or the Arduino IDE 2.x) with the `esp32` core by Espressif installed
* **esptool** — bundled with the `esp32` core; used for direct binary flashing
* **Xtensa toolchain** — installed automatically by the `esp32` core (`xtensa-esp32-elf-g++`)

Install the core once:
```bash
arduino-cli core update-index
arduino-cli core install esp32:esp32
```

### Node A: Camera Unit Flashing Configuration
* **Target Board:** AI-Thinker ESP32-CAM (ESP32-D0WDQ6, 4MB Flash, 8MB PSRAM)
* **Flash Mode:** `dio` | **Flash Frequency:** `40m` | **Flash Size:** `4MB`
* **Baud Rate:** 460800 (use 115200 if the link is unstable)
* **Memory Map:**
  * `0x1000` : `KRISHI_DRISHTI_Camera.ino.bootloader.bin`
  * `0x8000` : `KRISHI_DRISHTI_Camera.ino.partitions.bin`
  * `0xe000` : `boot_app0.bin`
  * `0x10000`: `KRISHI_DRISHTI_Camera.ino.bin`

### Node B: Controller Unit Flashing Configuration
* **Target Board:** ESP32 DevKit V1 (30-pin)
* **Flash Mode:** `dio` | **Flash Frequency:** `40m` | **Flash Size:** `4MB`
* **Baud Rate:** 460800
* **Memory Map:**
  * `0x1000` : `KRISHI_DRISHTI_Controller.ino.bootloader.bin`
  * `0x8000` : `KRISHI_DRISHTI_Controller.ino.partitions.bin`
  * `0xe000` : `boot_app0.bin`
  * `0x10000`: `KRISHI_DRISHTI_Controller.ino.bin`

### 1-Click Flashing (Windows)
```bash
./Flash_ESP32_CAM.bat COM7
./Flash_ESP32_Controller.bat COM5
```

### Manual Compile & Flash (any platform)
```bash
arduino-cli compile --fqbn esp32:esp32:esp32cam firmware/KRISHI_DRISHTI_Camera
arduino-cli upload  --fqbn esp32:esp32:esp32cam -p /dev/ttyUSB0 firmware/KRISHI_DRISHTI_Camera

arduino-cli compile --fqbn esp32:esp32:esp32 firmware/KRISHI_DRISHTI_Controller
arduino-cli upload  --fqbn esp32:esp32:esp32 -p /dev/ttyUSB0 firmware/KRISHI_DRISHTI_Controller
```

---

## 3. Git Repository

* **Remote Origin:** `https://github.com/gautamkr0104/KRISHI-DRISHTI.git`
* **Primary Branch:** `main`
* **Status Check:**
  ```bash
  git status
  git remote -v
  ```

---

## 4. Release Pipeline

Precompiled firmware binaries and the SD card image are published under `releases/` and on the GitHub Releases page:
1. `KRISHI_DRISHTI_Camera_Firmware_v2.5.1.zip` (ESP32-CAM optical gateway firmware)
2. `KRISHI_DRISHTI_Controller_Firmware_v2.5.1.zip` (ESP32 Controller firmware)
3. `SD_CARD_KRISHI_DRISHTI_READY.zip` (plug-and-play offline FAT32 filesystem bundle)

`releases/FLASHING_MAP.md` documents the exact flash offsets and the SD card recovery procedure.
