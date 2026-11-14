# CLAUDE.md — Agent Guidelines for KRISHI-DRISHTI

## Project Context
- **Name:** KRISHI-DRISHTI (कृषि-दृष्टि)
- **Domain:** Offline edge-AI plant pathology screening wand (Tomato & Potato blights)
- **BOM Cost:** Strictly ₹1,480 (under ₹1,500)
- **CBSE Team:** Gautam Kumar & Abhinav Kumar (Class IX) | Mentor: Soni Kumari (PGT) | School: Udaan International School, Begusarai | Team ID: T26706431

## Toolchain Paths (Windows)
- **Python:** `C:\Users\DELL\krishi_pdf_env\Scripts\python.exe`
- **Pip:** `C:\Users\DELL\krishi_pdf_env\Scripts\pip.exe`
- **Esptool:** `C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\tools\esptool_py\5.3.1\esptool.exe`
- **G++ Compiler:** `C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\tools\esp-x32\2601\bin\xtensa-esp32-elf-g++.exe`
- **Git Origin:** `https://github.com/gautamkr0104/KRISHI-DRISHTI.git` (branch `main`)
- **Default Port:** `COM7` (115200 baud)

## Essential Commands
```powershell
# Run Hardware Validation Test
C:\Users\DELL\krishi_pdf_env\Scripts\python.exe tests/validate_hardware_field_captures.py

# Flash Camera
.\Flash_ESP32_CAM.bat COM7

# Flash Controller
.\Flash_ESP32_Controller.bat COM7

# Rebuild Docs & Release ZIPs
C:\Users\DELL\krishi_pdf_env\Scripts\python.exe scratch/build_and_sync_all.py
```

## Architecture & Pinouts
- **Camera Wand (Node A):** AI-Thinker ESP32-CAM, OV2640, 8 cm shroud, Flash LED on GPIO 4, MicroSD 1-bit SD_MMC, SoftAP @ `192.168.4.1`
- **Controller (Node B):** ESP32 DevKit V1, SSD1306 OLED (GPIO 21/22), DHT11 (GPIO 18), Multifunction Button on GPIO 27 (Tap=Next/Scan, Hold=Force Scan)
- **Edge AI (Node C):** MobileNetV3 Float16 (2.01 MB), input 128x128x3, Shannon Entropy gate ($H > 1.45$), Microclimate cross-gate (Late Blight spray suppressed when RH < 85%)

## Critical Rules
1. Never write files to `C:\Users\DELL\Downloads\` root. All submission deliverables belong in `uploading_documents/`.
2. Keep CBSE Student Project Report strictly between 600–1,200 words (current: 1,144 words, 2 pages).
3. Unit BOM is fixed at ₹1,480. Do not alter component pricing.
4. Always attribute both students: Gautam Kumar and Abhinav Kumar.
