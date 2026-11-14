"""External validation v2: fixed scoring + raw probabilities for transparency."""
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

WEBTEST = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
MODEL = Path(__file__).resolve().parent.parent / "ai_engine" / "krishi_drishti_model.tflite"
CLASS = ["Tomato___Late_blight", "Tomato___Early_blight", "Tomato___healthy",
         "Potato___Late_blight", "Potato___Early_blight", "Potato___healthy"]

TESTS = [
    ("Tomato_leaf.jpg", "Tomato___healthy"),
    ("Potato_leaves.jpg", "Potato___healthy"),
    ("Late_blight_on_tomato_leaf_7871756748.jpg", "Tomato___Late_blight"),
    ("Tomato_late_blight_leaf_curl_2_5816171413.jpg", "Tomato___Late_blight"),
    ("Alternaria_solani_-_leaf_lesions.jpg", "Tomato___Early_blight"),
    ("Late_blight_on_potato_leaf_2.jpg", "Potato___Late_blight"),
    ("Phytophthora_infestans_on_potato_leaf.jpg", "Potato___Late_blight"),
    ("Pepper_infected_with_the_tomato_chlorotic_spot_virus_TCSV_used_by_U_S_Department", None),
]

interp = tf.lite.Interpreter(model_path=str(MODEL))
interp.allocate_tensors()
ind, outd = interp.get_input_details()[0], interp.get_output_details()[0]

print(f"{'image':44s} {'expected':22s} {'prediction':22s} {'conf':>6}  gates")
print("-" * 108)
score, scored = 0, 0
rows = []
for fname, expected in TESTS:
    p = WEBTEST / fname
    if not p.exists():
        continue
    img = Image.open(p)
    # raw model output (square-crop like the browser engine? daemon uses plain resize)
    arr = np.asarray(img.convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
    interp.set_tensor(ind["index"], np.expand_dims(arr, 0))
    interp.invoke()
    pr = interp.get_tensor(outd["index"])[0].astype(np.float32)
    top = int(np.argmax(pr))
    # daemon pipeline (gates + same model)
    res = K.KrishiAIDaemon.__new__(K.KrishiAIDaemon)
    res.input_dtype = np.float32
    tensor, foliar = K.KrishiAIDaemon.preprocess_image(res, img)
    if tensor is None:
        gates = f"foliar={foliar:.2f} GATED-OUT"
        shown = f"-> {res2 if False else ''}UNCERTAIN"
        pred, conf = "REJECTED", 0.0
    else:
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        dark = float(np.mean((r < 35) & (g < 35) & (b < 35)))
        gates = f"foliar={foliar:.2f} dark={dark:.2f} pass"
        sp = np.sort(pr)[::-1]
        margin = float(sp[0] - sp[1])
        ent = -float(sum(x * math.log(x) for x in pr if x > 1e-6))
        okp = (float(pr[top]) >= K.MIN_CONFIDENCE_THRESHOLD and ent <= K.MAX_ENTROPY_THRESHOLD and margin >= K.MIN_DECISION_MARGIN)
        gates += f" | conf={float(pr[top]):.2f} marg={margin:.2f} ent={ent:.2f} {'pass' if okp else 'GATED'}"
        pred, conf = CLASS[top], float(pr[top])
    if expected is None:
        verdict = "OK (OOD)" if (tensor is None or conf < K.MIN_CONFIDENCE_THRESHOLD) else "WRONG (accepted as in-domain)"
    else:
        verdict = "OK" if pred == expected else "WRONG"
        scored += 1
        score += pred == expected
    rows.append({"image": fname, "expected": expected, "pred": pred, "conf": conf, "verdict": verdict})
    print(f"{fname[:44]:44s} {str(expected)[:22]:22s} {pred[:22]:22s} {conf * 100:5.1f}%  {verdict:6s}")
    print(f"{'':44s} {gates}")

print(f"\nIn-domain strict score: {score}/{scored}")
(Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest") / "internet_test_results.json").write_text(
    json.dumps(rows, indent=1), encoding="utf-8")
