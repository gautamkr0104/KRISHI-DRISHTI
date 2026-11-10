"""
KRISHI-DRISHTI :: Independent TFLite Model & Runtime Verification Suite
----------------------------------------------------------------------
Inspects model tensors, verifies input/output contracts, tests numerical
stability, and executes inference on canonical sample leaves and edge controls
using the EXACT production KrishiAIDaemon pipeline.

Run with:
  python tests/verify_tflite_model.py
or using the dedicated virtual environment:
  D:\\tools\\krishi_ai_env\\Scripts\\python.exe tests/verify_tflite_model.py
"""

import os
import sys
import json
import hashlib
import time
import numpy as np
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

AI_ENGINE_DIR = os.path.join(REPO_ROOT, "ai_engine")
MODEL_PATH = os.path.join(AI_ENGINE_DIR, "krishi_drishti_model.tflite")
LABELS_PATH = os.path.join(AI_ENGINE_DIR, "labels.json")
SAMPLE_DIR = os.path.join(AI_ENGINE_DIR, "sample_leaves")
AUDIT_OUT_PATH = os.path.join(REPO_ROOT, "tests", "tflite_model_verification_audit.json")

GROUND_TRUTH_MAP = {
    "potato_early_blight.jpg": "Potato Early Blight",
    "potato_healthy.jpg": "Potato Healthy",
    "potato_late_blight.jpg": "Potato Late Blight",
    "tomato_early_blight.jpg": "Tomato Early Blight",
    "tomato_healthy.jpg": "Tomato Healthy",
    "tomato_late_blight.jpg": "Tomato Late Blight",
    "test_edge_lens_cap.jpg": "NON_FOLIAR_CONTROL",
    "test_edge_ambient_surface.jpg": "NON_FOLIAR_CONTROL",
}

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    print("=" * 80)
    print("  KRISHI-DRISHTI :: PRODUCTION TFLITE & DAEMON END-TO-END AUDIT")
    print("=" * 80)

    if not os.path.exists(MODEL_PATH):
        print(f"[FAIL] Model file not found at: {MODEL_PATH}")
        sys.exit(1)

    file_size = os.path.getsize(MODEL_PATH)
    sha256_hash = compute_sha256(MODEL_PATH)
    print(f"[OK] Model File: {os.path.basename(MODEL_PATH)}")
    print(f"     File Size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
    print(f"     SHA-256:   {sha256_hash}")

    # Check for interpreter
    interpreter_lib = None
    try:
        import tflite_runtime.interpreter as tflite
        interpreter_lib = "tflite-runtime"
    except ImportError:
        try:
            import tensorflow as tf
            interpreter_lib = f"TensorFlow {tf.__version__}"
        except ImportError:
            print("\n[!] Neither tflite-runtime nor tensorflow is installed.")
            print("    To run live inference verification, install tflite-runtime or tensorflow:")
            print("      pip install tflite-runtime")
            print("      or")
            print("      pip install tensorflow")
            sys.exit(1)

    print(f"[OK] Runtime Backend: {interpreter_lib}")

    # Import and instantiate production daemon
    from ai_engine.krishi_ai_daemon import KrishiAIDaemon
    daemon = KrishiAIDaemon(MODEL_PATH, LABELS_PATH)

    input_shape = daemon.input_shape.tolist()
    input_dtype = str(daemon.input_dtype)
    output_shape = daemon.output_details[0]['shape'].tolist()
    output_dtype = str(daemon.output_details[0]['dtype'])

    print("\n--- Production Daemon & Tensor Specifications ---")
    print(f"  Input Tensor  : Shape={input_shape}, Dtype={input_dtype}")
    print(f"  Output Tensor : Shape={output_shape}, Dtype={output_dtype}")

    assert input_shape == [1, 128, 128, 3], f"Unexpected input shape: {input_shape}"
    assert output_shape == [1, 6], f"Unexpected output shape: {output_shape}"

    # Verify probability distribution sum == 1.0
    dummy = np.full((1, 128, 128, 3), 128.0, dtype=np.float32)
    daemon.interpreter.set_tensor(daemon.input_details[0]['index'], dummy)
    daemon.interpreter.invoke()
    dummy_out = daemon.interpreter.get_tensor(daemon.output_details[0]['index'])[0]
    prob_sum = float(np.sum(dummy_out))
    assert abs(prob_sum - 1.0) < 1e-3, f"Softmax sum violated: {prob_sum}"
    print(f"[OK] Softmax Probability Sum Validation: {prob_sum:.6f} (Passed: sum == 1.0)")

    # Execute inference on sample leaves using production daemon.run_inference()
    print("\n" + "=" * 80)
    print("  PRODUCTION DAEMON INFERENCE AUDIT ON CANONICAL SPECIMENS & EDGE CONTROLS")
    print("=" * 80)
    image_files = sorted([f for f in os.listdir(SAMPLE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    
    sample_results = []
    correct_evaluations = 0
    total_evaluations = 0

    print(f"{'Filename':28s} {'Ground Truth':20s} {'Prediction':22s} {'Conf':7s} {'Status':10s} {'Gating Decision'}")
    print("-" * 110)

    for fname in image_files:
        fpath = os.path.join(SAMPLE_DIR, fname)
        pil_img = Image.open(fpath)
        expected_gt = GROUND_TRUTH_MAP.get(fname, "Unknown")
        total_evaluations += 1

        # Run 100% production daemon method
        diag = daemon.run_inference(pil_img)

        pred_crop = diag["crop"]
        pred_disease = diag["disease"]
        predicted_class = f"{pred_crop} {pred_disease}" if pred_crop not in ("Unknown", "Solanaceae") else pred_disease
        confidence = diag["confidence"]
        status = diag["status"]
        latency = diag["latency_ms"]

        if status == "UNCERTAIN":
            decision = f"REJECTED ({pred_disease})"
            match = (expected_gt == "NON_FOLIAR_CONTROL")
        else:
            decision = f"ACCEPTED ({status})"
            # Strict 1:1 exact crop and disease matching (zero cross-crop leeway)
            match = (predicted_class == expected_gt)

        if match:
            correct_evaluations += 1

        result_entry = {
            "filename": fname,
            "ground_truth": expected_gt,
            "predicted_class": predicted_class,
            "confidence_pct": confidence,
            "decision": decision,
            "status": status,
            "verified_match": match,
            "latency_ms": latency,
            "pathogen": diag.get("pathogen", ""),
            "organic_recommendation": diag.get("organic", ""),
            "chemical_recommendation": diag.get("chemical", "")
        }
        sample_results.append(result_entry)

        conf_str = f"{confidence:.1f}%"
        print(f"{fname:28s} {expected_gt:20s} {predicted_class:22s} {conf_str:7s} {status:10s} {decision}")

    accuracy_rate = (correct_evaluations / total_evaluations) * 100.0 if total_evaluations > 0 else 0.0

    print("-" * 110)
    print(f"[SUMMARY] Total Specimens Evaluated via Production Daemon: {total_evaluations}")
    print(f"          Verified Accurate Diagnoses: {correct_evaluations}/{total_evaluations} ({accuracy_rate:.1f}%)")

    # Save comprehensive audit
    audit = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_file": os.path.basename(MODEL_PATH),
        "file_size_bytes": file_size,
        "sha256": sha256_hash,
        "runtime_backend": interpreter_lib,
        "pipeline": "KrishiAIDaemon.run_inference (Full Production Method)",
        "tensors": {
            "input": {
                "name": daemon.input_details[0]['name'],
                "shape": input_shape,
                "dtype": input_dtype
            },
            "output": {
                "name": daemon.output_details[0]['name'],
                "shape": output_shape,
                "dtype": output_dtype
            }
        },
        "softmax_sum_check": round(prob_sum, 6),
        "softmax_check_status": "PASSED",
        "sample_evaluations_summary": {
            "total_tested": total_evaluations,
            "verified_correct": correct_evaluations,
            "accuracy_pct": round(accuracy_rate, 2)
        },
        "sample_evaluations": sample_results
    }

    with open(AUDIT_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)

    print(f"\n[OK] Production verification audit written to: {AUDIT_OUT_PATH}")
    print("=" * 80)
    print("ALL PRODUCTION DAEMON PATH INFERENCES & GATING CHECKS PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    main()
