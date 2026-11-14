"""Round-3 external validation: 100 totally-new images found via Bing image search
in the user's Edge browser (browse extension relay, session cosmic-badger-684).

- 569 unique image URLs harvested across 14 queries covering all 6 classes.
- Downloaded, deduped by exact SHA-256 against ALL 40 prior web-test images
  (webtest/ + fresh_round3/), plus within-set dedupe by 64x64 pixel hash.
- 120 candidates survived; 9 visually rejected from contact-sheet review
  (montages/collages, paper figures, ambiguous lesions) by the operator.
- Final set: 17 per class = 102 images. Ground truth = the search-query label.
"""
import sys, json, math, os
from pathlib import Path
import numpy as np
from PIL import Image

REPO = Path(r"C:\Users\DELL\Downloads\KRISHI-DRISHTI")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(REPO / "ai_engine"))
import tensorflow as tf
from krishi_ai_daemon import KrishiAIDaemon

BASE = Path(r"C:\Users\DELL\Documents\Default Project\webtest100")
IMGDIR = BASE / "images"
MODEL = REPO / "ai_engine" / "krishi_drishti_model.tflite"
LABELS = REPO / "ai_engine" / "labels.json"
CLASS = ["Tomato___Late_blight", "Tomato___Early_blight", "Tomato___healthy",
         "Potato___Late_blight", "Potato___Early_blight", "Potato___healthy"]

DROP = {
    "Tomato___Late_blight__019.jpg",  # multi-panel disease collage
    "Tomato___Late_blight__009.jpg",  # shot-holes, ambiguous
    "Tomato___Late_blight__010.jpg",  # tip necrosis, ambiguous
    "Tomato___Early_blight__019.jpg", # stem in pocket, not a leaf
    "Tomato___Early_blight__001.jpg", # ambiguous large lesion
    "Potato___Late_blight__019.jpg",  # labeled montage grid
    "Potato___Late_blight__013.jpg",  # concentric lesion, ambiguous
    "Potato___Early_blight__011.jpg", # paper figure (a)(b)(c)
    "Potato___Early_blight__014.jpg", # montage grid
    "Potato___Early_blight__017.jpg", # paper figure "(b)"
}

cands = json.load(open(BASE / "candidates.json", encoding="utf-8"))
by_label = {}
for c in cands:
    if c["file"] in DROP:
        continue
    by_label.setdefault(c["label"], []).append(c)

final = []
for label, items in sorted(by_label.items()):
    final.extend(items[:17])
final.sort(key=lambda c: c["file"])
print(f"final test set: {len(final)} images")
counts = {}
for c in final:
    counts[c["label"]] = counts.get(c["label"], 0) + 1
print("per class:", counts)

interp = tf.lite.Interpreter(model_path=str(MODEL))
interp.allocate_tensors()
ind, outd = interp.get_input_details()[0], interp.get_output_details()[0]
daemon = KrishiAIDaemon(model_path=str(MODEL), labels_path=str(LABELS))

rows = []
raw_score, raw_n = 0, 0
acc_score, acc_n = 0, 0
confusion = {}
for c in final:
    p = IMGDIR / c["file"]
    img = Image.open(p)
    # --- raw argmax path (128x128 bilinear, raw [0,255]) ---
    arr = np.asarray(img.convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
    interp.set_tensor(ind["index"], np.expand_dims(arr, 0))
    interp.invoke()
    pr = interp.get_tensor(outd["index"])[0].astype(np.float32)
    top = int(np.argmax(pr))
    raw_pred, raw_conf = CLASS[top], float(pr[top])
    raw_ok = raw_pred == c["label"]
    raw_n += 1
    raw_score += raw_ok
    # --- production daemon gate pipeline ---
    res = daemon.run_inference(img)
    status = res.get("status", "")
    accepted = status not in ("UNCERTAIN",)
    d_pred = res.get("disease", "")
    d_crop = res.get("crop", "")
    d_conf = res.get("confidence", 0.0)
    exp_crop, exp_dis = c["label"].split("___")
    exp_dis = exp_dis.replace("_", " ")  # "Late_blight" -> "Late blight"
    d_ok = accepted and d_crop == exp_crop and d_pred.lower() == exp_dis.lower()
    if accepted:
        acc_n += 1
        acc_score += d_ok
    key = (c["label"], raw_pred)
    confusion[key] = confusion.get(key, 0) + 1
    rows.append({
        "file": c["file"], "expected": c["label"], "query": c["query"],
        "raw_pred": raw_pred, "raw_conf": round(raw_conf, 4), "raw_ok": raw_ok,
        "daemon_status": status, "daemon_pred": f"{d_crop} {d_pred}", "daemon_conf": d_conf,
        "daemon_accepted": accepted, "daemon_ok": d_ok,
    })

accepted_rows = [r for r in rows if r["daemon_accepted"]]
print(f"\n=== RAW ARGMAX: {raw_score}/{raw_n} = {100.0 * raw_score / raw_n:.1f}% ===")
print(f"=== DAEMON accepted: {acc_n}/{len(rows)} images passed gates; accepted-accuracy {acc_score}/{acc_n} ===")
uncertain = [r for r in rows if not r["daemon_accepted"]]
print(f"uncertain/rejected: {len(uncertain)}")
for r in uncertain:
    print("   REJ", r["file"], "->", r["daemon_pred"], round(r["daemon_conf"], 1))
print("\nper-class raw accuracy:")
for cls in CLASS:
    sub = [r for r in rows if r["expected"] == cls]
    ok = sum(r["raw_ok"] for r in sub)
    print(f"  {cls:24s} {ok}/{len(sub)}")

print("\nraw confusion (expected -> predicted):")
for cls in CLASS:
    line = " ".join(f"{confusion.get((cls, p), 0):3d}" for p in CLASS)
    print(f"  {cls:24s} {line}")

out = BASE / "webtest100_results.json"
out.write_text(json.dumps({
    "model_sha_source": "ai_engine/krishi_drishti_model.tflite (deployment fine-tuned v4)",
    "n": len(rows), "raw_score": raw_score, "daemon_accepted": acc_n,
    "daemon_accepted_score": acc_score, "rows": rows, "confusion": {f"{k[0]}->{k[1]}": v for k, v in confusion.items()},
}, indent=1), encoding="utf-8")
print("wrote", out)
