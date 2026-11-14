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
5. **Float16 Quantization:** Post-Training Quantization (PTQ) reducing weights to IEEE 754 half-precision float16 (reducing model footprint from 4.02 MB to **2.03 MB** / 2,123,856 bytes, SHA-256: `be71ededc29f19f69ab98b63bebf281c6a1d88f468b6dc1a2a2dac655f406aaa`), with standard Float32 input/output interfaces (`[1, 128, 128, 3]` raw pixels and `[1, 6]` probabilities with built-in Softmax), achieving **3.94 ms** inference on host CPU reference interpreter (benchmark mean: **4.94 ms** with XNNPACK; target ~12–15 ms on smartphone mobile CPU engineering estimate, budget < 40 ms).

### 6.3 Empirical Performance Metrics
| Metric | Benchmark Result | Practical Agricultural Significance |
| :--- | :--- | :--- |
| **Training Convergence Accuracy** | **91.80%** | Robust feature representation on diverse foliar lesions |
| **Validation Set Accuracy** | **88.74%** | Evaluated on 2,850 unseen independent validation images |
| **Validation Macro F1 Score** | **0.8863** | Balanced performance across all 6 Solanaceae categories |
| **Potato Early Blight F1** | **0.9665** | Precision: 98.09%, Recall: 95.26% |
| **Potato Healthy Tissue F1** | **0.9824** | Precision: 98.46%, Recall: 98.03% |
| **Tomato Healthy Tissue F1** | **0.9531** | Precision: 91.57%, Recall: 99.38% |
| **60-Specimen Botanical Benchmark** | **88.33% Strict / 92.98% Accepted** | Strict 6-class exact match: 53/60 (88.33%); Accepted predictions: 53/57 (92.98% coverage, 3 gated UNCERTAIN; 54/60 90.0% pathogen match reported separately) |
| **PlantDoc Held-Out Unseen Test Partition** | **33.33% Raw $
ightarrow$ 55.36% Accepted** | Hash-level 80/20 holdout manifest (`PLANTDOC_HOLDOUT_MANIFEST.json`). Genuinely unseen test partition (93 unique images, 100% excluded from training, 0 duplicate hashes): 33.33% raw accuracy (31/93), 55.36% diagnostic accuracy on accepted frames (31/56, 37 frames gated UNCERTAIN); Full domain adaptation corpus (487 images): 43.12% raw (210/487) / 66.25% accepted (210/317) |
| **Field Night-Flash & OOD Audit** | **1/6 In-Domain (16.7%) / 3/4 OOD Gated (75.0%)** | Real unshielded torch flash creates specular central hotspots confused with necrotic margins (4/6 misdiagnosed). 3/4 alien non-crop leaves (Hibiscus) safely intercepted by dark-void gating |
| **Exploratory Open-Web Specimens** | **15 Wikimedia Commons Images** | Evaluated on unencountered internet photography. Demonstrates shadow susceptibility on healthy potato and high-confidence false acceptance on alien tea leaf (87.0%) |
| **Model Size (Quantized TFLite)** | **2.03 MB (2,123,856 bytes)** | Universal: Fully cached in RAM on any low-RAM smartphone (1GB+ RAM, Android/iOS) |
| **Edge Inference Latency** | **4.94 ms Mean (Host CPU Reference)** | Benchmark mean: 4.94 ms on Host CPU (Intel i5 with XNNPACK, range: 4.43–5.33 ms); Target Mobile Edge: ~12–15 ms (Tested on Cortex-A55 baseline, budget < 40 ms) |

### 6.4 Scientific Uncertainty & Plausibility Gating
To prevent misleading predictions when pointed at bare soil, weeds, or hands:
* **Foliar Plausibility Ratio:** Evaluates green chlorophyll and necrotic pigmentation; rejects images with $< 12\%$ foliar tissue (`NON_LEAF` status).
* **Peripheral Dark Void Gate:** Intercepts frames where dark perimeter pixels exceed $45\%$, preventing misclassification of black background cloths or unshielded flash drop-offs.
* **Shannon Information Entropy:** Computes $H = -\sum_{i=1}^6 p_i \ln p_i$. Ambiguous or uniform probability spreads ($H > 1.45$ nats or $p_{\max} < 0.50$) trigger an explicit `UNCERTAIN` advisory, prompting the farmer to steady the wand.

### 6.5 Core Scientific Principles & Real-World Engineering Findings

#### A. Pathogen Family Match vs. Discrete 6-Class Classification
In botanical pathology, Late Blight on both Tomato (*Solanum lycopersicum*) and Potato (*Solanum tuberosum*) is incited by the exact same oomycete water mold, ***Phytophthora infestans***. Similarly, Early Blight on both crops is incited by the fungus ***Alternaria solani***. 
* Consequently, when a tomato late blight leaf exhibits characteristic water-soaked olive lesions and the neural network predicts `Potato Late Blight`, the system has successfully recognized the **underlying biological pathogen family** (*Phytophthora infestans*).
* **Strict Scientific Standard:** In KRISHI-DRISHTI's 6-class discrete taxonomy, crop host and disease constitute distinct output classes. Therefore, **pathogen matches are never counted toward exact 6-class classification accuracy**. They are reported strictly as biological pathogen correlations (e.g., 53/60 strict vs. 54/60 pathogen match).

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

## 7. Technical Defense & System Architecture Q&A Strategy

### Q1: "Where did you learn your coding? Did you just copy-paste this from YouTube or GitHub?"
> **Student Defense:**  
> *"Respected Sir/Ma'am, I learned standard C++ and Python syntax through tutorials and official documentation. However, **KRISHI-DRISHTI is an original multi-tier systems architecture** designed specifically to overcome hardware limitations:  
> 1. In `KRISHI_DRISHTI_Camera.ino`, the Edge AI server daemon is embedded directly into ESP32 flash memory (`PROGMEM`) and static files are streamed from SDMMC, overcoming Android 13's Scoped Storage restriction (`ERR_ACCESS_DENIED`) and allowing offline browser inference.  
> 2. The Controller wand uses non-blocking polling and FreeRTOS-compatible timing for SSD1306 I2C telemetry, decoupling camera captures from sensor reads to prevent Watchdog Timer (WDT) resets. **Wi-Fi association is fully non-blocking**: the wand calls `WiFi.begin()` every 5 seconds with static IP (192.168.4.2) first, then auto-falls back to DHCP if static assignment fails — the NEXT button (GPIO 26) remains responsive throughout association.  
> 3. Wi-Fi RF transmit power is set to 8.5 dBm for stable USB-powered wand-to-camera SoftAP link, with hardware brownout protection disabled during Wi-Fi PLL lock to prevent resets under load.  
> 4. The machine learning pipeline uses two-stage fine-tuning with canopy-specific augmentation on 7,710 dual-domain records representing 6,965 unique image files (6,600 clean PlantVillage + 1,110 clean PlantDoc outdoor, documented in TRAINING_RUN_MANIFEST.json) and evaluates against PlantDoc field images, with Shannon entropy gating to reject non-leaf frames."*

### Q2: "Is Late Blight caused by a fungus?"
> **Student Defense:**  
> *"Historically, Late Blight was classified as a fungus, but modern botanical taxonomy classifies its causal agent, **Phytophthora infestans**, as an **Oomycete** (water mold in the kingdom Stramenopila). This distinction is critical because true fungi have chitinous cell walls, whereas Oomycetes have cell walls composed of cellulose and $eta$-glucans. Consequently, standard fungal chitin-inhibiting fungicides are ineffective against Late Blight, requiring oomycete-specific active ingredients like Metalaxyl, Cymoxanil, or copper compounds."*

### Q3: "Why not run the neural network directly on the ESP32 microchip?"
> **Student Defense:**  
> *"An ESP32-S has 520 KB of internal SRAM and ~4 MB external PSRAM running at 240 MHz without hardware vector or NEON SIMD acceleration. Running a convolutional backbone like MobileNet directly on the microcontroller causes two major hardware failures:  
> 1. Frame buffer starvation: The OV5640 5MP camera DMA channels compete with neural tensor allocations in PSRAM, leading to memory heap fragmentation and kernel panics.  
> 2. Latency: Inference takes over 3.8 seconds per frame on an MCU, draining battery power.  
> By delegating inference to the farmer's pocket smartphone over local Wi-Fi SoftAP, we achieve a **3.94 to 4.94-millisecond host reference inference time (~12–15 ms on budget smartphone CPUs)** on the phone's CPU while keeping the wand lightweight, ultra-low power, and total unit BOM of ₹1,480 (strictly under ₹1,500)."*

### Q4: "Why do you distinguish Pathogen Family Correlation from Exact 6-Class Classification?"
> **Student Defense:**  
> *"In our 6-class neural taxonomy, Tomato Late Blight and Potato Late Blight are distinct discrete classes. While both diseases are incited by the exact same oomycete organism (*Phytophthora infestans*) and produce identical water-soaked necrotic lesions, treating a cross-crop prediction as a full classification pass would be scientifically dishonest. Therefore, we report exact 6-class accuracy (53/60 = 88.33%) strictly separated from biological pathogen correlation (54/60 = 90.00%)."*

### Q5: "Does the 3D-printed optical shroud guarantee protection against out-of-distribution (non-crop) leaves?"
> **Student Defense:**  
> *"No, and claiming so would be scientifically inaccurate. The shroud is a physical image acquisition constraint: it fixes the camera-to-leaf working distance (8–10 cm) at the sensor's optical sweet spot and blocks harsh diagonal sun shadows. However, an out-of-distribution green leaf (such as tea or ornamental ficus) still possesses green chlorophyll and leaf vein morphology that can fool a 6-class foliar vision model into a high-confidence false positive. Gating requires multi-modal verification: visual entropy, foliar area ratios, and microclimate context."*

### Q6: "Can a single DHT11 sensor reading of RH < 85% prove that Late Blight is not present?"
> **Student Defense:**  
> *"No. Standard botanical epidemiology models like Wallin and Hyre require cumulative temperature-humidity wetness hours to predict pathogen sporulation. A single DHT11 snapshot cannot prove disease absence. Instead, KRISHI-DRISHTI uses microclimate telemetry as a **conservative agronomic risk advisory**: if visual screening detects Late Blight lesions but canopy humidity is below 85%, the system suppresses urgent chemical fungicide recommendations, preventing the farmer from spraying expensive systemic chemicals due to a shadow artifact."*

### Q7: "Why didn't you train your model on tens of thousands of free images downloaded from the web?"
> **Student Defense:**  
> *"In machine learning, data quality, label integrity, and sensor domain alignment far outweigh raw uncurated quantity. Public web scrapes suffer from 15–30% crowdsourced label noise, severe background shortcut learning (hands, flowerpots, horizons), and benchmark contamination. Furthermore, our edge budget is MobileNetV3-Small (2.03 MB), which has ~930k parameters. Overloading a lightweight edge model with high-noise internet data causes capacity saturation and degrades generalization. We prioritize curated, cryptographically audited domain data with strict zero-leakage holdout isolation."*

### Q8: "What is your next major empirical milestone to validate real-world readiness?"
> **Student Defense:**  
> *"Our defining next milestone is physical field validation: evaluating hundreds of foliar images captured directly by the KRISHI-DRISHTI ESP32-CAM wand with optical shroud in local agricultural plots across North India. Benchmarking the model on images produced by its own optical sensor under authentic ambient field conditions is the ultimate test of edge agritech readiness."*

---

## 8. Source-Available Architecture
All source code, CAD files, schematics, and model weights are released freely under the **Source-Available License** on GitHub:  
**Repository:** [https://github.com/gautamkr0104/KRISHI-DRISHTI](https://github.com/gautamkr0104/KRISHI-DRISHTI)

---

## 9. Wi-Fi Connectivity & Network Resilience

The Controller wand (ESP32 DevKit V1) operates as a Wi-Fi Station associating to the Camera unit's SoftAP (`KRISHI-DRISHTI` @ 192.168.4.1). The connection pipeline was hardened across three firmware revisions:

### 9.1 Transmit Power
Wi-Fi RF transmit power was set to `8.5 dBm` — a stable level for USB-powered ESP32 operation that avoids TG1WDT watchdog resets during Wi-Fi radio bringup. Higher power levels (13–19.5 dBm) caused crashes on USB power, so 8.5 dBm was retained for reliability. Hardware brownout protection is suppressed during Wi-Fi PLL lock (`WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0)`) to prevent resets under radio load. Hardware brownout protection is suppressed during Wi-Fi PLL lock (`WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0)`) to prevent resets under radio load.

### 9.2 Static IP with DHCP Fallback
The controller requests static IP `192.168.4.2` (gateway `192.168.4.1`) for deterministic addressing. Because ESP32 static-IP assignment can fail on SoftAP links, the firmware retries with DHCP if static association does not complete within the retry window. The wand cycles between static-IP and DHCP attempts every 5 seconds until linked.

### 9.3 Fully Non-Blocking Association
Wi-Fi association is entirely non-blocking: `ensureWiFiConnected()` calls `WiFi.begin()` every 5 seconds and returns immediately, letting the ESP32 Wi-Fi driver handle association in the background. The NEXT button (GPIO 26) remains responsive and cycles OLED pages even while the wand is still linking to the camera — the user is never locked out of the UI during connection attempts.

### 9.4 Connection State Machine
- **WL_CONNECTED:** `wifiConnected = true`, OLED shows `CAM LINKED! [OK]` or `CAM LINKED! [DHCP]`
- **Disconnected:** `wifiConnected = false`, OLED shows `Linking to Cam...`, background retries continue every 5s
- **Standby Mode:** If camera is out of range after all retries, OLED shows `Camera not in range`; wand remains usable in demo/offline mode
