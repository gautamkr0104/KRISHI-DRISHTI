"""Audit all SD-card scans through the production KrishiAIDaemon pipeline."""
import os, sys, json, time
import numpy as np
from PIL import Image

REPO_ROOT = r"C:\Users\DELL\Downloads\KRISHI-DRISHTI"
sys.path.insert(0, REPO_ROOT)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from ai_engine.krishi_ai_daemon import KrishiAIDaemon

SCAN_DIR = "E:/"
OUT = os.path.join(REPO_ROOT, "tests", "sd_card_scans_audit.json")

daemon = KrishiAIDaemon(os.path.join(REPO_ROOT, "ai_engine", "krishi_drishti_model.tflite"),
                        os.path.join(REPO_ROOT, "ai_engine", "labels.json"))

results = []
for i in range(1, 45):
    f = os.path.join(SCAN_DIR, f"scan_{i:06d}.jpg")
    if not os.path.exists(f):
        continue
    try:
        img = Image.open(f)
        res = daemon.run_inference(img)
        results.append({
            "scan": f"scan_{i:06d}.jpg",
            "crop": res["crop"],
            "disease": res["disease"],
            "confidence_pct": res["confidence"],
            "status": res["status"],
            "entropy": res.get("entropy"),
            "margin": res.get("margin"),
            "probabilities": res.get("probabilities"),
        })
        print(f"{res['scan'] if False else os.path.basename(f)}: {res['crop']:12s} | {res['disease']:28s} | {res['confidence']:5.1f}% | {res['status']}")
    except Exception as e:
        print(f"scan_{i:06d}.jpg: ERROR {e}")

with open(OUT, "w") as f:
    json.dump({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "model": "krishi_drishti_model.tflite (pre-v3)", "results": results}, f, indent=2)
print(f"\nSaved: {OUT}")
