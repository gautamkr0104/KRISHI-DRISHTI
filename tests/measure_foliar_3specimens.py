"""Measure daemon foliar/dark ratios for the 3 gated benchmark specimens (exact files)."""
import numpy as np
from PIL import Image
from pathlib import Path

d = Path(r"C:\Users\DELL\Downloads\KRISHI-DRISHTI\ai_engine\validation_60_specimens\Tomato___Late_blight")
for name in ["Tomato___Late_blight_05.jpg", "Tomato___Late_blight_08.jpg", "Tomato___Late_blight_09.jpg"]:
    arr = np.asarray(Image.open(d / name).convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    foliar = float(np.mean(((g > r * 0.95) & (g > b * 1.05)) | ((r > 60) & (g > 50) & (b < 80))))
    dark = float(np.mean((r < 35) & (g < 35) & (b < 35)))
    print(f"{name:32s} foliar={foliar:.4f} dark={dark:.4f}")

# Also scan ALL 60 specimens for the minimum foliar ratio (worst-case acceptance margin)
print("\nAll 60 specimens sorted by foliar ratio (lowest 12):")
vals = []
for cls in ["Potato___Early_blight", "Potato___Late_blight", "Potato___healthy",
            "Tomato___Early_blight", "Tomato___Late_blight", "Tomato___healthy"]:
    cdir = d.parent / cls
    for f in sorted(cdir.glob("*.jpg")):
        a = np.asarray(Image.open(f).convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
        rr, gg, bb = a[:, :, 0], a[:, :, 1], a[:, :, 2]
        fo = float(np.mean(((gg > rr * 0.95) & (gg > bb * 1.05)) | ((rr > 60) & (gg > 50) & (bb < 80))))
        vals.append((fo, f"{cls}/{f.name}"))
vals.sort()
for fo, name in vals[:12]:
    print(f"  foliar={fo:.4f}  {name}")
