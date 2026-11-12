# TOOLCHAINS.md — Complete Local Toolchain & Compiler Manual

This document provides exact paths, environment setups, compiler options, and build commands for all subsystems of KRISHI-DRISHTI.

---

## 1. Python Environment

### Executable Paths
* **Python Binary:** `C:\Users\DELL\krishi_pdf_env\Scripts\python.exe`
* **Pip Binary:** `C:\Users\DELL\krishi_pdf_env\Scripts\pip.exe`
* **Virtual Environment Directory:** `C:\Users\DELL\krishi_pdf_env`

### Core Libraries Installed
* `ai-edge-litert` (TensorFlow Lite XNNPACK delegate CPU inference)
* `numpy` (2.4.6)
* `Pillow` (13.0.0)
* `pymupdf` / `fitz` (2.1)
* `python-docx` (1.2.0)
* `python-pptx` (1.0.2)
* `reportlab` (5.1.0)
* `pyserial` (3.5)

### Running Python Scripts
Always invoke via the full environment binary or ensure `krishi_pdf_env` is activated:
```powershell
# Run hardware validation harness
C:\Users\DELL\krishi_pdf_env\Scripts\python.exe tests/validate_hardware_field_captures.py

# Run benchmark evaluation
C:\Users\DELL\krishi_pdf_env\Scripts\python.exe ai_engine/export_and_evaluate.py
```

---

## 2. Embedded ESP32 & Arduino Toolchain

### Compiler & Flashing Binaries
* **esptool.exe:**  
  `C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\tools\esptool_py\5.3.1\esptool.exe`
* **Xtensa C++ Cross-Compiler (`xtensa-esp32-elf-g++.exe`):**  
  `C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\tools\esp-x32\2601\bin\xtensa-esp32-elf-g++.exe`
* **Arduino15 Core Directory:**  
  `C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\hardware\esp32\3.0.7`

### Node A: Camera Wand Flashing Configuration
* **Target Board:** AI-Thinker ESP32-CAM (ESP32-D0WDQ6, 4MB Flash, 8MB PSRAM)
* **Flash Mode:** `dio` | **Flash Frequency:** `40m` | **Flash Size:** `4MB`
* **Default Port:** `COM7` @ `115200 baud`
* **Binary Locations:** `firmware/KRISHI_DRISHTI_Camera/build/esp32.esp32.esp32cam/`
* **Memory Map:**
  * `0x1000` : `KRISHI_DRISHTI_Camera.ino.bootloader.bin`
  * `0x8000` : `KRISHI_DRISHTI_Camera.ino.partitions.bin`
  * `0xe000` : `boot_app0.bin`
  * `0x10000`: `KRISHI_DRISHTI_Camera.ino.bin`
* **1-Click Command:**
  ```powershell
  .\Flash_ESP32_CAM.bat COM7
  ```

### Node B: Controller Wand Flashing Configuration
* **Target Board:** ESP32 DevKit V1 (30-pin)
* **Flash Mode:** `dio` | **Flash Frequency:** `40m` | **Flash Size:** `4MB`
* **Default Port:** `COM7` @ `115200 baud`
* **Binary Locations:** `firmware/KRISHI_DRISHTI_Controller/build/esp32.esp32.esp32/`
* **Memory Map:**
  * `0x1000` : `KRISHI_DRISHTI_Controller.ino.bootloader.bin`
  * `0x8000` : `KRISHI_DRISHTI_Controller.ino.partitions.bin`
  * `0xe000` : `boot_app0.bin`
  * `0x10000`: `KRISHI_DRISHTI_Controller.ino.bin`
* **1-Click Command:**
  ```powershell
  .\Flash_ESP32_Controller.bat COM7
  ```

---

## 3. Git Repository Architecture

* **Working Copy Root:** `C:\Users\DELL\Downloads\KRISHI-DRISHTI`
* **Remote Origin:** `https://github.com/gautamkr0104/KRISHI-DRISHTI.git`
* **Primary Branch:** `main`
* **Git Status Check:**
  ```powershell
  git status
  git remote -v
  ```

---

## 4. Release & Document Compilation Pipeline

To rebuild all exhibition documents, PDFs, DOCX, presentation decks, and both distribution ZIPs:
```powershell
C:\Users\DELL\krishi_pdf_env\Scripts\python.exe scratch/build_and_sync_all.py
```
This generates:
1. `uploading_documents/KRISHI-DRISHTI-Final-v3.0.zip` (Full 68MB master distribution)
2. `uploading_documents/KRISHI-DRISHTI-Audit-Docs-and-Code.zip` (Lightweight 15.8MB AI auditor package)
3. Synchronizes all submission PDFs into `uploading_documents/` and `docs/`.
