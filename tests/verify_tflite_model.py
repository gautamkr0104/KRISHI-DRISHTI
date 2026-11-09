"""
KRISHI-DRISHTI :: Independent TFLite Model & Runtime Verification Suite
----------------------------------------------------------------------
Inspects model tensors, verifies input/output contracts, tests numerical
stability, and executes inference on all sample leaves.

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
AI_ENGINE_DIR = os.path.join(REPO_ROOT, "ai_engine")
MODEL_PATH = os.path.join(AI_ENGINE_DIR, "krishi_drishti_model.tflite")
LABELS_PATH = os.path.join(AI_ENGINE_DIR, "labels.json")
SAMPLE_DIR = os.path.join(AI_ENGINE_DIR, "sample_leaves")
AUDIT_OUT_PATH = os.path.join(REPO_ROOT, "tests", "tflite_model_verification_audit.json")

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    print("=" * 70)
    print("KRISHI-DRISHTI :: TFLITE MODEL & TENSOR VERIFICATION AUDIT")
    print("=" * 70)

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
    Interpreter = None
    try:
        import tflite_runtime.interpreter as tflite
        Interpreter = tflite.Interpreter
        interpreter_lib = "tflite-runtime"
    except ImportError:
        try:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter
            interpreter_lib = f"TensorFlow {tf.__version__}"
        except ImportError:
            print("\n[!] Neither tflite-runtime nor tensorflow is installed.")
            print("    To run live inference verification, install tflite-runtime or tensorflow:")
            print("      pip install tflite-runtime")
            print("      or")
            print("      pip install tensorflow")
            sys.exit(1)

    print(f"[OK] Runtime Backend: {interpreter_lib}")

    # Load labels
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels_data = json.load(f)
    classes = [f"{c['crop']} {c['disease']}" for c in labels_data]

    # Initialize interpreter
    t0 = time.perf_counter()
    interpreter = Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    init_latency_ms = (time.perf_counter() - t0) * 1000.0
    print(f"[OK] Tensor allocation succeeded in {init_latency_ms:.2f} ms")

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    inp = input_details[0]
    outp = output_details[0]

    input_shape = inp['shape'].tolist()
    input_dtype = str(inp['dtype'])
    output_shape = outp['shape'].tolist()
    output_dtype = str(outp['dtype'])

    print("\n--- Tensor Details ---")
    print(f"  Input Tensor:  Name='{inp['name']}'")
    print(f"                 Shape={input_shape}, Dtype={input_dtype}")
    print(f"                 Quantization={inp.get('quantization')}")
    print(f"  Output Tensor: Name='{outp['name']}'")
    print(f"                 Shape={output_shape}, Dtype={output_dtype}")
    print(f"                 Quantization={outp.get('quantization')}")

    # Assertions
    assert input_shape == [1, 128, 128, 3], f"Unexpected input shape: {input_shape}"
    assert output_shape == [1, 6], f"Unexpected output shape: {output_shape}"

    # Verify synthetic distribution
    dummy = np.full((1, 128, 128, 3), 128.0, dtype=np.float32)
    interpreter.set_tensor(inp['index'], dummy)
    interpreter.invoke()
    dummy_out = interpreter.get_tensor(outp['index'])[0]
    prob_sum = float(np.sum(dummy_out))
    assert abs(prob_sum - 1.0) < 1e-3, f"Softmax sum violated: {prob_sum}"
    print(f"\n[OK] Softmax Probability Sum Validation: {prob_sum:.6f} (Passed: sum == 1.0)")

    # Execute inference on sample leaves
    print("\n--- Executing Live Inference on Sample Foliage ---")
    image_files = sorted([f for f in os.listdir(SAMPLE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    
    sample_results = []
    for fname in image_files:
        fpath = os.path.join(SAMPLE_DIR, fname)
        pil_img = Image.open(fpath).convert("RGB").resize((128, 128), Image.BILINEAR)
        arr = np.array(pil_img, dtype=np.float32)
        tensor = np.expand_dims(arr, 0)

        t_start = time.perf_counter()
        interpreter.set_tensor(inp['index'], tensor)
        interpreter.invoke()
        probs = interpreter.get_tensor(outp['index'])[0]
        lat_ms = (time.perf_counter() - t_start) * 1000.0

        top_idx = int(np.argmax(probs))
        top_prob = float(probs[top_idx])

        # Shannon Entropy
        entropy = -float(sum(p * np.log(p) for p in probs if p > 1e-6))

        result_entry = {
            "filename": fname,
            "predicted_class": classes[top_idx],
            "confidence_pct": round(top_prob * 100.0, 2),
            "shannon_entropy": round(entropy, 4),
            "latency_ms": round(lat_ms, 2),
            "probabilities": {classes[i]: round(float(probs[i]) * 100.0, 2) for i in range(len(classes))}
        }
        sample_results.append(result_entry)

        print(f"  • {fname:24s} -> {classes[top_idx]:22s} ({top_prob*100.0:5.1f}%) | Entropy: {entropy:.2f} | Latency: {lat_ms:.2f}ms")

    # Save comprehensive verification audit
    audit = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_file": os.path.basename(MODEL_PATH),
        "file_size_bytes": file_size,
        "sha256": sha256_hash,
        "runtime_backend": interpreter_lib,
        "tensors": {
            "input": {
                "name": inp['name'],
                "shape": input_shape,
                "dtype": input_dtype,
                "quantization": str(inp.get('quantization'))
            },
            "output": {
                "name": outp['name'],
                "shape": output_shape,
                "dtype": output_dtype,
                "quantization": str(outp.get('quantization'))
            }
        },
        "softmax_sum_check": round(prob_sum, 6),
        "softmax_check_status": "PASSED",
        "sample_evaluations": sample_results
    }

    with open(AUDIT_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)

    print(f"\n[OK] Verification audit report written to: {AUDIT_OUT_PATH}")
    print("=" * 70)
    print("ALL MODEL TENSOR CONTRACT CHECKS & REAL INFERENCE EXECUTIONS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    main()
