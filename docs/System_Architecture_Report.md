# KRISHI-DRISHTI: Project Synopsis & Science Report

**Title:** KRISHI-DRISHTI: Low-Cost Edge-AI Handheld Wand and Microclimate Telemetry for Predictive Plant Health Screening  
**Domain:** Edge Agritech & Computational Plant Pathology  
**Focus:** Offline-First Foliar Disease Screening & Microclimate Risk Modeling  
**Target Platform:** Ultra-Low-Cost Microcontrollers (ESP32) & Budget Smartphones  
**Author / Maintainer:** Gautam Kumar  
**License:** Source-Available Non-Commercial License

---

## 1. Abstract
Foliar plant blights—specifically Late Blight (*Phytophthora infestans*, an oomycete water mold) and Early Blight (*Alternaria solani*, a true ascomycete fungus)—cause up to 35% yield destruction in Indian potato and tomato cultivation annually. Marginal and smallholder farmers (< 2 hectares) cannot access expensive laboratory diagnostic kits (₹15,000–₹30,000) or high-speed cellular cloud apps in rural areas with zero connectivity.

**KRISHI-DRISHTI** is a low-cost (< ₹1,500 INR / $18 USD), 100% offline-first agritech system comprising:
1. **A Camera Unit:** An AI-Thinker ESP32-CAM with an OV5640 5MP sensor, 8GB MicroSD (SD_MMC 1-bit mode), and high-intensity LED flash.
2. **A Handheld Controller Wand:** An ESP32 DevKit V1 with an SSD1306 OLED display, active-low multifunction button (GPIO 27), and canopy microclimate telemetry (DHT11 on GPIO 18).
3. **A Universal Headless Edge AI Co-Processor:** Any standard smartphone (Android or iOS / iPhone / any manufacturer) or pocket tablet running an offline MobileNetV3 WebAssembly neural engine in the farmer's pocket without cell service, internet data, or app store installation. (Empirically benchmarked on low-end hardware down to an entry-level Samsung Galaxy A03 / Cortex-A55).

*Scientific Scope:* The device provides immediate, non-invasive **field screening indications and agronomic triage**, intended to guide timely preventative action rather than replace destructive laboratory PCR/ELISA confirmation.

---

## 2. Scientific Principle: The Plant Disease Triangle
Plant pathology dictates that infectious plant disease cannot develop purely because an inoculum is present. It mandates three concurrent, interdependent factors:
$$\text{Disease Outbreak} = \text{Susceptible Host} + \text{Virulent Pathogen} + \text{Favorable Microclimate}$$

Commercial smartphone apps only perform **reactive** classification after leaves have already turned brown, necrotic, and infectious. KRISHI-DRISHTI correlates **visual foliar classification** with **canopy microclimate telemetry**:
* **Late Blight Outbreak Risk Envelope:** Sustained canopy Relative Humidity $> 85\%$ combined with temperatures between $18^\circ\text{C} - 24.5^\circ\text{C}$ for $> 6$ hours.
* **Early Blight Risk Envelope:** Warm canopy temperatures ($24^\circ\text{C} - 29^\circ\text{C}$) paired with alternating wet-dry dew cycles.
* **Microclimate Risk Advisory vs. Proof of Absence:** Classic epidemiological forecasting models (such as Wallin and Hyre) require multi-day temperature-humidity leaf wetness duration curves. KRISHI-DRISHTI's canopy DHT11 sensor provides a **simplified environmental risk advisory** based on microclimate conduciveness. An instantaneous reading of Relative Humidity < 85% does not biologically prove that pathogens or spores are absent; rather, it acts as a conservative agronomic safety advisory to suppress unneeded, high-cost chemical fungicide applications when environmental conditions do not favor active sporulation.

---

## 3. System Architecture & Telemetry Pipeline

```mermaid
flowchart TD
    Farmer["Farmer holds KRISHI-DRISHTI Wand"] -->|Presses [SCAN] Button (GPIO 27)| Wand["ESP32 DevKit V1 (Controller)"]
    Wand -->|Wi-Fi HTTP GET /api/capture| Cam["AI-Thinker ESP32-CAM\n(OV5640 5MP + GPIO 4 Flash)"]
    Cam -->|Saves High-Res UXGA JPEG to SDMMC| SD["8GB MicroSD Card\n(Write Verified >= 512B)"]
    Cam -->|Broadcasts New scan_id| Phone["Any Smartphone (Android / iOS in pocket)\nHeadless Offline Neural Server"]
    Phone -->|Pulls Image via SoftAP & Runs MobileNetV3| AI["TFLite Neural Engine\nShannon Entropy Gating"]
    AI -->|HTTP GET /api/diagnosis/set| Cam["ESP32-CAM Bridge Buffer"]
    Wand -->|Polls /api/diagnosis/latest (Non-Blocking)| Cam
    Wand -->|Renders 4-Page Diagnosis & Cure Carousel| OLED["SSD1306 OLED Screen (I2C)"]
```

---

## 4. Cost Comparison & Affordability Analysis

| Component / Solution | Commercial Agritech Lab | Typical Cloud Agritech App | KRISHI-DRISHTI (Our Project) |
| :--- | :--- | :--- | :--- |
| **Hardware Diagnostic Tool** | ₹25,000 – ₹60,000 | Requires ₹15,000+ 5G Phone | **₹1,514 INR Total** |
| **Internet Requirement** | High (Cloud API) | Mandatory 4G/5G data | **100% Offline (Zero Data)** |
| **Recurring Cloud API Fee** | ₹500 – ₹1,500 / month | ₹200 – ₹500 / month | **₹0.00 (Zero Recurring Cost)** |
| **Canopy Incubation Sensor** | ₹8,000 weather station | Not Available | **Integrated DHT11 (₹57)* |

*\*Note on DHT11 Sensor: Measures ambient canopy temperature and relative humidity incubation conditions favorable for Phytophthora infestans sporulation and germination (Hyre/Wallin disease triangle); does not directly detect microscopic airborne spores or surface leaf wetness film.*
| **Target User** | Industrial Agro-Farms | Urban Gardeners | **Marginal Indian Farmers** |

---

## 5. Agronomic Prescriptions

Unlike generic diagnostic tools, KRISHI-DRISHTI outputs practical, dual-tier advice:
1. **Tier 1 — Organic / Biocontrol (जैविक उपचार):**
   * Cold-pressed Neem Oil (5ml/L) + *Trichoderma viride* / *Trichoderma harzianum* soil drenching.
   * Cultural practice: Pruning lower leaves (< 15cm from soil) to prevent soil-splash spore inoculation; strict haulm destruction 10 days before potato harvest.
2. **Tier 2 — Targeted Chemical Intervention (रासायनिक उपचार):**
   * Protective contact spray: Mancozeb 75% WP @ 2.5g/L or Copper Oxychloride 50% WP @ 3.0g/L.
   * Curative systemic spray: Cymoxanil 8% + Mancozeb 64% WP @ 2.5g/L or Ridomil Gold (Metalaxyl-M + Mancozeb) @ 2.0g/L if defoliation is actively progressing.

---

## 6. AI Model Performance & Empirical Validation Benchmark

To eliminate subjective bias and data leakage during scientific evaluation, the KRISHI-DRISHTI neural network was retrained on the **Pure Dual-Domain Solanaceae Corpus** (7,710 total records, 6,965 unique training SHA-256 hashes, with 100% cryptographic and perceptual exclusion of all 60 benchmark leaves, held-out PlantDoc images, and field test frames).

### 6.1 Dataset Distribution & Strict Class Alignment
The 7,710 training records reconcile into exactly 6,965 unique SHA-256 image hashes (6,600 clean PlantVillage samples [1,100 per class] representing 6,595 unique hashes, plus 370 clean outdoor PlantDoc representations replicated 3x = 1,110 records). 
* **Hash Reconciliation Audit:** The difference between 6,600 PlantVillage file paths and 6,595 unique hashes stems from exactly 5 duplicate image pairs in the public Kaggle mirror (`vipoooool/new-plant-diseases-dataset`). A dedicated cryptographic assertion verifies that all duplicates share identical class labels—yielding **zero cross-class label conflicts** and **zero cross-dataset leakage**.

| Index | Foliar Class Label | Target Crop | Botanical / Pathological Agent | Unique Training Hashes | Replicated Total | Validation Samples |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: |
| **0** | `Tomato___Late_blight` | *Solanum lycopersicum* | *Phytophthora infestans* (Oomycete) | 1,180 | 1,368 | 463 |
| **1** | `Tomato___Early_blight` | *Solanum lycopersicum* | *Alternaria solani* (Fungus) | 1,232 | 1,518 | 480 |
| **2** | `Tomato___healthy` | *Solanum lycopersicum* | Asymptomatic leaf tissue | 1,166 | 1,326 | 481 |
| **3** | `Potato___Late_blight` | *Solanum tuberosum* | *Phytophthora infestans* (Oomycete) | 1,170 | 1,268 | 485 |
| **4** | `Potato___Early_blight` | *Solanum tuberosum* | *Alternaria solani* (Fungus) | 1,121 | 1,280 | 485 |
| **5** | `Potato___healthy` | *Solanum tuberosum* | Asymptomatic leaf tissue | 1,096 | 950 | 456 |
| **Total** | **Solanaceae Corpus** | **6-Class Taxonomy** | **Pure Dual-Domain Baseline** | **6,965 Unique** | **7,710 Records** | **2,850 Images** |

### 6.2 Model Architecture & Training Protocol
1. **Backbone Architecture:** MobileNetV3-Small pre-trained on ImageNet, utilizing inverted residual bottlenecks and Squeeze-and-Excitation (SE) attention blocks.
2. **Canopy Data Augmentation:** Real-time affine transformations (`RandomFlip`, `RandomRotation(0.12)`, `RandomZoom(0.08)`, `RandomContrast(0.08)`) simulating field flutter and outdoor sun glare.
3. **Stage 1 (Head Warmup):** 2 epochs with frozen backbone using Adam ($	ext{lr} = 10^{-3}$), training dense classification layer with Dropout (0.25).
4. **Stage 2 (Deep Fine-Tuning):** 2 epochs unfreezing top 25 convolutional layers ($	ext{lr} = 10^{-4}$) to adapt high-level visual representations directly to foliar lesions.
5. **Float16 Quantization:** Post-Training Quantization (PTQ) reduces weights to IEEE 754 half-precision float16 (**2.03 MB** / 2,123,856 bytes for the shipped model, SHA-256: `a2a4c9f6134ec0de4b7c0654ce367a19afd86d730942d754eea5ab2a96186404`), with standard Float32 input/output interfaces (`[1, 128, 128, 3]` raw pixels and `[1, 6]` probabilities with built-in Softmax). Measured inference latency is **5.57 ms mean** on the host-PC CPU reference interpreter with XNNPACK across the 60-specimen benchmark; mobile-edge latency has not been measured on device.

### 6.3 Empirical Performance Metrics
| Metric | Benchmark Result | Practical Agricultural Significance |
| :--- | :--- | :--- |
| **Validation Set Accuracy** | **88.74%** | 2,529 / 2,850 held-out validation images (`ai_engine/model_evaluation_report.json`) |
| **Validation Macro F1 Score** | **0.8863** | Unweighted mean of the six per-class F1 scores below |
| **Tomato Late Blight** | P 92.15% / R 65.87% / **F1 0.7683** | Weakest class; roughly a third of late-blight tissue is predicted as potato late blight |
| **Tomato Early Blight** | P 94.96% / R 74.58% / **F1 0.8355** | Confused mainly with tomato late blight and healthy tissue |
| **Tomato Healthy** | P 91.57% / R 99.38% / **F1 0.9531** | High recall; 20 healthy frames offered to blight classes |
| **Potato Late Blight** | P 68.92% / R 98.76% / **F1 0.8119** | High recall, low precision; absorbs tomato late-blight frames |
| **Potato Early Blight** | P 98.09% / R 95.26% / **F1 0.9665** | Most reliable blight class |
| **Potato Healthy** | P 98.46% / R 98.03% / **F1 0.9824** | Most reliable class overall |
| **60-Specimen Botanical Benchmark** | **95.00% Strict / 98.28% Accepted** | 57/60 strict 6-class match; 57/58 accepted-frame accuracy (96.67% coverage, 2 frames gated UNCERTAIN); pathogen-family match 57/60 reported separately |
| **PlantDoc Held-Out Unseen Test Partition** | **22.58% Raw $ightarrow$ 60.00% Accepted** | Hash-level holdout manifest (`PLANTDOC_HOLDOUT_MANIFEST.json`). 93 unseen images (100% excluded from training, 0 duplicate hashes): 21/93 raw accuracy, 21/35 accepted-frame accuracy, 58 frames gated UNCERTAIN; full adaptation corpus (487 images): 32.44% raw (158/487) / 73.49% accepted (158/215) |
| **Field Night-Flash & OOD Audit** | **1/6 In-Domain (16.7%) / 4/4 OOD Gated (100%)** | Unshielded torch flash creates specular central hotspots confused with necrotic margins (5/6 misdiagnosed or gated). All 4 alien non-crop leaves (Hibiscus) safely intercepted by dark-void gating |
| **Exploratory Open-Web Specimens** | **15 Wikimedia Commons Images** | Evaluated on unencountered internet photography. Demonstrates shadow susceptibility on healthy potato and high-confidence false acceptance on alien tea leaf (87.0%) |
| **Model Size (Quantized TFLite)** | **2.03 MB (2,123,856 bytes)** | Universal: Fully cached in RAM on any low-RAM smartphone (1GB+ RAM, Android/iOS) |
| **Edge Inference Latency** | **5.57 ms Mean (Host CPU Reference)** | 60-specimen benchmark mean on host CPU (Intel i5 with XNNPACK), `tests/benchmark_60_specimens_report.json`; mobile-edge latency not yet measured on device |

### 6.4 Scientific Uncertainty & Plausibility Gating
To prevent misleading predictions when pointed at bare soil, weeds, or hands:
* **Foliar Plausibility Ratio:** Evaluates green chlorophyll and necrotic pigmentation; rejects images with $< 12\%$ foliar tissue (`NON_LEAF` status).
* **Peripheral Dark Void Gate:** Intercepts frames where dark perimeter pixels exceed $45\%$, preventing misclassification of black background cloths or unshielded flash drop-offs.
* **Shannon Information Entropy:** Computes $H = -\sum_{i=1}^6 p_i \ln p_i$. Ambiguous or uniform probability spreads ($H > 1.45$ nats or $p_{\max} < 0.50$) trigger an explicit `UNCERTAIN` advisory, prompting the farmer to steady the wand.

### 6.5 Core Scientific Principles & Real-World Engineering Findings

#### A. Pathogen Family Match vs. Discrete 6-Class Classification
In botanical pathology, Late Blight on both Tomato (*Solanum lycopersicum*) and Potato (*Solanum tuberosum*) is incited by the exact same oomycete water mold, ***Phytophthora infestans***. Similarly, Early Blight on both crops is incited by the fungus ***Alternaria solani***. 
* Consequently, when a tomato late blight leaf exhibits characteristic water-soaked olive lesions and the neural network predicts `Potato Late Blight`, the system has successfully recognized the **underlying biological pathogen family** (*Phytophthora infestans*).
* **Strict Scientific Standard:** In KRISHI-DRISHTI's 6-class discrete taxonomy, crop host and disease constitute distinct output classes. Therefore, **pathogen matches are never counted toward exact 6-class classification accuracy**. They are reported strictly as biological pathogen correlations (e.g., 57/60 strict vs. 57/60 pathogen match on the current model).

#### B. The Optical Shroud is a Physical Acquisition Constraint, Not an OOD Shield
The 3D-printed cylindrical optical shroud (8–10 cm depth) performs two critical optical functions:
1. **Mechanical Focal Distance Enforcement:** Fixes the subject distance to the OV5640 lens hyperfocal sweet spot, preventing severe macro blur.
2. **Ambient Stray Light Suppression:** Diffuses harsh directional sunlight and prevents long oblique shadows that convolutional edge filters misinterpret as necrotic lesion boundaries.
* **Limitation:** The shroud **does not and cannot function as an out-of-distribution (OOD) biological shield**. If an alien green leaf (such as a tea leaf or hibiscus) is inserted into the shroud, its chlorophyll pigments, veins, and natural leaf curvature can satisfy foliar plausibility and trigger high model confidence (as evidenced by our empirical test where an alien tea leaf reached 87.0% false confidence for Late Blight). The shroud stabilizes image capture; it does not replace botanical domain boundary enforcement.

#### C. Microclimate Telemetry as a Simplified Agronomic Risk Advisory
Classic epidemiological forecasting systems (such as Wallin and Hyre models) require continuous, cumulative temperature-humidity wetness duration tracking over multiple days to calculate Severity Values (SVs).
* KRISHI-DRISHTI's DHT11 canopy sensor provides an **instantaneous environmental risk advisory**, not a definitive biological proof of disease presence or absence.
* **Operational Rule:** When visual inference indicates disease but ambient canopy Relative Humidity is $< 85\%$, the system issues a conservative advisory: suppressing urgent chemical fungicide recommendations (e.g., systemic Metalaxyl) and alerting the farmer to verify foliar moisture. This prevents costly chemical misapplication triggered by visual illumination artifacts, while remaining honest about the limitations of single-point atmospheric sensing.

#### D. Exploratory Open-Web Testing vs. Formal Controlled Field Trials
Evaluating 15 unencountered open-web photographs from Wikimedia Commons provided valuable qualitative insights into failure modes (e.g., harsh drop shadows causing false positives on healthy potato foliage, and tea leaves causing high-confidence false acceptance).
* **Methodological Distinction:** Such small web sample sets represent **exploratory qualitative case studies**, not a statistically representative or independent field benchmark. 
* Furthermore, scraping arbitrary internet datasets without cryptographic deduplication introduces severe risks: 15–30% crowdsourced label noise, capacity saturation of low-parameter edge architectures (MobileNetV3-Small), and hidden benchmark contamination.

### 6.6 The Next Defining Milestone: Hardware Field Validation Protocol
The definitive proof of KRISHI-DRISHTI's real-world diagnostic reliability cannot come from internet web crawls. It must come from **images captured directly by the KRISHI-DRISHTI hardware wand (ESP32-CAM OV5640 with optical shroud) in authentic agricultural fields**.
* **Field Validation Protocol:** Defined in `tests/hardware_field_captures/FIELD_VALIDATION_PROTOCOL.md` and automated via `tests/validate_hardware_field_captures.py`.
* **Standardized Metadata:** Every field capture must log `capture_id`, `shroud_status` (attached/detached), `dht11_temp_c`, `dht11_humidity_pct`, `lighting_condition` (daylight/diffuse/shrouded), and independent expert pathologist verification.
* **Target Objective:** Quantify exact 6-class vs. pathogen correlation on the genuine hardware sensor pipeline under real farm conditions.

---

## 7. Source-Available Architecture
All source code, CAD files, schematics, and model weights are released freely under the **Source-Available License** on GitHub:  
**Repository:** [https://github.com/gautamkr0104/KRISHI-DRISHTI](https://github.com/gautamkr0104/KRISHI-DRISHTI)

---

## 8. Wi-Fi Connectivity & Network Resilience

The Controller wand (ESP32 DevKit V1) operates as a Wi-Fi Station associating to the Camera unit's SoftAP (`KRISHI-DRISHTI` @ 192.168.4.1). The connection pipeline was hardened across three firmware revisions:

### 8.1 Transmit Power
Wi-Fi RF transmit power was set to `8.5 dBm` — a stable level for USB-powered ESP32 operation that avoids TG1WDT watchdog resets during Wi-Fi radio bringup. Higher power levels (13–19.5 dBm) caused crashes on USB power, so 8.5 dBm was retained for reliability. Hardware brownout protection is suppressed during Wi-Fi PLL lock (`WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0)`) to prevent resets under radio load.

### 8.2 Static IP with DHCP Fallback
The controller requests static IP `192.168.4.2` (gateway `192.168.4.1`) for deterministic addressing. Because ESP32 static-IP assignment can fail on SoftAP links, the firmware retries with DHCP if static association does not complete within the retry window. The wand cycles between static-IP and DHCP attempts every 5 seconds until linked.

### 8.3 Fully Non-Blocking Association
Wi-Fi association is entirely non-blocking: `ensureWiFiConnected()` calls `WiFi.begin()` every 5 seconds and returns immediately, letting the ESP32 Wi-Fi driver handle association in the background. The multifunction button on GPIO 27 remains responsive and cycles OLED pages even while the wand is still linking to the camera, so the user is never locked out of the UI during connection attempts.

### 8.4 Connection State Machine
- **WL_CONNECTED:** `wifiConnected = true`, OLED shows `CAM LINKED! [OK]` or `CAM LINKED! [DHCP]`
- **Disconnected:** `wifiConnected = false`, OLED shows `Linking to Cam...`, background retries continue every 5s
- **Standby Mode:** If the camera is out of range after all retries, the OLED shows `Camera not in range`; environmental telemetry (DHT11) and page navigation remain available
