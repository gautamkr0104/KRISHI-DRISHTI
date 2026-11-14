"""Framing experiment: center-crop a single leaflet from the multi-leaf foliage image."""
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MODEL = Path(__file__).resolve().parent.parent / "ai_engine" / "krishi_drishti_model.tflite"
CLASS = ["Tomato___Late_blight", "Tomato___Early_blight", "Tomato___healthy",
         "Potato___Late_blight", "Potato___Early_blight", "Potato___healthy"]

interp = tf.lite.Interpreter(model_path=str(MODEL))
interp.allocate_tensors()
ind, outd = interp.get_input_details()[0], interp.get_output_details()[0]

src = Image.open(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest\Potato_leaves.jpg").convert("RGB")
w, h = src.size
print("source size:", src.size)

# full image resize (what the daemon does) vs center-square crop first (browser-engine style)
def run(im, tag):
    arr = np.asarray(im.resize((128, 128), Image.BILINEAR), dtype=np.float32)
    interp.set_tensor(ind["index"], np.expand_dims(arr, 0))
    interp.invoke()
    pr = interp.get_tensor(outd["index"])[0]
    top = int(np.argmax(pr))
    print(f"{tag:34s} -> {CLASS[top]:24s} conf={float(pr[top]):.3f}")

run(src, "full image, direct resize")
side = min(w, h)
sq = src.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
run(sq, "center square crop")
# manual single-leaflet crops (large healthy leaflet left-center and lower-right)
for i, box in enumerate([(0.02, 0.55, 0.38, 0.85), (0.55, 0.72, 0.95, 0.98), (0.3, 0.05, 0.75, 0.35)], 1):
    x0, y0, x1, y1 = box
    c = src.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    run(c, f"single-leaflet crop {i}")
    out = Path(rf"C:\Users\DELL\AppData\Local\Temp\opencode\webtest\leaflet_{i}.jpg")
    c.save(out)
