"""Stress-test green paper variants: crumpled, dark, curved — do any cross the 0.50 gate?"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai_engine"))
import krishi_ai_daemon as K

OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
MODEL = str(Path(__file__).resolve().parent.parent / "ai_engine" / "krishi_drishti_model.tflite")
LABELS = str(Path(__file__).resolve().parent.parent / "ai_engine" / "labels.json")
rng = np.random.default_rng(11)
daemon = K.KrishiAIDaemon(MODEL, LABELS)


def paper(base, wrinkle=False, curve=False, grain=6.0, size=(960, 1280)):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    lum = np.ones((h, w), dtype=np.float32)
    if wrinkle:
        n = rng.normal(0, 1, (h // 40, w // 40, 1)).repeat(40, 0).repeat(40, 1)[:, :, 0]
        n = np.asarray(Image.fromarray(((n - n.min()) / (np.ptp(n) + 1e-6) * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(6)), dtype=np.float32) / 255.0
        lum += (n - n.mean()) * 0.55
    if curve:
        lum += 0.28 * np.sin(xx / 130.0)
    img = np.zeros((h, w, 3), dtype=np.float32)
    for c in range(3):
        img[:, :, c] = base[c] * lum
    img += rng.normal(0, grain, (h, w, 3))
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


variants = {
    "paper_flat_green": paper((58, 138, 68)),
    "paper_dark_green": paper((38, 96, 48)),
    "paper_light_green": paper((110, 190, 120)),
    "paper_crumpled": paper((58, 138, 68), wrinkle=True),
    "paper_crumpled_dark": paper((40, 100, 50), wrinkle=True),
    "paper_curved": paper((58, 138, 68), curve=True),
    "paper_curved_crumpled": paper((50, 120, 60), wrinkle=True, curve=True),
}

print(f"\n{'variant':26s} {'foliar':>6} {'conf':>6}  result")
print("-" * 78)
for name, im in variants.items():
    p = OUT / (name + ".jpg")
    im.save(p, quality=92)
    res = daemon.run_inference(im)
    arr = np.asarray(im.resize((128, 128), Image.BILINEAR), dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    foliar = float(np.mean(((g > r * 0.95) & (g > b * 1.05)) | ((r > 60) & (g > 50) & (b < 80))))
    verdict = res.get("crop", "Unknown") + " " + res.get("disease", "?")
    flag = "  <<< PASSES GATE (misclassification risk)" if res.get("status") == "OK" else ""
    print(f"{name:26s} {foliar:6.2f} {res.get('confidence', 0):5.1f}%  {verdict}  {res.get('status')}{flag}")
