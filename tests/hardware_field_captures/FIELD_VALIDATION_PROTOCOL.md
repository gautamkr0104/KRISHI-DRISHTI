# KRISHI-DRISHTI — Hardware Field Validation Protocol

**Author:** Gautam Kumar / KRISHI-DRISHTI Engineering Team  
**Focus:** Standardized protocol for evaluating end-to-end diagnostic accuracy, optical shroud effectiveness, and microclimate risk advisory logic on authentic foliar photographs captured directly by the KRISHI-DRISHTI hardware wand.

---

## 1. Objective & Scientific Rationale

While public benchmarks (such as PlantVillage and PlantDoc) and curated open-web imagery provide useful developmental baselines, they do not answer the ultimate scientific question of edge agritech:

> **"Does the edge AI model perform reliably on the actual optical representations produced by its own low-cost sensor under genuine field conditions?"**

The KRISHI-DRISHTI hardware pipeline utilizes an **OV5640 5MP sensor on an ESP32-CAM module**, fitted with an **8–10 cm 3D-printed cylindrical optical shroud** and complemented by an **on-board DHT11 microclimate sensor**. 

This protocol establishes the rigorous, repeatable procedure for acquiring, labelling, and evaluating authentic field captures.

---

## 2. Experimental Data Collection Protocol

### 2.1 Hardware Configuration
1. **Camera Sensor:** AI-Thinker ESP32-CAM (OV5640 5MP CMOS sensor, default 65° FOV).
2. **Firmware:** `KRISHI_DRISHTI_Camera.ino` with SD_MMC 1-bit high-speed logging.
3. **Image Acquisition Resolution:** UXGA ($1600 \times 1200$, JPEG quality: 10–12).
4. **Illumination & Macro Shroud:**
   * **Test Condition A (Standard Shrouded):** 8–10 cm cylindrical black baffle placed flush against the target leaf surface. LED flash enabled in dim/shaded canopies.
   * **Test Condition B (Unshielded Baseline):** Shroud detached, held at approximately 8–15 cm under ambient daylight to measure ambient shadow degradation.
5. **Microclimate Telemetry:** Controller wand DHT11 sensor records instantaneous Temperature ($^\circ\text{C}$) and Relative Humidity ($\%$) at the exact second of frame acquisition.

### 2.2 Target Field Categories & Sampling Strategy
To ensure statistical validity without selection bias, field sampling should cover:
* **Target Crops:** Tomato (*Solanum lycopersicum*) and Potato (*Solanum tuberosum*).
* **Target Pathologies (6-Class Taxonomy):**
  1. `Tomato___Late_blight` (*Phytophthora infestans*)
  2. `Tomato___Early_blight` (*Alternaria solani*)
  3. `Tomato___healthy` (Asymptomatic foliar canopy)
  4. `Potato___Late_blight` (*Phytophthora infestans*)
  5. `Potato___Early_blight` (*Alternaria solani*)
  6. `Potato___healthy` (Asymptomatic foliar canopy)
* **Out-of-Distribution (OOD) Controls:**
  * Common weed foliage (e.g., *Parthenium hysterophorus*, *Chenopodium album*).
  * Non-Solanaceae crop leaves (e.g., Mustard, Hibiscus, Tea).
  * Bare agricultural soil, mulching plastic, and farmer hands.

### 2.3 Independent Ground Truth Verification
To prevent the label noise endemic to crowdsourced web datasets:
1. Each collected leaf specimen must be assigned a unique `capture_id` (e.g., `FIELD_TOM_LB_001`).
2. Primary ground truth must be determined by a qualified agricultural extension officer, plant pathologist, or verified via microscopic / lesion progression follow-up.
3. Both the raw uncompressed JPEG and its metadata record must be archived.

---

## 3. Metadata Schema (`field_validation_manifest.json`)

Each captured image must be logged in the JSON manifest with the following schema:

```json
{
  "capture_id": "FIELD_TOM_LB_001",
  "filename": "FIELD_TOM_LB_001.jpg",
  "timestamp": "2026-11-15T09:30:00Z",
  "hardware_id": "WAND_REV3_UNIT01",
  "sensor": "OV5640_5MP",
  "shroud_attached": true,
  "lighting": "shrouded_ambient",
  "telemetry": {
    "temperature_c": 21.4,
    "relative_humidity_pct": 88.5
  },
  "ground_truth": {
    "crop": "Tomato",
    "disease": "Late Blight",
    "canonical_class": "Tomato___Late_blight",
    "pathogen": "Phytophthora infestans",
    "verified_by": "Agricultural Extension Officer"
  }
}
```

---

## 4. Evaluation Metrics & Scientific Criteria

Field evaluation distinguishes between exact model classification and biological pathogen correlation:

1. **Strict 6-Class Accuracy:**
   $$\text{Exact Match} = \mathbb{I}(\hat{y} = y)$$
   A prediction is counted as correct *only* if both crop and disease match exactly.

2. **Pathogen Family Correlation:**
   Evaluates whether the neural network correctly identifies the causal agent family (*Phytophthora infestans* or *Alternaria solani*), even if the host crop is cross-predicted (e.g., Tomato Late Blight predicted as Potato Late Blight). Reported as secondary biological correlation, **never conflated with exact 6-class accuracy**.

3. **Dual-Stage Gating Efficacy:**
   * **Foliar Plausibility Gate:** Rejection of non-leaf objects ($< 12\%$ foliar pigmentation).
   * **Shannon Information Entropy Gate:** Gating of ambiguous frames ($H > 1.45$ nats or $p_{\max} < 0.50$).
   * **Reporting:** Both **Raw Baseline Accuracy** (all captures) and **Accepted Diagnostic Accuracy** (accepted frames only) must be reported alongside coverage percentage.

4. **Microclimate Advisory Interlock Validation:**
   Verifies whether the agronomic recommendation engine properly cross-references DHT11 Relative Humidity ($< 85\%$ vs $\ge 85\%$) to suppress unnecessary chemical fungicide sprays.

---

## 5. Automated Execution

To run the field evaluation harness once captures are populated:

```bash
python tests/validate_hardware_field_captures.py
```
