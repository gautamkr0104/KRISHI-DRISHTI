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
2. **A Handheld Controller Wand:** An ESP32 DevKit V1 with an SSD1306 OLED display, active-low SCAN/NEXT buttons, and canopy microclimate telemetry (DHT11 on GPIO 18).
3. **A Headless Edge AI Co-Processor:** A budget smartphone (Samsung Galaxy A03, Android 13) running an offline MobileNetV3 neural model in the farmer's pocket without cell service or cloud APIs.

*Scientific Scope:* The device provides immediate, non-invasive **field screening indications and agronomic triage**, intended to guide timely preventative action rather than replace destructive laboratory PCR/ELISA confirmation.

---

## 2. Scientific Principle: The Plant Disease Triangle
Plant pathology dictates that infectious plant disease cannot develop purely because an inoculum is present. It mandates three concurrent, interdependent factors:
$$\text{Disease Outbreak} = \text{Susceptible Host} + \text{Virulent Pathogen} + \text{Favorable Microclimate}$$

Commercial smartphone apps only perform **reactive** classification after leaves have already turned brown, necrotic, and infectious. KRISHI-DRISHTI correlates **visual foliar classification** with **canopy microclimate telemetry**:
* **Late Blight Outbreak Risk Envelope:** Sustained canopy Relative Humidity $> 85\%$ combined with temperatures between $18^\circ\text{C} - 24.5^\circ\text{C}$ for $> 6$ hours.
* **Early Blight Risk Envelope:** Warm canopy temperatures ($24^\circ\text{C} - 29^\circ\text{C}$) paired with alternating wet-dry dew cycles.
* The system tracks **microclimate disease-risk incubation conditions** (temperature and humidity thresholds) alongside visual foliar screening, alerting the farmer when environmental factors favor pathogen incubation so that irrigation or cultural interventions can be applied proactively.

---

## 3. System Architecture & Telemetry Pipeline

```mermaid
flowchart TD
    Farmer["Farmer holds KRISHI-DRISHTI Wand"] -->|Presses [SCAN] Button (GPIO 27)| Wand["ESP32 DevKit V1 (Controller)"]
    Wand -->|Wi-Fi HTTP GET /api/capture| Cam["AI-Thinker ESP32-CAM\n(OV5640 5MP + GPIO 4 Flash)"]
    Cam -->|Saves High-Res UXGA JPEG to SDMMC| SD["8GB MicroSD Card\n(Write Verified >= 512B)"]
    Cam -->|Broadcasts New scan_id| Phone["Samsung Galaxy A03 (in pocket)\nHeadless Offline Neural Server"]
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

To eliminate subjective bias during scientific evaluation, the KRISHI-DRISHTI neural network was trained on the primary **New Plant Diseases Dataset (Augmented 87K, Solanaceae Partition)** across 14,249 images and evaluated on independent real-world field photographs from **PlantDoc**.

### 6.1 Dataset Distribution & Strict Class Alignment
| Index | Foliar Class Label | Target Crop | Botanical / Pathological Agent | Training Samples | Validation Samples |
| :---: | :--- | :--- | :--- | :---: | :---: |
| **0** | `Tomato___Late_blight` | *Solanum lycopersicum* | *Phytophthora infestans* (Oomycete) | 1,909 | 463 |
| **1** | `Tomato___Early_blight` | *Solanum lycopersicum* | *Alternaria solani* (Fungus) | 1,000 | 480 |
| **2** | `Tomato___healthy` | *Solanum lycopersicum* | Asymptomatic leaf tissue | 1,591 | 481 |
| **3** | `Potato___Late_blight` | *Solanum tuberosum* | *Phytophthora infestans* (Oomycete) | 1,000 | 485 |
| **4** | `Potato___Early_blight` | *Solanum tuberosum* | *Alternaria solani* (Fungus) | 1,000 | 485 |
| **5** | `Potato___healthy` | *Solanum tuberosum* | Asymptomatic leaf tissue | 152 | 456 |
| **Total** | **Solanaceae Corpus** | **6-Class Taxonomy** | **Comprehensive Foliar Baseline** | **11,399 Images** | **2,850 Images** |

### 6.2 Model Architecture & Training Protocol
1. **Backbone Architecture:** MobileNetV3-Small pre-trained on ImageNet, utilizing inverted residual bottlenecks and Squeeze-and-Excitation (SE) attention blocks.
2. **Canopy Data Augmentation:** Real-time affine transformations (`RandomFlip`, `RandomRotation(0.12)`, `RandomZoom(0.08)`, `RandomContrast(0.08)`) simulating field flutter and outdoor sun glare.
3. **Stage 1 (Head Warmup):** 2 epochs with frozen backbone using Adam ($\text{lr} = 10^{-3}$), training dense classification layer with Dropout (0.25).
4. **Stage 2 (Deep Fine-Tuning):** 2 epochs unfreezing top 25 convolutional layers ($\text{lr} = 10^{-4}$) to adapt high-level visual representations directly to foliar lesions.
5. **Float16 Quantization:** Post-Training Quantization (PTQ) reducing weights to IEEE 754 half-precision float16 (reducing model footprint from 4.02 MB to **2.03 MB**), with standard Float32 input/output interfaces (`[1, 128, 128, 3]` raw pixels and `[1, 6]` probabilities with built-in Softmax), achieving **3.74–4.14 ms** inference on host CPU reference interpreter (benchmark mean: **3.94 ms** with XNNPACK; target ~12–15 ms on smartphone mobile CPU engineering estimate, budget < 40 ms).

### 6.3 Empirical Performance Metrics
| Metric | Benchmark Result | Practical Agricultural Significance |
| :--- | :--- | :--- |
| **Training Convergence Accuracy** | **91.80%** | Robust feature representation on diverse foliar lesions |
| **Validation Set Accuracy** | **88.74%** | Evaluated on 2,850 unseen independent validation images |
| **Validation Macro F1 Score** | **0.8863** | Balanced performance across all 6 Solanaceae categories |
| **Potato Early Blight F1** | **0.9665** | Precision: 98.09%, Recall: 95.26% |
| **Potato Healthy Tissue F1** | **0.9824** | Precision: 98.46%, Recall: 98.03% |
| **Tomato Healthy Tissue F1** | **0.9531** | Precision: 91.57%, Recall: 99.38% |
| **60-Specimen Botanical Benchmark** | **93.3% Strict / 93.3% Accepted** | Strict 6-class: 56/60 (93.33%); Accepted: 56/60 (93.33% coverage, 0 gated UNCERTAIN; 57/60 95.0% pathogen match) |
| **PlantDoc Outdoor Field Benchmark** | **48.05% Raw (All Frames) $\rightarrow$ 72.00% (Accepted Frames)** | Evaluated across 487 uncalibrated outdoor images; Dual-Stage Gating safely flags 162 ambiguous/cluttered frames (33.26%) as UNCERTAIN |
| **Model Size (Quantized TFLite)** | **2.03 MB** | Fully cached in RAM on low-RAM phones (Galaxy A03) |
| **Edge Inference Latency** | **3.94 ms Mean (Host CPU Reference)** | Benchmark mean: 3.94 ms on Host CPU (Intel i5 with XNNPACK, range: 3.74–4.14 ms); Target Mobile Edge: ~12–15 ms (Galaxy A03 Cortex-A55 engineering estimate, budget < 40 ms) |

### 6.4 Scientific Uncertainty & Plausibility Gating
To prevent misleading predictions when pointed at bare soil, weeds, or hands:
* **Foliar Plausibility Ratio:** Evaluates green chlorophyll and necrotic pigmentation; rejects images with $< 12\%$ foliar tissue (`NON_LEAF` status).
* **Shannon Information Entropy:** Computes $H = -\sum_{i=1}^6 p_i \ln p_i$. Ambiguous or uniform probability spreads ($H > 1.45$ nats or $p_{\max} < 0.50$) trigger an explicit `UNCERTAIN` advisory, prompting the farmer to steady the wand.

---

## 7. Technical Defense & System Architecture Q&A Strategy

### Q1: "Where did you learn your coding? Did you just copy-paste this from YouTube or GitHub?"
> **Student Defense:**  
> *"Respected Sir/Ma'am, I learned standard C++ and Python syntax through tutorials and official documentation. However, **KRISHI-DRISHTI is an original multi-tier systems architecture** designed specifically to overcome hardware limitations:  
> 1. In `KRISHI_DRISHTI_Camera.ino`, the Edge AI server daemon is embedded directly into ESP32 flash memory (`PROGMEM`) and static files are streamed from SDMMC, overcoming Android 13's Scoped Storage restriction (`ERR_ACCESS_DENIED`) and allowing offline browser inference.  
> 2. The Controller wand uses non-blocking polling and FreeRTOS-compatible timing for SSD1306 I2C telemetry, decoupling camera captures from sensor reads to prevent Watchdog Timer (WDT) resets.  
> 3. The machine learning pipeline uses two-stage fine-tuning with canopy-specific augmentation on 11,399 Kaggle images and evaluates against PlantDoc field images, with Shannon entropy gating to reject non-leaf frames."*

### Q2: "Is Late Blight caused by a fungus?"
> **Student Defense:**  
> *"Historically, Late Blight was classified as a fungus, but modern botanical taxonomy classifies its causal agent, **Phytophthora infestans**, as an **Oomycete** (water mold in the kingdom Stramenopila). This distinction is critical because true fungi have chitinous cell walls, whereas Oomycetes have cell walls composed of cellulose and $\beta$-glucans. Consequently, standard fungal chitin-inhibiting fungicides are ineffective against Late Blight, requiring oomycete-specific active ingredients like Metalaxyl, Cymoxanil, or copper compounds."*

### Q3: "Why not run the neural network directly on the ESP32 microchip?"
> **Student Defense:**  
> *"An ESP32-S has 520 KB of internal SRAM and ~4 MB external PSRAM running at 240 MHz without hardware vector or NEON SIMD acceleration. Running a convolutional backbone like MobileNet directly on the microcontroller causes two major hardware failures:  
> 1. Frame buffer starvation: The OV5640 5MP camera DMA channels compete with neural tensor allocations in PSRAM, leading to memory heap fragmentation and kernel panics.  
> 2. Latency: Inference takes over 3.8 seconds per frame on an MCU, draining battery power.  
> By delegating inference to the farmer's pocket smartphone over local Wi-Fi SoftAP, we achieve a **4.15 to 4.69-millisecond host reference inference time (~12–15 ms on budget smartphone CPUs)** on the phone's CPU while keeping the wand lightweight, ultra-low power, and strictly under ₹1,500 total cost."*

---

## 8. Source-Available Architecture
All source code, CAD files, schematics, and model weights are released freely under the **Source-Available License** on GitHub:  
**Repository:** [https://github.com/gautamkr0104/KRISHI-DRISHTI](https://github.com/gautamkr0104/KRISHI-DRISHTI)
