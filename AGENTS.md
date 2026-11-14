# AGENTS.md — Agentic AI Development Guide for KRISHI-DRISHTI

> **Welcome Agent!** This document is your primary onboarding reference. If you are an autonomous AI coding assistant (Antigravity, Cursor, Claude Code, Windsurf, Devin, GitHub Copilot, Roo Code, etc.) opened inside this repository, **you can start development immediately**. Everything you need is self-contained in this workspace.

---

## 1. Project Overview & Identity

* **Project Name:** **KRISHI-DRISHTI (कृषि-दृष्टि)**
* **Version:** `2.3.0` (Production Hardened)
* **Domain:** Ultra-Low-Cost, Completely Offline Foliar Plant Pathology Screening Wand for Smallholder Farmers
* **Target Crops:** Tomato (*Solanum lycopersicum*) and Potato (*Solanum tuberosum*)
* **Diseases Covered:** Early Blight (*Alternaria solani*), Late Blight (*Phytophthora infestans*), Asymptomatic Healthy
* **Authoritative Unit BOM Cost:** Strictly **₹1,480** (under ₹1,500 cap)
* **CBSE Science Exhibition Team:**
  * **Team ID:** `T26706431`
  * **Sub-Theme:** `Artificial Intelligence (AI) for Better Life`
  * **Students:** Gautam Kumar & Abhinav Kumar (Class IX)
  * **Mentor Teacher:** Soni Kumari (PGT Science, Mobile: `9102812661`, Email: `ksoni251090@gmail.com`)
  * **Institution:** Udaan International School, Begusarai, Bihar
  * **Date of Record:** `12 November 2026`

---

## 2. Local Environment, Compilers & Toolchains

All toolchains and compilers are pre-installed on this host machine. Use these exact paths:

### Python Virtual Environment
* **Python Executable:** `C:\Users\DELL\krishi_pdf_env\Scripts\python.exe`
* **Pip Executable:** `C:\Users\DELL\krishi_pdf_env\Scripts\pip.exe`
* **Installed Packages:**
  * `ai-edge-litert` (TensorFlow Lite runtime)
  * `numpy` (2.4.6)
  * `Pillow` (13.0.0)
  * `pymupdf` / `fitz` (2.1)
  * `python-docx` (1.2.0)
  * `python-pptx` (1.0.2)
  * `reportlab` (5.1.0)
  * `pyserial` (3.5)

### Arduino & ESP32 Toolchain
* **Flash Tool (esptool):** `C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\tools\esptool_py\5.3.1\esptool.exe`
* **C++ Cross-Compiler:** `C:\Users\DELL\AppData\Local\Arduino15\packages\esp32\tools\esp-x32\2601\bin\xtensa-esp32-elf-g++.exe`
* **Arduino15 Data Root:** `C:\Users\DELL\AppData\Local\Arduino15`
* **Default Target Hardware Port:** `COM7` (Serial 115200 baud)

### Git Repository Configuration
* **Local Root:** `C:\Users\DELL\Downloads\KRISHI-DRISHTI`
* **Remote Origin:** `https://github.com/gautamkr0104/KRISHI-DRISHTI.git`
* **Active Branch:** `main`

---

## 3. Hardware Architecture & Pinout Map

KRISHI-DRISHTI operates as a distributed 3-node edge architecture:

```
[ Node A: ESP32-CAM Wand ]  <--- SoftAP Wi-Fi (192.168.4.1) --->  [ Node C: Smartphone Co-Processor ]
  - OV2640/OV5640 Sensor                                            - Offline WebAssembly / TFLite
  - 8 cm Optical Shroud                                            - Float16 MobileNetV3 (2.01 MB)
  - MicroSD Logging                                                - Shannon Entropy & Microclimate Gate
         ^
         | Physical Alignment Wand
         v
[ Node B: ESP32 Dev Controller ]
  - SSD1306 OLED (I2C)
  - DHT11 Temp/Humidity
  - Multifunction SCAN/PAGE Button (GPIO 27)
```

### Node A: Camera Wand (`firmware/KRISHI_DRISHTI_Camera/`)
* **Core:** AI-Thinker ESP32-CAM
* **Image Sensor:** OV2640 installed (OV5640 auto-detect supported in code)
* **Optical Shroud:** 8 cm cylindrical shroud with matte acrylic light diffuser
* **Flash LED:** `GPIO 4`
* **MicroSD Bus:** 1-bit `SD_MMC` DMA mode (`GPIO 2`, `GPIO 14`, `GPIO 15`, `GPIO 13`)
* **Network:** Local SoftAP `SSID: KRISHI-DRISHTI` serving HTTP gateway at `http://192.168.4.1`

### Node B: Handheld Controller (`firmware/KRISHI_DRISHTI_Controller/`)
* **Core:** ESP32 DevKit V1 (30-pin)
* **OLED Display (SSD1306 0.96"):** `I2C SDA: GPIO 21`, `I2C SCL: GPIO 22`
* **Microclimate Sensor (DHT11):** `DATA: GPIO 18` (powered from 3.3V)
* **Hardware Pushbuttons:**
  * `SCAN Button`: `GPIO 27` (Active LOW with internal pull-up)
  * `NEXT/PAGE Button`: `GPIO 26` (Active LOW with internal pull-up)

### Node C: Edge AI Co-Processor (`ai_engine/`)
* **Architecture:** MobileNetV3-Small INT8 / Float16 Quantized (`2.03 MB`)
* **Input Tensor:** `[1, 128, 128, 3]` normalized Float32
* **Execution:** 100% offline browser WebAssembly via SoftAP (`krishi_ai_server.html`) or headless Python daemon (`krishi_ai_daemon.py`)
* **Diagnostic Gating Interlocks:**
  * **Shannon Entropy Gate:** $H > 1.45$ flags scan as `UNCERTAIN`
  * **Decision Margin Gate:** Top-1 minus Top-2 $< 12\%$ flags ambiguous species
  * **Foliar Content Gate:** Foliar ratio $< 12\%$ or dark peripheral void $> 45\%$ rejects non-leaf frames
  * **Microclimate Interlock:** Late Blight (*Phytophthora infestans*) chemical recommendations are suppressed when DHT11 Relative Humidity $< 85\%$ (favorable sporulation window: RH $\ge 85\%$, temp $15\text{--}22^\circ\text{C}$)

---

## 4. Directory & Component Locator

Everything needed for the project is located in this directory:

```
KRISHI-DRISHTI/
├── AGENTS.md                          # <-- THIS FILE (Onboarding guide for AI agents)
├── CLAUDE.md                          # Claude Code configuration
├── .cursorrules                       # Cursor & Windsurf IDE rules
├── ENVIRONMENT.json                   # Machine-readable toolchain & hardware specs
├── TOOLCHAINS.md                      # Detailed toolchain and build reference
├── Run_Tests.bat                      # 1-Click test execution harness
├── Flash_ESP32_CAM.bat                # 1-Click flasher for ESP32-CAM (COM7)
├── Flash_ESP32_Controller.bat         # 1-Click flasher for ESP32 Dev Controller (COM7)
├── Start_AI_Server.bat                # 1-Click local HTTP server for offline AI engine
├── Build_All_Docs.bat                 # 1-Click document compiler & release packager
│
├── firmware/                          # C++ Embedded Firmware
│   ├── KRISHI_DRISHTI_Camera/         # ESP32-CAM firmware (.ino + compiled binaries)
│   └── KRISHI_DRISHTI_Controller/     # ESP32 Dev Controller firmware (.ino + MicroclimateTracker)
│
├── ai_engine/                         # Edge AI Co-Processor
│   ├── krishi_drishti_model.tflite    # Quantized MobileNetV3 Float16 weights (2.01 MB)
│   ├── labels.json                    # 6-class agronomic metadata and ICAR protocols
│   ├── krishi_ai_server.html          # Offline WebAssembly browser inference UI
│   ├── krishi_ai_daemon.py            # Headless Python edge daemon for Termux/Edge
│   ├── train_model.py                 # Training script with hash-blacklist exclusion
│   ├── export_and_evaluate.py         # 460-image benchmark evaluator
│   ├── TRAINING_RUN_MANIFEST.json     # 7,710 records manifest (6,965 unique)
│   └── sample_leaves/                 # Canonical reference test leaves
│
├── tests/                             # Hardware & Software Test Suites
│   ├── validate_hardware_field_captures.py  # Hardware-in-the-loop validation harness
│   ├── hardware_field_captures/       # 10 authentic camera captures & manifest
│   ├── hardware_field_validation_report.json # Empirical failure mode validation report
│   └── ad_hoc_testing/                # User field test samples (early blight webp, etc.)
│
├── uploading_documents/               # Final Submission Deliverables (Keep synced!)
│   ├── KRISHI_DRISHTI_CBSE_STUDENT_PROJECT_REPORT_FILLED.pdf  (1,144 words, 2 pages)
│   ├── KRISHI_DRISHTI_CBSE_STUDENT_PROJECT_REPORT_FILLED.docx
│   ├── mentor_projreport.pdf          # Official CBSE Mentor Recommendation Form
│   ├── KRISHI_DRISHTI_Exhibition_Presentation.pptx (Both students, aligned figures)
│   ├── KRISHI_DRISHTI_Field_Survey_Report.pdf (30-farmer empirical survey)
│   ├── KRISHI_DRISHTI_Project_Evidence_Dossier.pdf (Wiring schematic & BOM)
│   ├── KRISHI-DRISHTI-Audit-Docs-and-Code.zip (Lightweight <20MB AI audit package)
│   └── KRISHI-DRISHTI-Final-v3.0.zip  (Full 68MB master distribution archive)
│
├── docs/                              # Markdown Technical Documentation
│   ├── Field_Survey_and_Farmer_Validation_Report.md
│   └── Wiring_Schematic_Pinout.md  # Detailed circuit schematics and pin connection tables
│
├── releases/                          # Pre-compiled binaries & SD-Card Package
│   └── SD_CARD_KRISHI_DRISHTI_READY.zip
│
└── templates/                         # Original CBSE Exhibition Templates
```

---

## 5. Development Workflow & Commands

### Running Hardware & Model Tests
Always run with the dedicated Python virtualenv:
```powershell
C:\Users\DELL\krishi_pdf_env\Scripts\python.exe tests/validate_hardware_field_captures.py
```

### Flashing Hardware Boards
Attach the board to FTDI / USB and run:
```powershell
# Flash Camera Wand (default COM7, override with port arg)
.\Flash_ESP32_CAM.bat COM7

# Flash Handheld Controller (default COM7, override with port arg - e.g. COM5)
.\Flash_ESP32_Controller.bat COM5
```

### Launching Local AI Server
```powershell
.\Start_AI_Server.bat
# Browse to: http://localhost:8000/krishi_ai_server.html
```

### Rebuilding All Submission Documents & ZIP Archives
```powershell
C:\Users\DELL\krishi_pdf_env\Scripts\python.exe scratch/build_and_sync_all.py
```

---

## 6. Golden Rules for Autonomous Agents

1. **Keep BOM at ₹1,480:** Never change or fluctuate the unit cost. The audited BOM is ₹1,480 (under ₹1,500).
2. **Student Report Word Count:** The CBSE Student Project Report must remain strictly between **600 and 1,200 words** (current: 1,144 words across 2 pages).
3. **No Scattered Files:** Never write outputs to `C:\Users\DELL\Downloads` root. All deliverables belong strictly inside `uploading_documents/`.
4. **Authentic Data Only:** Never fabricate agronomic stories or claim unverified trials. All hardware findings (including the real optical shadow failure mode under unshielded torchlight) are documented with exact empirical telemetry.
5. **Team Attribution:** Always represent both students: **Gautam Kumar & Abhinav Kumar (Class IX)**, and mentor **Soni Kumari (PGT Science)**.
