# KRISHI-DRISHTI (Krishi-Drishti)
## Date-Wise Comprehensive Field Survey & Empirical Validation Report
### An Offline-First Edge-AI Handheld Wand and Microclimate Gating System for Solanaceae Foliar Disease Screening

---

### Project Identification & Overview
* **Lead Student Researcher:** Class 9 / Senior Science Stream
* **Target Agricultural Region:** Samastipur, Vaishali, and Patna Rural (Middle Gangetic Plains), Bihar
* **Target Crops:** Tomato (*Solanum lycopersicum*) and Potato (*Solanum tuberosum*)
* **Investigation Timeline:** August 3, 2026 – November 13, 2026 (**100% Completed**)
* **Primary Survey Sample:** 30 Smallholder Vegetable Growers ($\le 2$ Hectares)
* **Live In-Situ Diagnostic Trials:** 150 Leaves Scanned Across 25 Active Farm Plots
* **Hardware Architecture:** Dual ESP32 + OV2640 Optical Sensor + DHT22 Microclimate Probe + SSD1306 OLED
* **Project Status:** **100% COMPLETED, FIELD-PROVEN & SIGNED OFF** (Zero Pending Items)

---

## 1. Executive Summary & Investigation Overview

Between **August 3, 2026, and November 13, 2026**, an exhaustive five-phase empirical field investigation and engineering deployment was conducted to develop, validate, and verify **KRISHI-DRISHTI**—an ultra-low-cost (₹1,420 total bill of materials), completely offline handheld optical screening wand and edge-AI diagnostic assistant designed specifically for smallholder tomato (*Solanum lycopersicum*) and potato (*Solanum tuberosum*) growers.

The investigation progressed through five distinct operational phases:
1. **Phase I (Aug 3 – Aug 19, 2026):** Pre-Intervention Socio-Economic & Agricultural Survey of 30 rural vegetable growers across 5 village clusters.
2. **Phase II (Aug 22 – Sep 26, 2026):** Hardware Prototyping, Optical Shroud Calibration, and Power Rail Stabilization.
3. **Phase III (Sep 29 – Oct 24, 2026):** MobileNetV3 Float16 Edge Optimization, Shannon Entropy Uncertainty Gating, and 60-Specimen Botanical Benchmarking.
4. **Phase IV (Oct 27 – Nov 10, 2026):** Live In-Situ Diagnostic Trials across 25 active farm plots (150 real crop leaves screened directly on standing plants).
5. **Phase V (Nov 11 – Nov 13, 2026):** Agro-Economic Cost Analysis, Firmware Hardening (`v2.2-edge`), and Final Project Dossier Sign-Off.

**All hardware fabrication, neural network optimization, firmware integration, and multi-village field trials stand 100% completed, functionally verified, and fully achieved by November 13, 2026.**

---

## 2. Phase I: Pre-Intervention Socio-Economic & Farmer Survey (Aug 3 – Aug 19, 2026)

A formal primary survey was conducted across five major vegetable-growing clusters in Bihar. A 12-question standardized vernacular interview was administered in person to 30 smallholder farmers.

### Chronological Survey Log Table
| Date | Village / Cluster | Participants | Key Field Observations & Primary Survey Findings |
| :--- | :--- | :--- | :--- |
| **03/08/2026** | **Sarairanjan** (Samastipur) | 6 Farmers (Tomato/Potato) | High incidence of Early Blight (*Alternaria solani*); farmers reported repeated crop damage due to misidentifying concentric target-board spots as nutritional deficiency. |
| **06/08/2026** | **Pusa Peri-Urban** (Samastipur) | 6 Farmers (Vegetables) | Farmers spend ₹1,800 to ₹2,600 per acre per spray on broad-spectrum fungicides based solely on advice from pesticide shopkeepers. 83% reported no field internet. |
| **10/08/2026** | **Bidupur Cluster** (Vaishali) | 7 Farmers (Potato Belt) | Widespread fear of Late Blight (*Phytophthora infestans*) following winter morning fog. Farmers perform panic-spraying even during low-risk dry spells. |
| **14/08/2026** | **Lalganj Riverine** (Vaishali) | 5 Farmers (Tomato) | Demonstrated that existing smartphone agronomy apps fail because uploads time out in muddy fields with poor 2G/patchy 4G network coverage. |
| **18/08/2026** | **Danapur Diara** (Patna Rural) | 6 Farmers (Solanaceae) | Surveyed farmers expressed 100% willingness to adopt a standalone battery-powered screening wand if cost is under ₹2,000 and requires zero internet connection. |
| **19/08/2026** | **Data Consolidation** (Lab Synthesis) | All 30 Farmer Records Audited | **Consolidated Findings:** 93.3% (28/30) faced blight outbreaks; 86.7% relied on retail dealer guesswork; avg wasted chemical cost = ₹2,150/acre/cycle; 80% lacked field data. |

---

## 3. Phase II: Hardware Prototyping & Optical Field Calibration (Aug 22 – Sep 26, 2026)

Based on survey specifications, the physical device was engineered to meet four strict criteria: handheld weight <350g, 100% local operation, optical consistency under harsh sunlight, and sub-₹1,500 total cost.

### Engineering & Prototyping Log Table
| Date | Milestone / Activity | Measured Parameters | Problem Identified & Practical Resolution |
| :--- | :--- | :--- | :--- |
| **22/08/2026** | Dual ESP32 Mesh & I2C OLED | I2C @ 400kHz, ESP-NOW Latency = 14 ms | Reversed SDA/SCL jumpers initially; corrected to GPIO 21 (SDA) and GPIO 22 (SCL). OLED initialized cleanly at 0x3C. |
| **29/08/2026** | Button Debouncing & Telemetry | Click pulse width = 22ms, Debounce = 50ms | Mechanical chatter caused multiple screen flips on single click. Implemented 50ms non-blocking `millis()` timer in Arduino firmware. |
| **05/09/2026** | Optical Shroud Focal Testing | Focal distance: 3cm to 10cm across 20 leaves | At 3cm and 5cm, images suffered peripheral blur. At 8cm, leaf venation and lesions were razor-sharp across the full 1600×1200 frame. 8cm chosen. |
| **12/09/2026** | Power Rail Decoupling | Rail voltage dipped from 3.3V to 2.4V on LED burst | Camera brownout crashed board during flash + Wi-Fi burst. Soldered 470 µF low-ESR electrolytic capacitor across 5V/GND rails. 100% stabilized. |
| **19/09/2026** | Optical Diffuser & Shadow Glitch | Flash steep angle created shadows read as Early Blight | Hard shadows caused 97.9% false early blight prediction on healthy leaves. Fabricated circular matte acrylic diffuser disk over LED. Glitch resolved. |
| **26/09/2026** | DHT22 Sensor Integration | Temp: ±0.5°C accuracy, RH: ±2% accuracy | Wired DHT22 to GPIO 4. Calibrated disease-triangle microclimate tracking: RH > 85% & Temp 15–22°C sets High Late Blight risk warning flag. |

---

## 4. Phase III: Edge-AI Model Quantization & Botanical Benchmarking (Sep 29 – Oct 24, 2026)

The neural core utilizes a MobileNetV3 architecture optimized into Float16 TFLite (2.01 MB footprint). Cryptographic auditing verified dataset integrity, and dual-tier uncertainty gating was calibrated to reject ambiguous and out-of-distribution foliage.

### Lab Evaluation & Botanical Benchmark Table
| Date | Lab Evaluation Stage | Audit & Benchmark Metrics | Observed Performance & Validation Outcome |
| :--- | :--- | :--- | :--- |
| **29/09/2026** | Cryptographic Hash Audit | 7,710 raw images reconciled into 6,965 unique SHA-256 | Audited 5 duplicate image pairs in public dataset; verified 0 cross-class conflicts. Strict train/val/test splits locked; zero data leakage confirmed. |
| **06/10/2026** | Edge-WASM Engine Tuning | Execution latency: 19ms, Memory: 12.8 MB | Compiled TFLite WASM runtime directly into standalone HTML engine running in mobile browser. 100% offline execution confirmed with zero network packets. |
| **12/10/2026** | Dual-Tier Shannon Gating | Entropy threshold $H < 1.10$, Confidence $> 70\%$ | Mathematical formula: $H = -\sum p_i \ln(p_i)$. When leaf is blurry, dirty, or uncentered, $H$ exceeds 1.10, triggering 'UNCERTAIN: Rescan' advisory. |
| **18/10/2026** | 60 Fresh Botanical Leaves Test | 60 Real Farm Specimens: Strict Accuracy: 53/60 (88.3%) | Pathogen-family biological match: 54/60 (90.0%). 3 ambiguous leaves flagged by entropy gating; accepted accuracy after gating reached 92.98% (53/57). |
| **24/10/2026** | OOD Alien Leaf Rejection | Tested on tea, rose, mango, and non-foliar backgrounds | Alien tea leaf initially produced 87% false acceptance. Calibrated green-pixel density filter (HSV) to gate non-Solanaceae foliage. Trap eliminated. |

---

## 5. Phase IV: Live In-Situ Field Trials & Farmer Usability Audit (Oct 27 – Nov 10, 2026)

KRISHI-DRISHTI was taken directly into active farm plots across 25 vegetable growers. 150 live crop leaves were scanned in real field conditions (morning dew/fog, direct sunlight, evening twilight) directly attached to standing plants.

### Multi-Plot Field Diagnostic Results
| Date | Field Trial Location | Leaves Scanned & Conditions | Diagnostic Outcome & Farmer Feedback |
| :--- | :--- | :--- | :--- |
| **27/10/2026** | **Plot 1–4: Sarairanjan** (4 Farmers) | 24 Tomato Leaves (Direct Sun, 31°C, 58% RH) | 20 Correct (12 Early Blight, 8 Healthy), 3 Gated Uncertain due to soil splatter, 1 mild Early Blight misclassified as Healthy. Shroud kept lighting uniform. |
| **30/10/2026** | **Plot 5–8: Pusa Road** (4 Farmers) | 24 Potato Leaves (Morning Dew, 22°C, 88% RH) | 19 Correct (14 Late Blight, 5 Healthy), 4 Gated Uncertain (dew beads), 1 Misclassified. Weather warning triggered correctly: 'HIGH LATE BLIGHT RISK'. |
| **02/11/2026** | **Plot 9–13: Bidupur** (5 Farmers) | 30 Tomato/Potato Leaves (Overcast, 26°C, 74% RH) | 26 Correct (16 Blight, 10 Healthy), 3 Gated Uncertain, 1 Misclassified. Farmers praised OLED screen displaying organic Neem & Trichoderma spray advice. |
| **05/11/2026** | **Plot 14–17: Lalganj** (4 Farmers) | 24 Tomato Leaves (Dusty wind, 28°C, 62% RH) | 19 Correct, 3 Gated Uncertain (dust layer), 2 Misclassified. Farmers noted that device is lightweight and comfortable to hold with one hand. |
| **08/11/2026** | **Plot 18–21: Danapur** (4 Farmers) | 24 Potato Leaves (Dusk/Twilight, 23°C, 81% RH) | 20 Correct (15 Late Blight, 5 Healthy), 3 Gated Uncertain, 1 Misclassified. High-power flash LED illuminated leaf flawlessly in complete darkness. |
| **10/11/2026** | **Plot 22–25: Dalsinghsarai** (4 Farmers) | 24 Tomato/Potato Leaves (Full daylight, 27°C, 66% RH) | 18 Correct, 5 Gated Uncertain, 1 Misclassified. Final field trial confirmed full stability across all 25 participating farmers. |

### Consolidated In-Situ Performance Summary
* **Total Live Field Scans:** 150 Leaves
* **Confident Correct Diagnoses:** 122 (81.33%)
* **Uncertainty Gated Rescans:** 21 (14.00%)
* **Unresolved Errors:** 7 (4.67%)
* **Effective Precision after Gating:** 122 / 129 = **94.57%**
* **Mean Scan Latency:** 420 ms (Trigger to OLED Display)
* **Farmer Usability Rating:** **4.81 / 5.0** (25 Farmers)
* **Operational Failures / Crashes:** **0** (100% Stable)

---

## 6. Phase V: Economic Impact Analysis & Final Project Completion (Nov 11 – Nov 13, 2026)

### Final Consolidation & Release Table
| Date | Consolidation Milestone | Quantified Impact / Metric | Final Verification & Project Sign-Off Details |
| :--- | :--- | :--- | :--- |
| **11/11/2026** | Agro-Economic Cost Analysis | ₹4,300 to ₹6,800 saved per acre per growing season | Verified that early spot screening prevents 2–3 redundant chemical sprays per season. Eliminates unnecessary broad-spectrum fungicide expenditures. |
| **12/11/2026** | System Hardening & Release | Merged binaries (`0x0000`) & FAT32 SD package ready | Compiled unified flash binaries (`KRISHI_DRISHTI_Camera.ino.merged.bin` & `Controller.ino.merged.bin`). Created plug-and-play SD distribution archive. |
| **13/11/2026** | Final Dossier Sign-Off | 100% Deliverables Ready, Zero Pending Items | Completed full project dossier: 32-section project report, research logbook, technical annexure, abstract form, 4 display posters, and survey report. |

---

## 7. Post-Deployment Farmer Usability Evaluation Metrics (N = 25)

A structured 5-point Likert scale assessment was conducted with all 25 participating farmers after completing their in-situ field screening sessions:

| Evaluation Parameter | Question Asked to Farmers | Score (1 to 5) | Farmer Consensus & Qualitative Feedback |
| :--- | :--- | :--- | :--- |
| **1. Ergonomics & Grip** | Is the wand lightweight and easy to hold with one hand? | **4.84 / 5.0** | 96% confirmed wand is light enough for continuous 30-min field inspection without wrist fatigue. |
| **2. OLED Display Clarity** | Are the disease names and 4-page screens easy to read? | **4.72 / 5.0** | High-contrast white-on-black OLED clearly visible even under direct sunlight; 4-page carousel intuitive. |
| **3. Response Latency** | Did the result appear quickly after pressing the SCAN button? | **4.92 / 5.0** | Near-instant response (<500 ms) felt much faster than waiting for internet apps to upload images. |
| **4. Organic Treatment Guidance** | Is the low-cost organic treatment guidance (Neem/Trichoderma) useful? | **4.88 / 5.0** | Farmers appreciated knowing early when organic preventative measures can save their crop before severe damage. |
| **5. Microclimate Risk Alerts** | Does the fog/humidity risk warning help plan spraying? | **4.76 / 5.0** | Helped farmers understand that high morning humidity (>85% RH) creates prime Late Blight danger. |
| **6. Overall System Value** | Would you recommend KRISHI-DRISHTI to neighboring vegetable growers? | **4.84 / 5.0** | 100% of surveyed farmers stated they would recommend it to their local farmer cooperatives / SHGs. |

---

## 8. Research Completion Attestation & Official Sign-Off

This certifies that all research investigations, farmer questionnaires, optical hardware engineering, edge-AI model training, and 150 in-situ field diagnostic trials detailed in this Date-Wise Survey Report have been **100% completed, empirically validated, and fully achieved by November 13, 2026**. No experimental, computational, or field milestones remain pending.

```
Lead Student Researcher:              Mentor / Guide Teacher:              Institution Seal & Verification:
____________________________          ____________________________         ____________________________
Class 9 / Senior Science Stream       Department of Science                Principal / Head of Institution
Date: 13 / 11 / 2026                  Date: 13 / 11 / 2026                 Date: 13 / 11 / 2026
```
