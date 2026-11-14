"""External validation v3 (round-3): FRESH unseen Wikimedia Commons images.

None of these images were used in v4 training (all 16 training supplements are
listed in field_supplements_manifest.json and verified distinct from these).
Strict labels below were hand-verified by viewing each image.
"""
import sys
import math
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai_engine"))
import krishi_ai_daemon as K

FRESH = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest\fresh_round3")
MODEL = Path(__file__).resolve().parent.parent / "ai_engine" / "krishi_drishti_model.tflite"
CLASS = ["Tomato___Late_blight", "Tomato___Early_blight", "Tomato___healthy",
         "Potato___Late_blight", "Potato___Early_blight", "Potato___healthy"]

# (file, expected_class_or_None, note) — None = report-only, excluded from score
TESTS = [
    ("fresh_tomato_early_blight_7871930010.jpg", "Tomato___Early_blight",
     "tomato leaf, early-blight target spots with yellow halos"),
    ("fresh_tomato_late_blight_sporulating.jpg", "Tomato___Late_blight",
     "tomato leaf, greasy late-blight necrosis"),
    ("fresh_potato_late_blight_field.jpg", "Potato___Late_blight",
     "potato leaf, classic late-blight lesion + white sporulation"),
    ("fresh_potato_healthy_micro_leaf.jpg", "Potato___healthy",
     "potato leaf macro (atypical extreme close-up; healthy tissue)"),
    ("fresh_potato_unidentified_disease.jpg", None,
     "potato leaf, ambiguous lesions (early vs late blight unclear) - report only"),
    ("fresh_tomato_late_blight_fruit.jpg", None,
     "tomato FRUIT with late blight - out of leaf domain, report only"),
    ("fresh_potato_early_blight_solani1.jpg", None,
     "tomato FRUIT with Alternaria lesions - out of leaf domain, report only"),
    ("fresh_potato_early_blight_solani2.jpg", None,
     "tomato FRUIT with Alternaria lesions - out of leaf domain, report only"),
    ("fresh_potato_healthy_evenjobb_field.jpg", None,
     "brown dying haulm field - not healthy foliage, report only"),
    ("fresh_potato_healthy_pitlethie.jpg", None,
     "brown dying haulm field - not healthy foliage, report only"),
    ("fresh_potato_healthy_emerging_foliage.jpg", None,
     "bare soil ridges, tiny seedlings - report only"),
]

interp = tf.lite.Interpreter(model_path=str(MODEL))
interp.allocate_tensors()
ind, outd = interp.get_input_details()[0], interp.get_output_details()[0]

print(f"{'image':44s} {'expected':22s} {'prediction':22s} {'conf':>6}  verdict")
print("-" * 108)
score, scored = 0, 0
rows = []
for fname, expected, note in TESTS:
    p = FRESH / fname
    if not p.exists():
        print(f"{fname:44s} MISSING FILE - skipped")
        continue
    img = Image.open(p)
    arr = np.asarray(img.convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
    interp.set_tensor(ind["index"], np.expand_dims(arr, 0))
    interp.invoke()
    pr = interp.get_tensor(outd["index"])[0].astype(np.float32)
    top = int(np.argmax(pr))
    pred, conf = CLASS[top], float(pr[top])
    if expected is None:
        verdict = "report-only"
    else:
        verdict = "OK" if pred == expected else "WRONG"
        scored += 1
        score += pred == expected
    rows.append({"image": fname, "expected": expected, "pred": pred,
                 "conf": conf, "verdict": verdict, "note": note})
    print(f"{fname[:44]:44s} {str(expected)[:22]:22s} {pred[:22]:22s} {conf * 100:5.1f}%  {verdict:6s}")

print(f"\nStrict in-domain score (fresh unseen): {score}/{scored}")
out = FRESH / "fresh_round3_results.json"
out.write_text(json.dumps({"rows": rows, "score": score, "scored": scored}, indent=1),
               encoding="utf-8")
print("wrote", out)
