# KRISHI-DRISHTI — 50-Condition Multi-Factor Robustness & Repeatability Protocol

**Author:** Gautam Kumar  
**Focus:** Standardized physical verification protocol for edge diagnostic repeatability, focus stability, illumination invariance, and uncertainty rejection across 50 distinct test conditions.

---

## 1. Objective & Scope

This protocol measures **system repeatability, hardware-in-the-loop stability, and epistemic uncertainty gating**. It does not attempt to establish field generalization across uncalibrated outdoor landscapes; that is the separate objective of the field validation protocol in `tests/hardware_field_captures/FIELD_VALIDATION_PROTOCOL.md`.

Running the wand across **50 controlled experimental conditions** measures:
1. **Camera Trigger & SD Logging:** Reliable 1600×1200 frame capture without file truncation.
2. **Wi-Fi Telemetry Round-Trip:** Non-blocking synchronization between ESP32 Controller, ESP32-CAM, and phone co-processor.
3. **Inference Consistency:** Variance in predicted confidence scores under consistent lighting and distance.
4. **Dual-Stage Uncertainty Gating:** Automatic rejection of non-foliar objects, bare soil, hands, and ambiguous frames.

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
* **Scans 01–05 (Tomato Healthy):** Baseline consistency. Expected prediction: `Tomato Healthy` (>95.0% confidence, Shannon entropy $H < 0.10$, Status: `OPTIMAL`).
* **Scans 06–10 (Tomato Late Blight):** Baseline disease sensitivity. Expected prediction: `Tomato Late Blight` (>90.0% confidence, Shannon entropy $H < 0.20$, Status: `SEVERE`).

### Condition Set 2: Focal Distance & Macro Depth-of-Field Sensitivity (Scans 11–20)
*Setup: Perpendicular angle, variable working distance from leaf surface.*
* **Scans 11–12 (Extreme Close-Up, 6 cm):** Partial blur. Dual-stage gating evaluates whether blur shifts entropy.
* **Scans 13–16 (Optimal Working Window, 8 cm – 12 cm):** Sharp focus maintained by mechanical wand spacer. Expected: 100% accurate classification.
* **Scans 17–20 (Extended Distance, 15 cm):** Smaller foliar footprint. Evaluates foliar ratio thresholding.

### Condition Set 3: Angular Incidence & Specular Cuticle Reflection (Scans 21–30)
*Setup: 10 cm fixed distance, sensor angled off-axis relative to leaf plane.*
* **Scans 21–23 (15° Off-Axis Tilt):** Minimal parallax. Predictions expected stable with $<2\%$ confidence variance.
* **Scans 24–27 (30° Off-Axis Tilt):** Mild cuticle reflection. Evaluates robustness against specular glare.
* **Scans 28–30 (45° Steep Oblique Tilt):** Severe geometric foreshortening. Evaluates whether increased entropy triggers uncertainty gating.

### Condition Set 4: Variable Illumination & Canopy Shading (Scans 31–40)
*Setup: Optimal distance, variable ambient lux with and without onboard flash assist.*
* **Scans 31–33 (Deep Canopy Shade, ~100 lux):** Low illumination. Model relies on onboard flash assist to restore SNR.
* **Scans 34–37 (Normal Diffuse Daylight, ~400 lux):** Typical agricultural lighting.
* **Scans 38–40 (Direct Sunlight Glare, ~1,000 lux):** High-contrast specular highlights.

### Condition Set 5: Boundary & Adversarial Uncertainty Gating Controls (Scans 41–50)
*Setup: Non-foliar and out-of-distribution surfaces presented to the camera lens.*
* **Scans 41–42 (Lens Cap / All-Black Surface):** Foliar ratio = 0.00 (< 0.12). Expected: `UNCERTAIN (No Leaf Detected)`.
* **Scans 43–44 (Blank White Paper / Wall):** Foliar ratio = 0.00 (< 0.12). Expected: `UNCERTAIN (No Leaf Detected)`.
* **Scans 45–46 (Bare Dry Soil / Compost):** Foliar ratio < 0.08 (< 0.12). Expected: `UNCERTAIN (No Leaf Detected)`.
* **Scans 47–48 (Human Hand / Palm):** Expected: `UNCERTAIN (No Leaf Detected)`.
* **Scans 49–50 (Extreme Multi-Source Glare / Ambiguous Surface):** Expected entropy $H > 1.45$ nats. Expected: `UNCERTAIN (Low Confidence / Ambiguous)`.

---

## 4. 50-Condition Run Sheet

> [!NOTE]
> **Status of these trials:** The end-to-end software pipeline (8-specimen daemon verification and 60-specimen botanical benchmark) is covered by the automated suite in `tests/`. The 50 physical trials below have **not yet been recorded**; the table defines the pre-registered conditions and acceptance criteria to be filled in as each scan is executed on the physical wand.

| Scan # | Target Specimen | Test Condition / Variable | Expected Classification | Expected Status | Gating Action | Recorded Result |
| :---: | :--- | :--- | :--- | :---: | :--- | :---: |
| **01–05** | Tomato Healthy Leaf | Baseline (8–10 cm, 500 lux) | `Tomato Healthy` (>95%) | `OPTIMAL` | Accepted | *not recorded* |
| **06–10** | Tomato Late Blight Leaf | Baseline (8–10 cm, 500 lux) | `Tomato Late Blight` (>90%) | `SEVERE` | Accepted | *not recorded* |
| **11–12** | Tomato Healthy Leaf | 6 cm (Macro Close-Up) | `Tomato Healthy` (>85%) | `OPTIMAL` | Accepted | *not recorded* |
| **13–14** | Tomato Healthy Leaf | 10 cm (Optimal Spacer) | `Tomato Healthy` (>95%) | `OPTIMAL` | Accepted | *not recorded* |
| **15–16** | Tomato Late Blight Leaf | 10 cm (Optimal Spacer) | `Tomato Late Blight` (>95%) | `SEVERE` | Accepted | *not recorded* |
| **17–18** | Tomato Late Blight Leaf | 12 cm (Spacer Boundary) | `Tomato Late Blight` (>85%) | `SEVERE` | Accepted | *not recorded* |
| **19–20** | Tomato Healthy Leaf | 15 cm (Extended Distance) | `Tomato Healthy` (>80%) | `OPTIMAL` | Accepted | *not recorded* |
| **21–23** | Tomato Healthy Leaf | 15° Off-Axis Tilt | `Tomato Healthy` (>90%) | `OPTIMAL` | Accepted | *not recorded* |
| **24–27** | Tomato Late Blight Leaf | 30° Off-Axis Tilt | `Tomato Late Blight` (>85%) | `SEVERE` | Accepted | *not recorded* |
| **28–30** | Tomato Healthy Leaf | 45° Steep Oblique Tilt | `Tomato Healthy` / Gated | `OPTIMAL`/`UNCERTAIN` | Accepted / Safe Gate | *not recorded* |
| **31–33** | Tomato Late Blight Leaf | Deep Shade (100 lux + Flash) | `Tomato Late Blight` (>85%) | `SEVERE` | Accepted | *not recorded* |
| **34–37** | Tomato Healthy Leaf | Diffuse Daylight (400 lux) | `Tomato Healthy` (>95%) | `OPTIMAL` | Accepted | *not recorded* |
| **38–40** | Tomato Late Blight Leaf | Bright Ambient (1,000 lux) | `Tomato Late Blight` (>85%) | `SEVERE` | Accepted | *not recorded* |
| **41–42** | Lens Cap (All-Black) | Zero Lux / Occluded | `No Leaf Detected` (0.0%) | `UNCERTAIN` | **REJECTED (Foliar Gate)** | *not recorded* |
| **43–44** | Blank White Paper | Non-Foliar Background | `No Leaf Detected` (0.0%) | `UNCERTAIN` | **REJECTED (Foliar Gate)** | *not recorded* |
| **45–46** | Bare Dry Soil | Agricultural Ground Control | `No Leaf Detected` (0.0%) | `UNCERTAIN` | **REJECTED (Foliar Gate)** | *not recorded* |
| **47–48** | Human Palm | Skin Cuticle Control | `No Leaf Detected` (0.0%) | `UNCERTAIN` | **REJECTED (Foliar Gate)** | *not recorded* |
| **49–50** | Extreme Glare / Ambiguous | Specular Highlight Glare | `Uncertain / Ambiguous` (<50%) | `UNCERTAIN` | **REJECTED (Entropy Gate)** | *not recorded* |

---

## 5. Reporting the Results

Report each condition set as a pass/fail against the acceptance criteria in the run sheet, and record:

1. **Repeatability:** per-scan prediction, confidence, and entropy for each trial, so within-condition variance is visible.
2. **Gate behaviour:** which frames were accepted, and which were rejected by the foliar-ratio gate versus the entropy gate.
3. **Domain shift disclosure:** classification accuracy on controlled indoor specimens is not an outdoor field metric. The measured outdoor figure is the PlantDoc held-out result in `tests/plantdoc_benchmark_audit.json`, and it is substantially lower than the controlled-set figure. Gating exists because that drop is real, not to hide it.
