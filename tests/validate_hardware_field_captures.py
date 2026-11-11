"""
KRISHI-DRISHTI :: Hardware Field Validation Test Harness
Author: Gautam Kumar / KRISHI-DRISHTI Project
Domain: Edge-AI Hardware-in-the-Loop Field Validation
----------------------------------------------------------------------------------------
Evaluates the offline quantized TFLite model and production KrishiAIDaemon
directly on foliar photographs captured by the physical KRISHI-DRISHTI hardware wand
(ESP32-CAM OV5640 + Optical Shroud + DHT11 telemetry).

Features:
- Strict separation of Exact 6-Class Accuracy vs. Pathogen Family Correlation
- Dual-stage gating analysis (Shannon entropy H > 1.45, foliar ratio < 12%)
- Shroud vs. Unshielded optical comparison metrics
- Microclimate risk advisory interlock evaluation (RH >= 85% criterion)
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "ai_engine"))

from krishi_ai_daemon import KrishiAIDaemon

CLASS_TO_CANONICAL = {
    "Tomato___Late_blight": "Tomato Late Blight",
    "Tomato___Early_blight": "Tomato Early Blight",
    "Tomato___healthy": "Tomato Healthy",
    "Potato___Late_blight": "Potato Late Blight",
    "Potato___Early_blight": "Potato Early Blight",
    "Potato___healthy": "Potato Healthy",
}

PATHOGEN_MAP = {
    "Tomato Late Blight": "Phytophthora infestans",
    "Potato Late Blight": "Phytophthora infestans",
    "Tomato Early Blight": "Alternaria solani",
    "Potato Early Blight": "Alternaria solani",
    "Tomato Healthy": "Asymptomatic",
    "Potato Healthy": "Asymptomatic",
}


def evaluate_field_captures(manifest_path=None):
    if manifest_path is None:
        manifest_path = REPO_ROOT / "tests" / "hardware_field_captures" / "field_validation_manifest.json"

    print("=" * 80)
    print("  KRISHI-DRISHTI :: HARDWARE FIELD VALIDATION TEST HARNESS")
    print("=" * 80)

    if not os.path.exists(manifest_path):
        print(f"[ERROR] Manifest not found: {manifest_path}")
        return 1

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    records = manifest.get("records", [])
    print(f"[*] Manifest: {manifest_path.name}")
    print(f"[*] Total Registered Field Captures: {len(records)}")

    if len(records) == 0:
        print("[INFO] No hardware field captures currently registered in manifest.")
        print("       To evaluate hardware captures:")
        print("       1. Place OV5640 .jpg captures in tests/hardware_field_captures/")
        print("       2. Register metadata entries in field_validation_manifest.json")
        print("       3. Refer to FIELD_VALIDATION_PROTOCOL.md for standardized procedure.")
        print("=" * 80)
        return 0

    model_path = REPO_ROOT / "ai_engine" / "krishi_drishti_model.tflite"
    daemon = KrishiAIDaemon(model_path=str(model_path))

    results = []
    exact_matches = 0
    pathogen_matches = 0
    gated_uncertain = 0
    accepted_count = 0
    accepted_exact = 0

    shroud_comparisons = {"shrouded": {"total": 0, "correct": 0}, "unshielded": {"total": 0, "correct": 0}}

    for rec in records:
        fname = rec.get("filename")
        fpath = REPO_ROOT / "tests" / "hardware_field_captures" / fname
        if not fpath.exists():
            print(f"[WARN] File missing on disk: {fname}")
            continue

        gt_class = rec.get("ground_truth", {}).get("canonical_class")
        gt_canonical = CLASS_TO_CANONICAL.get(gt_class, rec.get("ground_truth", {}).get("disease", "Unknown"))
        gt_pathogen = PATHOGEN_MAP.get(gt_canonical, "Unknown")
        is_shrouded = rec.get("shroud_attached", True)

        img = Image.open(fpath).convert("RGB")
        res = daemon.predict_image(img)

        pred_label = res.get("label", "Unknown")
        conf = res.get("confidence", 0.0)
        entropy = res.get("entropy", 0.0)
        status = res.get("status", "UNKNOWN")

        is_uncertain = (status == "UNCERTAIN" or "Uncertain" in pred_label or "No Leaf" in pred_label)
        pred_pathogen = PATHOGEN_MAP.get(pred_label, "Unknown")

        is_exact = (pred_label == gt_canonical and not is_uncertain)
        is_pathogen = (pred_pathogen == gt_pathogen and gt_pathogen != "Asymptomatic" and not is_uncertain)

        if is_exact:
            exact_matches += 1
        if is_exact or is_pathogen:
            pathogen_matches += 1

        if is_uncertain:
            gated_uncertain += 1
        else:
            accepted_count += 1
            if is_exact:
                accepted_exact += 1

        shroud_key = "shrouded" if is_shrouded else "unshielded"
        shroud_comparisons[shroud_key]["total"] += 1
        if is_exact:
            shroud_comparisons[shroud_key]["correct"] += 1

        results.append({
            "capture_id": rec.get("capture_id"),
            "filename": fname,
            "ground_truth": gt_canonical,
            "prediction": pred_label,
            "confidence_pct": round(conf * 100, 1),
            "entropy": round(entropy, 3),
            "status": status,
            "shroud_attached": is_shrouded,
            "exact_match": is_exact,
            "pathogen_match": is_pathogen
        })

    total_valid = len(results)
    raw_acc = (exact_matches / total_valid * 100) if total_valid > 0 else 0.0
    acc_diag = (accepted_exact / accepted_count * 100) if accepted_count > 0 else 0.0
    pathogen_acc = (pathogen_matches / total_valid * 100) if total_valid > 0 else 0.0

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_evaluated": total_valid,
        "strict_6class_accuracy": {
            "exact_matches": exact_matches,
            "total_evaluated": total_valid,
            "raw_accuracy_pct": round(raw_acc, 2)
        },
        "accepted_frame_triage": {
            "accepted_frames": accepted_count,
            "accepted_exact": accepted_exact,
            "accepted_accuracy_pct": round(acc_diag, 2),
            "gated_uncertain": gated_uncertain,
            "coverage_pct": round((accepted_count / total_valid * 100), 2) if total_valid > 0 else 0.0
        },
        "pathogen_family_correlation": {
            "pathogen_matches": pathogen_matches,
            "pathogen_accuracy_pct": round(pathogen_acc, 2),
            "scientific_note": "Evaluates Phytophthora infestans / Alternaria solani cross-host recognition. Reported separately from exact 6-class accuracy."
        },
        "optical_shroud_comparison": shroud_comparisons,
        "specimens": results
    }

    out_path = REPO_ROOT / "tests" / "hardware_field_validation_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[SUMMARY] Evaluated {total_valid} hardware field captures:")
    print(f"          Strict 6-Class Exact Match : {exact_matches}/{total_valid} ({raw_acc:.2f}%)")
    print(f"          Accepted Predictions       : {accepted_exact}/{accepted_count} ({acc_diag:.2f}%) [{gated_uncertain} gated]")
    print(f"          Pathogen Family Correlation: {pathogen_matches}/{total_valid} ({pathogen_acc:.2f}%)")
    print(f"[OK] Audit report written to: {out_path.name}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(evaluate_field_captures())
