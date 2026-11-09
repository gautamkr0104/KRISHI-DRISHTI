# KRISHI-DRISHTI — 50-Image Two-Leaf Repeatability Demonstration Protocol

**Author:** Gautam Kumar (Class IX)  
**Institution:** Udaan International School, Begusarai, Bihar  
**Purpose:** Standardized physical verification protocol to demonstrate edge diagnostic repeatability, focus stability, and sensor-to-phone synchronization to science fair judges.

---

## 1. Objective & Scientific Honesty

This demonstration is specifically designed to prove **system repeatability and hardware-in-the-loop reliability**, not to artificially claim 100% field generalization across unencountered crops. 

In a live judging environment, testing the wand repeatedly on two known physical specimens (or laminated high-resolution foliar reference targets) allows judges to directly verify:
1. **Camera Trigger & SD Logging:** Reliable 1600×1200 frame capture without file truncation.
2. **Wi-Fi Telemetry:** Non-blocking synchronization between ESP32 Controller, ESP32-CAM, and phone co-processor.
3. **Inference Consistency:** Low variance in predicted confidence scores under consistent lighting.
4. **Uncertainty Gating:** Automatic rejection when the wand is angled away from the leaf or subjected to excessive shadow.

---

## 2. Experimental Setup

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **Specimen A (Healthy)** | Solanaceae (Tomato) Healthy Foliage | Uniform green cuticle, zero necrotic lesions |
| **Specimen B (Symptomatic)** | Solanaceae (Tomato) Late Blight Target | Visible water-soaked dark lesions with chlorotic halos |
| **Focal Distance** | 8 cm – 12 cm | Maintained via wand positioning guide |
| **Lighting Environment** | Standard indoor exhibition lighting + onboard flash | Uniform lux |
| **Total Trials** | 50 Scans (25 Healthy + 25 Symptomatic) | Logged sequentially to MicroSD |

---

## 3. Recommended Judge Demonstration Run Sheet

| Scan # | Reference Leaf | Predicted Class | Confidence (%) | Status | Processing Latency | Match? |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **01 – 25** | **Tomato Healthy** | `Tomato___healthy` | Expected > 90% | `HEALTHY` | < 50 ms | Yes |
| **26 – 50** | **Tomato Late Blight** | `Tomato___Late_blight` | Expected > 85% | `INFECTED` | < 50 ms | Yes |
| **Test 51 (Edge Case)** | **Blank Paper / Hand** | `No Leaf Detected` | 0.0% | `UNCERTAIN` | Immediate | Correct Rejection |
| **Test 52 (Edge Case)** | **Extreme Shadow / Glare** | `Low Confidence` | < 50.0% (Entropy > 1.45) | `UNCERTAIN` | Immediate | Correct Rejection |

---

## 4. Key Talking Points for Judges

1. **Repeatability vs. Generalization:**
   > *"Respected judges, this 50-scan run sheet demonstrates the physical stability of our camera optics, DMA memory buffer, and TFLite execution. It shows that KRISHI-DRISHTI produces rock-solid, repeatable results on consistent leaf targets without firmware hangs or memory leaks."*

2. **Honesty on Domain Shift:**
   > *"While the lab validation accuracy across 14,249 images is 88.74%, real unaugmented outdoor field photos (PlantDoc) drop to 34.91%. That is why we added the Shannon Entropy safeguard (Test 52) to refuse uncertain diagnoses in the field rather than spraying wrong chemicals."*
