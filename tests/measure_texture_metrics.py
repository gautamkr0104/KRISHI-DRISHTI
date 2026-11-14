"""Measure candidate texture metrics: real leaves vs paper vs palms, find a separator."""
import sys
import json
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
WEBTEST = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
PV_VALID = Path.home() / ".cache" / "kagglehub" / "datasets" / "vipoooool" / "new-plant-diseases-dataset" / "versions" / "2" / "New Plant Diseases Dataset(Augmented)" / "New Plant Diseases Dataset(Augmented)" / "valid"


def metrics(img):
    """Texture metrics on the 128x128 daemon view."""
    a = np.asarray(img.convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
    gray = a.mean(axis=2)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    foliar_mask = ((g > r * 0.95) & (g > b * 1.05)) | ((r > 60) & (g > 50) & (b < 80))

    # Sobel edge energy
    gx = np.abs(np.diff(gray, axis=1))[:-1, :]
    gy = np.abs(np.diff(gray, axis=0))[:, :-1]
    edge = float(np.mean(np.hypot(gx, gy)))

    # Laplacian variance (texture "crispness")
    lap = (np.roll(gray, 1, 0) + np.roll(gray, -1, 0) + np.roll(gray, 1, 1) + np.roll(gray, -1, 1) - 4 * gray)
    lap_var = float(np.var(lap))

    # hue spread within foliar pixels (green-hue diversity)
    mx = a.max(axis=2); mn = a.min(axis=2)
    hue_spread = float(np.std(mx[mn > 0] - mn[mn > 0]))

    # block structure: variance of 8x8 block means (spatial color layout)
    blocks = gray.reshape(16, 8, 16, 8).mean(axis=(1, 3))
    block_var = float(np.var(blocks))

    # edge energy ONLY on foliar pixels (paper wrinkles vs leaf veins both show, but compare)
    edge_foliar = float(np.mean(np.hypot(gx, gy)[foliar_mask[:-1, :-1]])) if foliar_mask.sum() > 50 else 0.0

    return {"edge": round(edge, 2), "lap_var": round(lap_var, 1),
            "hue_spread": round(hue_spread, 2), "block_var": round(block_var, 1),
            "edge_foliar": round(edge_foliar, 2)}


rows = []
# green paper variants
for p in sorted(WEBTEST.glob("paper_*.jpg")) + sorted(WEBTEST.glob("green_chart_paper_*.jpg")):
    rows.append(("PAPER", p.name, metrics(Image.open(p))))
# palms from SD
for n in (4, 5, 6, 7):
    p = Path(f"E:/scan_{n:06d}.jpg")
    if p.exists():
        rows.append(("PALM", p.name, metrics(Image.open(p))))
# real leaves: 10 random PV valid images per class
import random
random.seed(3)
for cls in sorted(PV_VALID.iterdir()):
    files = list(cls.glob("*.jpg"))
    for f in random.sample(files, 4):
        rows.append(("LEAF", f"{cls.name}/{f.name[:20]}", metrics(Image.open(f))))
# real leaves: washed-out SD scans + benchmark worst cases
for n in (15, 39, 42):
    p = Path(f"E:/scan_{n:06d}.jpg")
    if p.exists():
        rows.append(("LEAF-SD", f"scan_{n:06d}", metrics(Image.open(p))))
for spec in ["Tomato___Late_blight/Tomato___Late_blight_09.jpg", "Tomato___Late_blight/Tomato___Late_blight_05.jpg"]:
    p = REPO / "ai_engine" / "validation_60_specimens" / spec
    if p.exists():
        rows.append(("LEAF-BENCH", spec.split("/")[1], metrics(Image.open(p))))

print(f"{'kind':10s} {'name':36s} {'edge':>7} {'lap_var':>9} {'hue_sp':>7} {'blk_var':>8} {'edg_fol':>8}")
for kind, name, m in rows:
    print(f"{kind:10s} {name[:36]:36s} {m['edge']:7.2f} {m['lap_var']:9.1f} {m['hue_spread']:7.2f} {m['block_var']:8.2f} {m['edge_foliar']:8.2f}")

Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\texture_metrics.json").write_text(
    json.dumps([{"kind": k, "name": n, **m} for k, n, m in rows], indent=1), encoding="utf-8")
