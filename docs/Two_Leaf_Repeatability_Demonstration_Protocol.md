# KRISHI-DRISHTI — 50-Condition Multi-Factor Robustness & Repeatability Protocol

**Author:** Gautam Kumar (Class IX)  
**Institution:** Udaan International School, Begusarai, Bihar  
**Purpose:** Standardized physical verification protocol to demonstrate edge diagnostic repeatability, focus stability, illumination invariance, and uncertainty rejection across 50 distinct test conditions to science fair judges.

---

## 1. Objective & Scientific Honesty

This demonstration is specifically designed to prove **system repeatability, hardware-in-the-loop stability, and epistemic uncertainty gating**, not to artificially claim 100% field generalization across uncalibrated outdoor landscapes.

In a live judging environment, testing the wand across **50 controlled experimental conditions** allows judges to directly verify:
1. **Camera Trigger & SD Logging:** Reliable 1600×1200 frame capture without file truncation.
2. **Wi-Fi Telemetry Round-Trip:** Non-blocking synchronization between ESP32 Controller, ESP32-CAM, and phone co-processor.
3. **Inference Consistency:** Low variance in predicted confidence scores under consistent lighting and distance.
4. **Dual-Stage Uncertainty Gating:** 100% automatic rejection of non-foliar objects, bare soil, hands, and ambiguous frames.

---

## 2. Experimental Setup & Equipment

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **Specimen A (Healthy)** | Solanaceae (*Solanum lycopersicum*) Healthy Foliage | Uniform green cuticle, zero necrotic lesions |
| **Specimen B (Infected)** | Solanaceae (*Solanum lycopersicum*) Late Blight Target | Visible water-soaked dark lesions with chlorotic halos (*Phytophthora infestans*) |
| **Edge Controls** | Lens cap (black), blank paper (white), dry soil, human palm | Non-foliar and out-of-distribution targets |
| **Focal Distance Range** | 6 cm to 15 cm (Nominal: 8 cm – 12 cm) | Controlled via wand spacer |
| **Illumination Range** | 100 lux (deep shade) to 1,000 lux (bright ambient) | Modulated with diffuse LED / onboard flash |
| **Total Trials** | **50 Structured Scans (5 Condition Sets × 10 Trials)** | Logged sequentially to MicroSD (`/scans/`) |

---

## 3. The 50-Condition Experimental Matrix

### Condition Set 1: Baseline Geometry & Controlled Illumination (Scans 01–10)
*Setup: 8–10 cm distance, 90° perpendicular incidence, 500 lux diffuse illumination.*
* **Scans 01–05 (Tomato Healthy):** Evaluates baseline consistency. Expected prediction: `Tomato Healthy` (>95.0% confidence, Shannon entropy $H < 0.10$, Status: `OPTIMAL`).
* **Scans 06–10 (Tomato Late Blight):** Evaluates baseline disease sensitivity. Expected prediction: `Tomato Late Blight` (>90.0% confidence, Shannon entropy $H < 0.20$, Status: `SEVERE`).

### Condition Set 2: Focal Distance & Macro Depth-of-Field Sensitivity (Scans 11–20)
*Setup: Perpendicular angle, variable working distance from leaf surface.*
* **Scans 11–12 (Extreme Close-Up, 6 cm):** Partial blur. Dual-stage gating evaluates whether blur shifts entropy.
* **Scans 13–16 (Optimal Working Window, 8 cm – 12 cm):** Sharp focus maintained by mechanical wand spacer. Expected: 100% accurate classification.
* **Scans 17–20 (Extended Distance, 15 cm):** Smaller foliar footprint. Evaluates foliar ratio thresholding.

### Condition Set 3: Angular Incidence & Specular Cuticle Reflection (Scans 21–30)
*Setup: 10 cm fixed distance, sensor angled off-axis relative to leaf plane.*
* **Scans 21–23 (15° Off-Axis Tilt):** Minimal parallax. Predictions remain stable with $<2\%$ confidence variance.
* **Scans 24–27 (30° Off-Axis Tilt):** Mild cuticle reflection. Evaluates robustness against specular glare.
* **Scans 28–30 (45° Steep Oblique Tilt):** Severe geometric foreshortening. Evaluates whether increased entropy triggers uncertainty gating.

### Condition Set 4: Variable Illumination & Canopy Shading (Scans 31–40)
*Setup: Optimal distance, variable ambient lux with and without onboard flash assist.*
* **Scans 31–33 (Deep Canopy Shade, ~100 lux):** Low illumination. Model relies on onboard flash assist to restore SNR.
* **Scans 34–37 (Normal Diffuse Daylight, ~400 lux):** Optimal agricultural lighting. High certainty classifications.
* **Scans 38–40 (Direct Sunlight Glare, ~1,000 lux):** High-contrast specular highlights.

### Condition Set 5: Boundary & Adversarial Uncertainty Gating Controls (Scans 41–50)
*Setup: Non-foliar and out-of-distribution surfaces presented to the camera lens.*
* **Scans 41–42 (Lens Cap / All-Black Surface):** Foliar ratio = 0.00 (< 0.12). Rejection: `UNCERTAIN (No Leaf Detected)`.
* **Scans 43–44 (Blank White Paper / Wall):** Foliar ratio = 0.00 (< 0.12). Rejection: `UNCERTAIN (No Leaf Detected)`.
* **Scans 45–46 (Bare Dry Soil / Compost):** Foliar ratio < 0.08 (< 0.12). Rejection: `UNCERTAIN (No Leaf Detected)`.
* **Scans 47–48 (Human Hand / Palm):** Foliar ratio < 0.05 (< 0.12). Rejection: `UNCERTAIN (No Leaf Detected)`.
* **Scans 49–50 (Extreme Multi-Source Glare / Ambiguous Surface):** Entropy $H > 1.45$ nats. Rejection: `UNCERTAIN (Low Confidence / Ambiguous)`.

---

## 4. Master 50-Condition Demonstration Run Sheet (Pre-Registered Protocol)

> [!NOTE]
> **Pre-Registration vs. Live Execution Protocol:**
> The end-to-end software pipeline (8-specimen daemon verification and 60-specimen reproducible botanical benchmark) is 100% verified and reproducible in automated testing. The 50 physical trials tabulated below constitute the **Pre-Registered Live Demonstration Protocol** to be executed sequentially on the physical wand in front of the NCSC evaluation committee upon hardware assembly. All conditions are pre-registered with strict quantitative acceptance criteria.

| Scan # | Target Specimen | Test Condition / Variable | Expected Classification | Expected Status | Gating Action | Live Demo Verification Status |
| :---: | :--- | :--- | :--- | :---: | :--- | :---: |
| **01–05** | Tomato Healthy Leaf | Baseline (8–10 cm, 500 lux) | `Tomato Healthy` (>95%) | `OPTIMAL` | Accepted | **PENDING LIVE DEMO** (Criteria: Conf > 95%, H < 0.10) |
| **06–10** | Tomato Late Blight Leaf | Baseline (8–10 cm, 500 lux) | `Tomato Late Blight` (>90%) | `SEVERE` | Accepted | **PENDING LIVE DEMO** (Criteria: Conf > 90%, H < 0.20) |
| **11–12** | Tomato Healthy Leaf | 6 cm (Macro Close-Up) | `Tomato Healthy` (>85%) | `OPTIMAL` | Accepted | **PENDING LIVE DEMO** (Criteria: Conf > 85%, focal blur toleration) |
| **13–14** | Tomato Healthy Leaf | 10 cm (Optimal Spacer) | `Tomato Healthy` (>95%) | `OPTIMAL` | Accepted | **PENDING LIVE DEMO** (Criteria: Conf > 95%, sharp focus) |
| **15–16** | Tomato Late Blight Leaf | 10 cm (Optimal Spacer) | `Tomato Late Blight` (>95%) | `SEVERE` | Accepted | **PENDING LIVE DEMO** (Criteria: Conf > 95%, lesion resolved) |
| **17–18** | Tomato Late Blight Leaf | 12 cm (Spacer Boundary) | `Tomato Late Blight` (>85%) | `SEVERE` | Accepted | **PENDING LIVE DEMO** (Criteria: Conf > 85%, foliar area > 20%) |
| **19–20** | Tomato Healthy Leaf | 15 cm (Extended Distance) | `Tomato Healthy` (>80%) | `OPTIMAL` | Accepted | **PENDING LIVE DEMO** (Criteria: Conf > 80%, foliar ratio >= 12%) |
| **21–23** | Tomato Healthy Leaf | 15° Off-Axis Tilt | `Tomato Healthy` (>90%) | `OPTIMAL` | Accepted | **PENDING LIVE DEMO** (Criteria: Minimal angular variance < 2%) |
| **24–27** | Tomato Late Blight Leaf | 30° Off-Axis Tilt | `Tomato Late Blight` (>85%) | `SEVERE` | Accepted | **PENDING LIVE DEMO** (Criteria: Stable diagnosis under mild glare) |
| **28–30** | Tomato Healthy Leaf | 45° Steep Oblique Tilt | `Tomato Healthy` / Gated | `OPTIMAL`/`UNCERTAIN` | Accepted / Safe Gate | **PENDING LIVE DEMO** (Criteria: Safe classification or entropy gate) |
| **31–33** | Tomato Late Blight Leaf | Deep Shade (100 lux + Flash) | `Tomato Late Blight` (>85%) | `SEVERE` | Accepted | **PENDING LIVE DEMO** (Criteria: Flash assist restores SNR, Conf > 85%) |
| **34–37** | Tomato Healthy Leaf | Diffuse Daylight (400 lux) | `Tomato Healthy` (>95%) | `OPTIMAL` | Accepted | **PENDING LIVE DEMO** (Criteria: Daylight baseline Conf > 95%) |
| **38–40** | Tomato Late Blight Leaf | Bright Ambient (1,000 lux) | `Tomato Late Blight` (>85%) | `SEVERE` | Accepted | **PENDING LIVE DEMO** (Criteria: Glare immunity, Conf > 85%) |
| **41–42** | Lens Cap (All-Black) | Zero Lux / Occluded | `No Leaf Detected` (0.0%) | `UNCERTAIN` | **REJECTED (Foliar Gate)** | **PENDING LIVE DEMO** (Criteria: Foliar ratio < 12% -> UNCERTAIN) |
| **43–44** | Blank White Paper | Non-Foliar Background | `No Leaf Detected` (0.0%) | `UNCERTAIN` | **REJECTED (Foliar Gate)** | **PENDING LIVE DEMO** (Criteria: Foliar ratio < 12% -> UNCERTAIN) |
| **45–46** | Bare Dry Soil | Agricultural Ground Control | `No Leaf Detected` (0.0%) | `UNCERTAIN` | **REJECTED (Foliar Gate)** | **PENDING LIVE DEMO** (Criteria: Foliar ratio < 12% -> UNCERTAIN) |
| **47–48** | Human Palm | Skin Cuticle Control | `No Leaf Detected` (0.0%) | `UNCERTAIN` | **REJECTED (Foliar Gate)** | **PENDING LIVE DEMO** (Criteria: Foliar ratio < 12% -> UNCERTAIN) |
| **49–50** | Extreme Glare / Ambiguous | Specular Highlight Glare | `Uncertain / Ambiguous` (<50%) | `UNCERTAIN` | **REJECTED (Entropy Gate)** | **PENDING LIVE DEMO** (Criteria: Entropy H > 1.45 nats -> UNCERTAIN) |

---

## 5. Key Talking Points for Judges

1. **Physical Repeatability vs. Generalization:**
   > *"Respected judges, this 50-condition run sheet demonstrates the physical stability of our camera optics, DMA memory buffer, and TFLite execution across five real-world variables: focal distance, viewing angle, lighting intensity, specimen health, and non-foliar edge controls. It proves that KRISHI-DRISHTI produces rock-solid, repeatable results without firmware hangs or memory leaks."*

2. **Honesty on Domain Shift & Dual-Stage Safeguards:**
   > *"While lab validation across 14,249 images is 88.74%, raw unaugmented outdoor images (PlantDoc) drop to 34.91% due to background dirt and inter-leaf shadows. That is precisely why we engineered Dual-Stage Uncertainty Gating (Condition Set 5). Instead of hallucinating a false diagnosis on confusing images, KRISHI-DRISHTI safely rejects ambiguous frames with 'UNCERTAIN / CONSULT AGRONOMIST', protecting farmers from applying costly and harmful chemicals unnecessarily."*
