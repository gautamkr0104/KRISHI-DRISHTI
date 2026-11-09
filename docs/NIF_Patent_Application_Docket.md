# NATIONAL INNOVATION FOUNDATION (NIF) — INDIA
## Formal Grassroots Technology Submission & Free Patent Facilitation Application
*(Under Department of Science & Technology (DST), Government of India)*

---

### TO:
**The National Coordinator (Scouting & Documentation / Intellectual Property Management)**  
National Innovation Foundation - India  
Grambharti, Amrapur, Gandhinagar-Mahudi Road,  
Gandhinagar, Gujarat — 382650  
**Emails:** `campaign@nifindia.org`, `info@nifindia.org`, `patent@nifindia.org`

---

### SUBJECT:
**Submission of Working Technological Prototype and Request for Free Patent Drafting & Filing Assistance under NIF-DST Mandate**

---

### 1. INNOVATOR PROFILE
* **Name of Innovator:** Gautam Kumar
* **Nationality:** Indian
* **State / District:** Begusarai, Bihar, India
* **Innovation Category:** Mechanical / Agricultural Engineering & Edge Artificial Intelligence
* **Stage of Innovation:** Fully Functional Working Hardware Prototype & Verified Neural Model

---

### 2. TITLE OF INNOVATION
> **"AN OFFLINE-FIRST DISTRIBUTED SYSTEM AND METHOD FOR PREDICTIVE PLANT HEALTH SCREENING AND MICROCLIMATE TELEMETRY (KRISHI-DRISHTI)"**

---

### 3. GENESIS & AGRICULTURAL PROBLEM ADDRESSED
In Indian agriculture—particularly across potato and tomato farming in Bihar, Uttar Pradesh, West Bengal, and Punjab—foliar blights (*Phytophthora infestans* and *Alternaria solani*) destroy 20% to 35% of annual crop yield.

Existing diagnostic solutions fail Indian smallholder farmers for three critical reasons:
1. **Excessive Cost:** Laboratory optical diagnostic kits cost ₹25,000 to ₹60,000, placing them completely out of reach of marginal farmers (< 2 hectares).
2. **Rural Connectivity Barrier:** Commercial mobile smartphone apps require continuous 4G/5G cellular internet and cloud APIs, which are absent or unreliable in rural field environments.
3. **Purely Reactive Nature:** Existing apps only classify diseases after leaves are already brown, necrotic, and infectious. They do not predict or prevent outbreaks.

**KRISHI-DRISHTI** was engineered to solve this by creating an integrated, handheld, zero-cloud agricultural screening system that costs under **₹1,500 INR ($18 USD)** to manufacture and operates **100% offline without cellular service, cloud servers, or paid subscriptions**.

---

### 4. TECHNICAL SOLUTION & SYSTEM ARCHITECTURE
The system operates as an integrated **Hardware-Software Triad** communicating over a private, ad-hoc 2.4 GHz local Wi-Fi mesh:

```text
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

1. **The Optical Capture Node (Camera Unit):**
   * AI-Thinker ESP32-CAM board with an OV5640 5MP sensor.
   * Broadcasts an isolated SoftAP network (`KRISHI-DRISHTI` @ `192.168.4.1`).
   * Onboard 8GB MicroSD operating in 1-bit SD_MMC DMA mode with strict write verification (`written >= 512 bytes`).
   * Serves static neural runtimes via embedded HTTP server with CORS headers.
2. **The Handheld Telemetry Wand (Controller Unit):**
   * ESP32 DevKit V1 microcontroller.
   * SSD1306 128×64 I2C OLED display (SDA: GPIO 21, SCL: GPIO 22).
   * Active-low pushbuttons: `[SCAN]` (GPIO 27) and `[NEXT]` (GPIO 26).
   * Digital microclimate sensor (DHT11 on GPIO 18).
   * FreeRTOS non-blocking polling state machine with stale scan rejection (`retScanId == activeScanId`).
3. **The Offline Pocket AI Co-Processor (Edge Engine):**
   * Standard budget Android smartphone (e.g., Samsung Galaxy A03) placed in the farmer's pocket.
   * Operates completely offline with mobile data turned OFF.
   * Runs an optimized MobileNetV3 Float16 neural model locally in RAM.
   * Latency: **10.54 milliseconds** per leaf.

---

### 5. SCIENTIFIC PRINCIPLE: OPERATIONALIZING THE PLANT DISEASE TRIANGLE
In classical plant pathology:
$$\text{Disease Outbreak} = \text{Susceptible Host} + \text{Virulent Pathogen} + \text{Favorable Microclimate}$$

KRISHI-DRISHTI is the first low-cost handheld device to correlate **visual foliar feature maps** with **canopy microclimate thresholds**:
* **Late Blight Outbreak Envelope:** Ambient canopy Relative Humidity $> 85\%$ combined with temperatures between $18^\circ\text{C} - 24.5^\circ\text{C}$ for $> 6$ hours.
* **Early Blight Risk Envelope:** Canopy temperatures between $24^\circ\text{C} - 29^\circ\text{C}$ with fluctuating wet/dry leaf spells.
* **Information Entropy Gating ($H$):**
  $$H = -\sum_{i=1}^6 p_i \ln p_i$$
  If $H > 1.45$ nats or maximum probability $p_{\max} < 50\%$, the system flags the image as `UNCERTAIN`, preventing false positive diagnoses on non-target vegetation or bare soil.

---

### 6. EMPIRICAL VERIFICATION & MEASURED PERFORMANCE
The neural network was trained on the **New Plant Diseases Dataset (Augmented 87K, Solanaceae Partition)** with 11,399 training and 2,850 validation images, and benchmarked on independent outdoor field photographs from **PlantDoc**:

* **Training Convergence Accuracy:** **91.80%**
* **Validation Accuracy:** **88.74%** (evaluated across 2,850 unseen real images)
* **Validation Macro F1 Score:** **0.8863**
* **Inference Latency:** **10.54 ms** (measured on edge CPU)
* **Model Size:** **2.01 MB** (Float16 Post-Training Quantized)
* **Firmware Verification:** Both ESP32 sketches compile with Exit Code 0 via `arduino-cli`.
* **Automated Regression Suite:** 6/6 tests passing (100% OK) covering label alignment, foliar plausibility, entropy bounds, and mock multi-hop HTTP telemetry.

---

### 7. PROPOSED NOVEL PATENT CLAIMS FOR FREE FILING
We request NIF’s legal cell to assist in claiming:
1. **Apparatus Claim:** An offline-first, distributed agricultural screening triad comprising a handheld environmental telemetry wand, an asynchronous optical capture unit, and a localized edge co-processor communicating over an ad-hoc local mesh without internet connectivity.
2. **Method Claim:** A method for predictive plant disease screening correlating ambient canopy temperature and humidity thresholds with real-time foliar Shannon information entropy and neural classification.
3. **Firmware Decoupling Method:** A non-blocking telemetry protocol where high-resolution frame capture, local wireless dispatches, pocket neural inference, and OLED carousel rendering are asynchronously decoupled across independent microcontrollers.

---

### 8. DECLARATION OF ORIGINALITY
I hereby declare that:
1. The KRISHI-DRISHTI system architecture, firmware implementation, and telemetry integration described herein are my original technological design.
2. The prototype is fully implemented, verified, and operational.
3. The online source repository has been set to **PRIVATE** to preserve absolute patent novelty.
4. I request the National Innovation Foundation - India to evaluate this entry and grant free patent drafting, filing, and intellectual property support under the official DST mandate.

**Dated:** 9th November 2026  
**Innovator / Applicant:** Gautam Kumar  
**Location:** Begusarai, Bihar, India
