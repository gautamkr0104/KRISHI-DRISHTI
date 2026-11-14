"""Gate hole test: green chart paper + palm photos through the daemon pipeline."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai_engine"))
import krishi_ai_daemon as K
import tensorflow as tf

OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
MODEL = str(Path(__file__).resolve().parent.parent / "ai_engine" / "krishi_drishti_model.tflite")
LABELS = str(Path(__file__).resolve().parent.parent / "ai_engine" / "labels.json")

rng = np.random.default_rng(7)

def synth_paper(size, base=(58, 138, 68), grain=6.0, vignette=0.10, jitter=2.0):
    """Realistic flat green chart paper photo: uniform color + grain + gentle lighting."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # gentle lighting gradient (like a handheld photo)
    grad = 1.0 + vignette * ((xx / w - 0.35) * 0.6 + (yy / h - 0.45) * 0.4)
    img = np.zeros((h, w, 3), dtype=np.float32)
    for c in range(3):
        img[:, :, c] = base[c] * grad
    # paper grain
    img += rng.normal(0, grain, (h, w, 3))
    # slight AWB channel jitter like the ESP32
    img += np.array([jitter, 0, -jitter])
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

paper_full = synth_paper((960, 1280))
paper_full.save(OUT / "green_chart_paper_full.jpg", quality=92)
paper_partial = Image.new("RGB", (960, 1280))
p2 = synth_paper((960, 900))
paper_partial.paste(p2, (0, 0))
# bottom part: desk background (brown)
bg = np.zeros((1280 - 900, 960, 3), dtype=np.float32)
bg[..., 0] = 96 + rng.normal(0, 8, (1280 - 900, 960))
bg[..., 1] = 74 + rng.normal(0, 8, (1280 - 900, 960))
bg[..., 2] = 52 + rng.normal(0, 8, (1280 - 900, 960))
paper_partial.paste(Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)), (0, 900))
paper_partial.save(OUT / "green_chart_paper_partial.jpg", quality=92)

daemon = K.KrishiAIDaemon(MODEL, LABELS)

tests = [
    ("green_chart_paper_full.jpg", OUT / "green_chart_paper_full.jpg"),
    ("green_chart_paper_partial.jpg", OUT / "green_chart_paper_partial.jpg"),
] + [(f"SD palm scan_{n:06d}.jpg", Path(f"E:/scan_{n:06d}.jpg")) for n in (4, 5, 6, 7)]

print(f"\n{'image':34s} {'foliar':>6} {'dark':>6} {'daemon result':30s} {'conf':>6}")
print("-" * 92)
for name, p in tests:
    if not p.exists():
        print(f"{name:34s} MISSING")
        continue
    img = Image.open(p)
    res = daemon.run_inference(img)
    conf = res.get("confidence", 0.0)
    # recompute gate stats for the record
    arr = np.asarray(img.convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    foliar = float(np.mean(((g > r * 0.95) & (g > b * 1.05)) | ((r > 60) & (g > 50) & (b < 80))))
    dark = float(np.mean((r < 35) & (g < 35) & (b < 35)))
    print(f"{name[:34]:34s} {foliar:6.2f} {dark:6.2f} {(res.get('crop') or 'Unknown') + ' ' + res.get('disease', '?'):30s} {conf:5.1f}%  {res.get('status')}")
