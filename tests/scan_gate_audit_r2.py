"""Round-2 gate audit: daemon foliar/dark heuristics + round-2 TFLite probs over all 44 SD scans."""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
import tensorflow as tf

REPO = Path(__file__).resolve().parent.parent
GT = json.loads((REPO / "tests" / "sd_scan_ground_truth.json").read_text(encoding="utf-8"))

kinds = {}
for cat, spec in GT["categories"].items():
    scans = spec.get("scans", {})
    if isinstance(scans, dict):
        for k, v in scans.items():
            kinds[int(k)] = f"{cat}:{v}" if not isinstance(v, dict) else cat
    elif isinstance(scans, list):
        for n in scans:
            kinds[int(n)] = cat

interp = tf.lite.Interpreter(model_path=str(REPO / "ai_engine" / "krishi_drishti_model.tflite"))
interp.allocate_tensors()
ind, outd = interp.get_input_details()[0], interp.get_output_details()[0]
CLASS = ["Tomato___Late_blight", "Tomato___Early_blight", "Tomato___healthy",
         "Potato___Late_blight", "Potato___Early_blight", "Potato___healthy"]

rows = []
for n in range(1, 45):
    p = Path(f"E:/scan_{n:06d}.jpg")
    if not p.exists():
        continue
    arr = np.asarray(Image.open(p).convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    is_foliar = ((g > r * 0.95) & (g > b * 1.05)) | ((r > 60) & (g > 50) & (b < 80))
    foliar = float(np.mean(is_foliar))
    dark = float(np.mean((r < 35) & (g < 35) & (b < 35)))
    interp.set_tensor(ind["index"], np.expand_dims(arr, 0))
    interp.invoke()
    pr = interp.get_tensor(outd["index"])[0].astype(np.float32)
    top = int(np.argmax(pr))
    conf = float(pr[top])
    sp = np.sort(pr)[::-1]
    margin = float(sp[0] - sp[1])
    ent = -float(sum(x * math.log(x) for x in pr if x > 1e-6))
    rows.append(dict(scan=n, kind=kinds.get(n, "?"), foliar=round(foliar, 3), dark=round(dark, 3),
                     pred=CLASS[top], conf=round(conf, 3), margin=round(margin, 3), ent=round(ent, 3)))

hdr = f"{'scan':>5} {'kind':40} {'foliar':>6} {'dark':>6} {'pred':24} {'conf':>6} {'marg':>6} {'ent':>6}"
print(hdr)
for x in rows:
    print(f"{x['scan']:>5} {x['kind']:40} {x['foliar']:>6.3f} {x['dark']:>6.3f} {x['pred']:24} "
          f"{x['conf']:>6.3f} {x['margin']:>6.3f} {x['ent']:>6.3f}")

Path.home().joinpath("scan_gate_stats.json")
out = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\scan_gate_stats.json")
out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print("saved:", out)

# Full-gate evaluation helper: daemon order = dark -> foliar -> conf/entropy/margin
def full_gate(row, min_conf, max_ent, min_marg, min_foliar, max_dark):
    if row["dark"] > max_dark:
        return "REJ_DARK"
    if row["foliar"] < min_foliar:
        return "REJ_FOLIAR"
    if row["conf"] < min_conf or row["ent"] > max_ent or row["margin"] < min_marg:
        return "REJ_PROB"
    return "ACCEPT"

hw_kinds = ("screen_pseudo", "direct_forced_healthy", "direct_pseudo_44")
hw = [x for x in rows if x["kind"].split(":")[0] in ("screen_leaf_diseased", "direct_leaf")
      and not x["kind"].endswith(":discard")]
nonleaf = [x for x in rows if x["kind"].startswith("non_leaf_noise")]
mixed = [x for x in rows if x["kind"].startswith("mixed_outdoor")]

print(f"\nhardware scans: {len(hw)}  non-leaf: {len(nonleaf)}  mixed: {len(mixed)}")

best = None
for min_foliar in [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]:
    for max_dark in [0.30, 0.35, 0.40, 0.45]:
        for min_conf in [0.40, 0.50, 0.60]:
            for max_ent in [1.20, 1.45, 1.75]:
                for min_marg in [0.05, 0.10, 0.12]:
                    rej_nl = sum(1 for x in nonleaf if full_gate(x, min_conf, max_ent, min_marg, min_foliar, max_dark) != "ACCEPT")
                    acc_hw = sum(1 for x in hw if full_gate(x, min_conf, max_ent, min_marg, min_foliar, max_dark) == "ACCEPT")
                    score = (rej_nl, acc_hw)
                    if best is None or score > best[0]:
                        best = (score, (min_foliar, max_dark, min_conf, max_ent, min_marg))

(brej, bacc), (bf, bd, bc, be, bm) = best
print(f"\nBEST full gate: reject {brej}/{len(nonleaf)} non-leaf, accept {bacc}/{len(hw)} hardware")
print(f"  MIN_FOLIAR_RATIO={bf}  MAX_DARK_FRACTION={bd}  MIN_CONFIDENCE={bc}  MAX_ENTROPY={be}  MIN_MARGIN={bm}")

print("\nPer-scan verdicts at best gate:")
for x in rows:
    v = full_gate(x, bc, be, bm, bf, bd)
    print(f"  scan {x['scan']:>2} {x['kind']:40} {v}")
