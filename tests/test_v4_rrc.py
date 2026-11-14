"""Quick numeric sanity check of the v4 RRC loader on 3 real images per source type."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai_engine"))

import numpy as np
import tensorflow as tf

import train_model_v4 as T

paths = [
    (r"C:\Users\DELL\.cache\kagglehub\datasets\vipoooool\new-plant-diseases-dataset\versions\2"
     r"\New Plant Diseases Dataset(Augmented)\New Plant Diseases Dataset(Augmented)"
     r"\train\Potato___healthy\00fc2ee5-729f-4757-8aeb-65c3355874f2___RS_HL 1864.JPG",
     T.RRC_MIN_PV, "PV"),
    (r"C:\Users\DELL\Downloads\KRISHI-DRISHTI\ai_engine\field_supplements\Potato___healthy__6388db5e429a.jpg",
     T.RRC_MIN_SUPPLEMENT, "SUPP"),
]

ds_files = [(str(p), m, tag) for p, m, tag in paths if Path(p).exists()]
print("found:", [(t, Path(p).exists()) for p, m, t in paths])

for p, m, tag in ds_files:
    img_t, y, w = T.load_img(tf.constant(p), tf.constant(3, tf.int32),
                             tf.constant(1.0, tf.float32), tf.constant(m, tf.float32))
    arr = img_t.numpy()
    print(f"{tag}: shape={arr.shape} min={arr.min():.1f} max={arr.max():.1f} "
          f"mean={arr.mean():.1f} label_onehot_sum={float(tf.reduce_sum(y)):.3f} w={float(w):.2f}")

# run 5 random draws to confirm variability
p, m, tag = ds_files[1]
outs = []
for i in range(5):
    img_t, _, _ = T.load_img(tf.constant(p), tf.constant(3, tf.int32),
                             tf.constant(1.0, tf.float32), tf.constant(m, tf.float32))
    outs.append(float(tf.reduce_mean(img_t)))
print("supp 5 draws mean-px:", [round(v, 1) for v in outs])
print("RRC SANITY OK")
