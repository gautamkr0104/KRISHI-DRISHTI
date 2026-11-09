# KRISHI-DRISHTI (कृषि-दृष्टि)
> **Offline-First Edge-AI Handheld Wand and Microclimate Telemetry System for Predictive Agricultural Plant Health Screening**

[![License: Source Available](https://img.shields.io/badge/License-Source--Available-blue.svg)](LICENSE)
[![Platform: ESP32](https://img.shields.io/badge/Platform-ESP32%20%7C%20FreeRTOS-blue.svg)](https://www.espressif.com/)
[![Inference: Offline TFLite](https://img.shields.io/badge/AI-Offline%20TFLite%20%7C%20MobileNetV3-orange.svg)](https://www.tensorflow.org/lite)
[![Architecture: Edge Mesh](https://img.shields.io/badge/Mesh-Zero--Cloud%20SoftAP-success.svg)](#)

---

## 🌟 Overview & System Architecture

Over **35% of potato and tomato crops across India are destroyed annually by foliar blights** like Late Blight (*Phytophthora infestans*, an oomycete water mold) and Early Blight (*Alternaria solani*, an ascomycete fungus). Smallholder and marginal farmers often lack access to expensive laboratory diagnostic equipment (₹25,000+) or reliable cloud connectivity in rural fields with poor cellular reception.

**KRISHI-DRISHTI** is an ultra-low-cost (< ₹1,500 INR / $18 total), **100% offline-first agritech screening system** designed for rural field environments.

Instead of relying on cloud APIs or expensive 5G connectivity, KRISHI-DRISHTI uses a **handheld wireless telemetry wand**, an **ESP32-CAM optical capture unit**, and an ordinary budget smartphone (e.g. Samsung Galaxy A03) acting as an **invisible, headless edge AI co-processor** operating over a dedicated local Wi-Fi mesh.

```
+--------------------------------------------------------------------------+
|                        KRISHI-DRISHTI SYSTEM TRIAD                       |
|                                                                          |
|  [ Handheld Wand ]      ==== Wi-Fi ====>    [ AI-Thinker ESP32-CAM ]     |
|  ESP32 DevKit V1                            5MP OV5640 Sensor + Flash    |
|  SSD1306 OLED Display                       8GB MicroSD Storage (SD_MMC) |
|  DHT11 Canopy Sensor                        SoftAP: 192.168.4.1          |
|  2 Active-Low Buttons                                 ||                 |
|         ^                                             || (Local Wi-Fi)   |
|         ||                                            \/                 |
|         +=========== Diagnosis Payload ========= [ Pocket AI Engine ]   |
|                      synced in < 15 ms           Samsung Galaxy A03      |
|                                                  MobileNetV3 Edge Model  |
|                                                  100% Offline (No Data)  |
+--------------------------------------------------------------------------+
```

---

## 🌿 The Core Scientific Principle: The Plant Disease Triangle

In plant pathology, diseases do **not** occur simply because a pathogen exists. They only manifest when three conditions coincide:

$$\mathbf{\text{Disease Outbreak}} = \mathbf{\text{Susceptible Host}} + \mathbf{\text{Virulent Pathogen}} + \mathbf{\text{Favorable Microclimate}}$$

```mermaid
flowchart TD
    Host["1. Susceptible Host (Tomato/Potato Plant)"] --- Env["2. Favorable Environment (High Canopy Humidity + Cool Temps)"]
    Env --- Pathogen["3. Pathogen (Phytophthora oomycete spores)"]
    Pathogen --- Host
    Host & Env & Pathogen --> Disease["DISEASE OUTBREAK!\n(Late Blight Spores Germinate)"]
```

### Proactive Microclimate Correlation vs. Reactive Classification:
* **Reactive Classification:** Evaluates leaves only after severe necrosis, chlorosis, and irreversible tissue decay have occurred.
* **KRISHI-DRISHTI Predictive Triage:** The handheld wand integrates a **DHT11 digital microclimate sensor** on GPIO 18. Late Blight spores require **Relative Humidity $> 85\%$** between **$18^\circ\text{C} - 24.5^\circ\text{C}$** for $> 6$ hours to germinate. KRISHI-DRISHTI continuously monitors this canopy microclimate envelope to advise the farmer **BEFORE** visual spore damage spreads across the field.

---

## 📂 Repository Structure

```text
KRISHI-DRISHTI/
├── LICENSE                         # Source-Available Non-Commercial License
├── README.md                       # Master Project Architecture & Guide
├── .gitignore                      # Git ignore rules for Arduino & Python
├── firmware/
│   ├── KRISHI_DRISHTI_Camera/
│   │   └── KRISHI_DRISHTI_Camera.ino       # Camera unit firmware v2.2 (Write Verification + SDMMC Static Serving)
│   └── KRISHI_DRISHTI_Controller/
│       └── KRISHI_DRISHTI_Controller.ino   # Controller wand firmware v2.2 (Real Wi-Fi + OLED + DHT11)
├── ai_engine/
│   ├── krishi_ai_server.html       # Headless offline AI daemon for Android (Bundled WASM TFLite)
│   ├── krishi_ai_daemon.py         # Headless Python AI daemon for Termux/Android/PC
│   ├── krishi_drishti_model.tflite # Optimized MobileNetV3 Float16 model (2.01 MB, 10.54 ms latency)
│   ├── model_evaluation_report.json# Full empirical metrics, confusion matrix & PlantDoc evaluation
│   ├── train_model.py              # Two-stage MobileNetV3 training pipeline
│   ├── export_and_evaluate.py      # TFLite quantization and evaluation script
│   ├── labels.json                 # Strict 1:1 disease taxonomy, organic & chemical dosages
│   └── vendor/                     # Bundled 100% offline JS & WASM TFLite browser runtimes
├── tests/
│   └── test_ai_pipeline.py         # Automated hardware-independent test suite (Unit & Mock REST cycle)
└── docs/
    ├── System_Architecture_Report.md# In-depth architectural & pathological specification
    └── Wiring_Schematic_Pinout.md  # Detailed circuit schematics and pin connection tables
```

---

## 💰 Bill of Materials (BOM) — Under ₹1,500 Total

| Component | Purpose | Unit Cost (INR) | Sourcing |
| :--- | :--- | :--- | :--- |
| **ESP32-S CAM Board** | 5MP camera + 4MB PSRAM | ₹675.00 | Standard Electronics Distributor |
| **ESP32-CAM-MB Programmer** | USB programming shield (No jumper wires) | ₹92.00 | Standard Electronics Distributor |
| **ESP32 DevKit V1** | Handheld wand controller core | ~₹350.00 | Standard Electronics Distributor |
| **SSD1306 0.96" OLED** | 128×64 I2C diagnostic display | ~₹150.00 | Local Electronics |
| **DHT11 Sensor Module** | Canopy temperature & relative humidity (GPIO 18) | ₹57.00 | Standard Electronics Distributor |
| **MicroSD Card (8GB)** | Local storage for UXGA leaf scans | ~₹180.00 | Standard Class 10 card |
| **Pushbuttons (x2)** | `[SCAN]` (GPIO 27) and `[NEXT]` (GPIO 26) | ~₹10.00 | Local Electronics |
| **Total Hardware Cost** | **Complete System Triad** | **~₹1,514 INR ($18 USD)** | **Ultra-Low Cost Compliant** |

---

## 📊 Genuine Empirical AI Metrics

Trained on the **New Plant Diseases Dataset (Augmented 87K, Solanaceae Partition)** with 11,399 training and 2,850 validation images, and benchmarked on independent real-world field photographs from **PlantDoc**:

| Metric | Measured Value | Practical Significance |
| :--- | :--- | :--- |
| **Training Accuracy** | **91.80%** | High feature convergence on diverse foliar lesions |
| **Validation Set Accuracy** | **88.74%** | Evaluated on 2,850 independent test samples |
| **Validation Macro F1** | **0.8863** | Balanced precision and recall across all 6 classes |
| **Potato Early Blight F1** | **0.9665** | Precision: 98.09%, Recall: 95.26% |
| **Potato Healthy Tissue F1** | **0.9824** | Precision: 98.46%, Recall: 98.03% |
| **Tomato Healthy Tissue F1** | **0.9531** | Precision: 91.57%, Recall: 99.38% |
| **Model Size (TFLite)** | **2.01 MB** | Fits comfortably in low-RAM smartphone memory |
| **On-Device Inference Time** | **10.54 ms** | Real-time classification on smartphone CPU |
| **PlantDoc Field Benchmark** | **34.91%** | Evaluated on unaugmented outdoor images with complex backgrounds |
| **Entropy Rejection Threshold** | **$H > 1.45$ nats** | Rejects non-foliar objects, bare soil, and ambiguous leaves |

---

## 🧪 Automated Testing & Verification

Run the automated hardware-independent test suite directly on any PC:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Verified test coverage:
1. `test_labels_file_exists_and_matches_strict_classes`: Verifies strict 1:1 index alignment with model outputs.
2. `test_model_artifact_and_report_integrity`: Verifies model file size and report accuracy figures.
3. `test_non_foliar_rejection`: Confirms lens cap (black) and background glare (white) rejection.
4. `test_foliar_acceptance_on_real_samples`: Confirms real leaf images pass foliar plausibility.
5. `test_shannon_entropy_gating`: Verifies Shannon entropy mathematical bounds.
6. `test_full_wand_phone_oled_telemetry_cycle`: Simulates complete end-to-end HTTP REST loop.

---

## 🚀 Hardware Upload & Flashing Guide

### Step 1: Flash the Controller Wand (ESP32 DevKit V1)
1. Connect ESP32 DevKit V1 via Micro-USB.
2. In Arduino IDE:
   - Select Board: **DOIT ESP32 DEVKIT V1**.
   - Pin Connections:
     - SSD1306 OLED: `SDA -> GPIO 21`, `SCL -> GPIO 22`, `VCC -> 3V3`, `GND -> GND`
     - DHT11 Sensor: `DATA -> GPIO 18`, `VCC -> 3V3`, `GND -> GND`
     - Buttons: `SCAN -> GPIO 27 to GND`, `NEXT -> GPIO 26 to GND` (Active-Low internal pull-up)
3. Open [`firmware/KRISHI_DRISHTI_Controller/KRISHI_DRISHTI_Controller.ino`](firmware/KRISHI_DRISHTI_Controller/KRISHI_DRISHTI_Controller.ino) and click **Upload**.

### Step 2: Flash the Camera Unit (AI-Thinker ESP32-CAM)
1. Snap the AI-Thinker ESP32-CAM onto the **ESP32-CAM-MB Programmer Shield**.
2. Connect via USB.
3. In Arduino IDE:
   - Select Board: **AI Thinker ESP32-CAM**.
   - Partition Scheme: **Huge APP (3MB No OTA / 1MB SPIFFS)**.
   - Flash Frequency: **40MHz**, Flash Mode: **DIO**.
4. Open [`firmware/KRISHI_DRISHTI_Camera/KRISHI_DRISHTI_Camera.ino`](firmware/KRISHI_DRISHTI_Camera/KRISHI_DRISHTI_Camera.ino) and click **Upload**.
5. Insert the prepared 8GB MicroSD card (FAT32 formatted) into the card slot.

### Step 3: Run the Edge AI Engine
1. Connect your Android phone to the Wi-Fi network: **`KRISHI-DRISHTI`** (Password: `12345678`).
2. Open Chrome on the phone and navigate to `http://192.168.4.1/` (served directly from ESP32-CAM flash and SDMMC) or open [`ai_engine/krishi_ai_server.html`](ai_engine/krishi_ai_server.html) locally.
3. Tap **`START AI SERVER`** and place the phone in your pocket.
4. Aim the wand at a leaf and press the **`[SCAN]`** button!
5. Within seconds, the diagnosis and treatment carousel appears on the wand's OLED screen.

---

## 📜 License & Intellectual Property

This project is licensed under the **Source-Available Non-Commercial License**. See [`LICENSE`](LICENSE) for terms.  
Source code, schematics, and model weights are made available solely for personal inspection, educational evaluation, and non-commercial research. Commercial manufacturing, sublicensing, redistribution, and third-party patent filing without explicit written authorization are strictly prohibited.

**Author & Systems Designer:** Gautam Kumar  
**Copyright (c) 2026 Gautam Kumar. All rights reserved.**
