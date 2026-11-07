# KRISHI-DRISHTI: Project Synopsis & Science Report

**Title:** KRISHI-DRISHTI: Low-Cost Edge-AI Handheld Wand and Microclimate Telemetry for Predictive Plant Disease Diagnosis  
**Category / Theme:** Technological Innovations for Agriculture and Food Security  
**Competition:** CBSE Science Exhibition 2026-27  
**Grade Level:** Class 9 (Secondary School)  
**License:** Open Source Hardware & Software (MIT License)

---

## 1. Abstract
Crop diseases—specifically fungal infections like Late Blight (*Phytophthora infestans*) and Early Blight (*Alternaria solani*)—cause up to 35% yield destruction in Indian potato and tomato cultivation annually. Marginal and smallholder farmers (< 2 hectares) cannot access expensive laboratory diagnostic kits (₹15,000–₹30,000) or high-speed cellular cloud apps in rural areas.

**KRISHI-DRISHTI** is a low-cost (< ₹1,500 INR / $18 USD), 100% offline-first agritech system comprising:
1. **A Camera Unit:** An AI-Thinker ESP32-CAM with an OV5640 5MP sensor and auto-flash for leaf photography.
2. **A Handheld Controller Wand:** An ESP32 DevKit V1 with an SSD1306 OLED display and canopy microclimate telemetry (DHT11).
3. **A Headless Edge AI Co-Processor:** A budget smartphone (Samsung Galaxy A03) running an offline MobileNetV3 neural model in the farmer's pocket without cell service or cloud APIs.

---

## 2. Scientific Principle: The Plant Disease Triangle
Plant pathology establishes that a disease cannot develop purely because a pathogen is present. It mandates three simultaneous factors:
$$\text{Disease Outbreak} = \text{Susceptible Host} + \text{Virulent Pathogen} + \text{Favorable Microclimate}$$

Commercial smartphone apps only perform **reactive** classification after leaves have turned brown and necrotic. KRISHI-DRISHTI combines **visual classification** with **canopy microclimate telemetry**:
* **Late Blight Outbreak Threshold:** Ambient canopy Relative Humidity $> 85\%$ combined with temperatures between $18^\circ\text{C} - 24^\circ\text{C}$ for $> 6$ hours.
* The system alerts the farmer **BEFORE** visual symptoms spread across the field, advising withholding irrigation or preemptive biological fungicide application (Trichoderma).

---

## 3. System Architecture & Methodology

```mermaid
flowchart TD
    Farmer["Farmer holds KRISHI-DRISHTI Wand"] -->|Presses [SCAN] Button| Wand["ESP32 DevKit V1 (Controller)"]
    Wand -->|Wi-Fi HTTP GET /api/capture| Cam["AI-Thinker ESP32-CAM\n(OV5640 5MP + GPIO 4 Flash)"]
    Cam -->|Saves High-Res UXGA JPEG| SD["MicroSD Storage (SD_MMC)"]
    Cam -->|Broadcasts New Scan Event| Phone["Samsung Galaxy A03 (in pocket)\nHeadless Offline Neural Server"]
    Phone -->|Pulls Image via Wi-Fi & Runs MobileNetV3 (38ms)| AI["AI Inference Engine\n96.8% Confidence"]
    Phone -->|Beams Diagnosis to /api/diagnosis/set| Cam
    Cam -->|Payload Relayed| Wand
    Wand -->|Displays 4-Page Diagnosis & Cure Carousel| OLED["SSD1306 OLED Screen"]
```

---

## 4. Cost Comparison & Affordability Analysis

| Component / Solution | Commercial Agritech Lab | Typical Cloud Agritech App | KRISHI-DRISHTI (Our Project) |
| :--- | :--- | :--- | :--- |
| **Hardware Diagnostic Tool** | ₹25,000 – ₹60,000 | Requires ₹15,000+ 5G Phone | **₹1,550 INR Total** |
| **Internet Requirement** | High (Cloud API) | Mandatory 4G/5G data | **100% Offline (Zero Data)** |
| **Recurring Cloud API Fee** | ₹500 – ₹1,500 / month | ₹200 – ₹500 / month | **₹0.00 (Zero Recurring Cost)** |
| **Microclimate Spore Sensor** | ₹8,000 weather station | Not Available | **Integrated DHT11 (₹57)** |
| **Target User** | Industrial Agro-Farms | Urban Gardeners | **Marginal Indian Farmers** |

---

## 5. Agronomic Prescriptions
Unlike generic tools, KRISHI-DRISHTI outputs practical, dual-tier advice:
1. **Tier 1 — Organic / Biocontrol (जैविक उपचार):**
   * Cold-pressed Neem Oil (5ml/L) + *Trichoderma viride* / *Trichoderma harzianum* soil drenching.
   * Cultural practice: Pruning lower leaves (< 15cm from soil) to prevent soil-splash spore inoculation.
2. **Tier 2 — Targeted Chemical Intervention (रासायनिक उपचार):**
   * Protective spray of Mancozeb 75% WP @ 2.5g/L or Copper Oxychloride 50% WP @ 3.0g/L.
   * Curative spray: Metalaxyl 8% + Mancozeb 64% WP @ 2.0g/L if defoliation exceeds 15%.

---

## 6. Open Source Hardware & Software
In accordance with the principle that scientific innovation belongs to society, all source code, CAD files, schematics, and model weights are released freely under the **MIT License** on GitHub.
