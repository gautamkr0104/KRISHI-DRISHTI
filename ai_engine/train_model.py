"""
KRISHI-DRISHTI :: Production Dual-Domain Edge AI Training Pipeline
Author: Gautam Kumar / KRISHI-DRISHTI Project
----------------------------------------------------------------------------------------
Architecture: MobileNetV3-Small (Two-Phase Fine-Tuning + Float16 PTQ)
Target Hardware: Edge Devices (Samsung Galaxy A03 / Cortex-A55, < 40 ms budget)

Cryptographic Zero-Leakage Boundaries:
1. PlantVillage: 6,600 clean foliar samples (1,100 per class)
   - Excludes all 60 botanical validation benchmark hashes (ai_engine/validation_60_specimens)
   - Excludes all 10 real-world field test hashes (ai_engine/field_test_images)
   - Excludes all 8 canonical sample leaves hashes (ai_engine/sample_leaves)
2. PlantDoc Outdoor Solanaceae Partition:
   - 80% Train Split (380 clean unique images, replicated 3x = 1,140 samples)
   - 20% Held-Out Test Split (93 unique clean images) strictly excluded via PLANTDOC_HOLDOUT_MANIFEST.json
   - 5 conflicting cross-class duplicate hashes excluded completely to eliminate label noise
3. Zero Test Images in Training:
   - Zero images from validation_60_specimens are added to training
   - Zero images from field_test_images are added to training
   - Zero images from sample_leaves are added to training

Outputs:
  - Model Artifact: ai_engine/krishi_drishti_model.tflite (~2.03 MB)
  - Provenance Manifest: ai_engine/PLANTDOC_HOLDOUT_MANIFEST.json
"""

import os
import sys
import time
import json
import random
import hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, regularizers
    from tensorflow.keras.applications import MobileNetV3Small
except ImportError:
    print("[ERROR] TensorFlow is required for training: pip install tensorflow")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGE_SIZE = (128, 128)
BATCH_SIZE = 32

CLASS_NAMES = [
    "Tomato___Late_blight",   # Index 0
    "Tomato___Early_blight",  # Index 1
    "Tomato___healthy",       # Index 2
    "Potato___Late_blight",   # Index 3
    "Potato___Early_blight",  # Index 4
    "Potato___healthy"        # Index 5
]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASS_NAMES)}

def main():
    print("=" * 80)
    print("  KRISHI-DRISHTI :: PRODUCTION STRICT ZERO-LEAKAGE DUAL-DOMAIN TRAINING")
    print("=" * 80)

    # 1. Collect Evaluation Hashes for Master Blacklist
    bench_dir = REPO_ROOT / "ai_engine" / "validation_60_specimens"
    field_dir = REPO_ROOT / "ai_engine" / "field_test_images"
    sample_dir = REPO_ROOT / "ai_engine" / "sample_leaves"

    bench_hashes = set(hashlib.sha256(f.read_bytes()).hexdigest() for f in bench_dir.glob("*/*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png"])
    field_hashes = set(hashlib.sha256(f.read_bytes()).hexdigest() for f in field_dir.glob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png"])
    sample_hashes = set(hashlib.sha256(f.read_bytes()).hexdigest() for f in sample_dir.glob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png"])

    print(f"[+] Loaded {len(bench_hashes)} 60-specimen benchmark hashes")
    print(f"[+] Loaded {len(field_hashes)} real-world field test hashes")
    print(f"[+] Loaded {len(sample_hashes)} canonical sample leaves hashes")

    # 2. Build Clean PlantDoc Hash Partition
    manifest_path = REPO_ROOT / "ai_engine" / "PLANTDOC_HOLDOUT_MANIFEST.json"
    if not manifest_path.exists():
        print(f"[FAIL] Holdout manifest missing at: {manifest_path}")
        print("       Run manifest generation to ensure strict hash-level train/test separation.")
        return 1

    with open(manifest_path, "r", encoding="utf-8") as mf:
        mdata = json.load(mf)

    plantdoc_test_specimens = mdata.get("held_out_test_specimens", [])
    plantdoc_train_specimens = mdata.get("train_specimens", [])
    conflicting_hashes = set(mdata.get("conflicting_hashes", []))

    plantdoc_test_hashes = set(x["sha256"] for x in plantdoc_test_specimens)
    print(f"[+] PlantDoc Manifest: {len(plantdoc_train_specimens)} TRAIN | {len(plantdoc_test_specimens)} HELD-OUT TEST")

    # Master Blacklist: Zero test or benchmark data can EVER enter training
    master_blacklist = bench_hashes.union(field_hashes).union(sample_hashes).union(plantdoc_test_hashes).union(conflicting_hashes)
    print(f"[+] MASTER BLACKLIST FOR TRAINING: {len(master_blacklist)} unique hashes strictly forbidden from training.")

    # 3. Assemble Pure Training Dataset
    pv_train_dir = Path(r"C:\Users\DELL\.cache\kagglehub\datasets\vipoooool\new-plant-diseases-dataset\versions\2\New Plant Diseases Dataset(Augmented)\New Plant Diseases Dataset(Augmented)\train")
    if not pv_train_dir.exists():
        pv_train_dir = REPO_ROOT / "ai_engine" / "PlantVillage_Train"

    all_paths = []
    all_labels = []

    random.seed(42)
    np.random.seed(42)
    tf.random.set_seed(42)

    # (A) PlantVillage Clean Samples (1,100 per class, zero blacklist overlap)
    if pv_train_dir.exists():
        for cname in CLASS_NAMES:
            cdir = pv_train_dir / cname
            if cdir.exists():
                files = sorted(list(cdir.glob("*.*")))
                clean_files = [
                    f for f in files 
                    if f.suffix.lower() in [".jpg", ".jpeg", ".png"] 
                    and hashlib.sha256(f.read_bytes()).hexdigest() not in master_blacklist
                ]
                selected = random.sample(clean_files, min(len(clean_files), 1100))
                for sf in selected:
                    all_paths.append(str(sf))
                    all_labels.append(CLASS_TO_IDX[cname])
                print(f"  [PV Clean Train] {cname:<24}: {len(selected)} samples (zero blacklist overlap)")

    # (B) PlantDoc Clean Train Split (replicated 3x, zero test overlap)
    for item in plantdoc_train_specimens:
        assert item["sha256"] not in master_blacklist, f"LEAK DETECTED: {item['filename']}"
        if item["class"] in CLASS_TO_IDX:
            c_idx = CLASS_TO_IDX[item["class"]]
            for _ in range(3):
                all_paths.append(item["path"])
                all_labels.append(c_idx)

    print(f"  [PlantDoc Clean Train] {len(plantdoc_train_specimens)} unique outdoor images added (replicated 3x = {len(plantdoc_train_specimens)*3})")

    # STRICT AUDIT: Verify ZERO master_blacklist hashes exist in training!
    print("\n[*] Auditing training paths against master blacklist...")
    leak_count = 0
    for p in all_paths:
        h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
        if h in master_blacklist:
            print(f"[CRITICAL ERROR] Leaked hash in training: {p}")
            leak_count += 1

    assert leak_count == 0, f"Found {leak_count} leaked hashes!"
    print("[OK] ZERO LEAKAGE VERIFIED! Not a single benchmark, field, canonical, or test image exists in training.")

    print(f"\n[+] Total Pure Training Corpus: {len(all_paths)} images")

    combined = list(zip(all_paths, all_labels))
    random.shuffle(combined)
    train_paths, train_labels = zip(*combined)

    def load_img(path, label):
        img = tf.io.read_file(path)
        img = tf.image.decode_jpeg(img, channels=3)
        img = tf.image.resize(img, IMAGE_SIZE)
        img = tf.cast(img, tf.float32)
        return img, tf.one_hot(label, len(CLASS_NAMES))

    train_ds = tf.data.Dataset.from_tensor_slices((list(train_paths), list(train_labels)))
    train_ds = train_ds.map(load_img, num_parallel_calls=tf.data.AUTOTUNE).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

    augmentation = tf.keras.Sequential([
        layers.RandomFlip("horizontal_and_vertical"),
        layers.RandomRotation(0.12),
        layers.RandomZoom(0.10),
        layers.RandomContrast(0.15),
        layers.RandomBrightness(0.15),
    ], name="field_canopy_augmentation")

    base_model = MobileNetV3Small(
        input_shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3),
        include_top=False,
        weights='imagenet',
        pooling='avg'
    )
    base_model.trainable = False

    inputs = tf.keras.Input(shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3), name="serving_default_leaf_rgb_input")
    x = augmentation(inputs)
    x = tf.keras.applications.mobilenet_v3.preprocess_input(x)
    x = base_model(x, training=False)

    x = layers.Dropout(0.25, name="head_dropout_1")(x)
    x = layers.Dense(144, activation='relu', kernel_regularizer=regularizers.l2(3e-5), name="foliar_feature_dense")(x)
    x = layers.BatchNormalization(name="head_bn")(x)
    x = layers.Dropout(0.20, name="head_dropout_2")(x)
    outputs = layers.Dense(len(CLASS_NAMES), activation='softmax', name="disease_probability_output")(x)

    model = models.Model(inputs, outputs, name="krishi_drishti_edge_model")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    print("\n[+] Phase 1: Classification Head Warmup (4 Epochs)...")
    t0 = time.time()
    model.fit(train_ds, epochs=4, verbose=1)

    print("\n[+] Phase 2: Deep Fine-Tuning Top 25 Backbone Layers (3 Epochs)...")
    base_model.trainable = True
    for layer in base_model.layers[:-25]:
        layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1.2e-4),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    model.fit(train_ds, epochs=3, verbose=1)
    print(f"\n[+] Total Training Elapsed Time: {time.time() - t0:.1f} seconds")

    # Export Float16 Quantized Model
    print("\n[*] Exporting Post-Training Quantized (Float16) Edge TFLite Model...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_bytes = converter.convert()

    out_path = REPO_ROOT / "ai_engine" / "krishi_drishti_model.tflite"
    with open(out_path, "wb") as f:
        f.write(tflite_bytes)

    print(f"[OK] Pure Zero-Leakage TFLite model successfully written to: {out_path}")
    print(f"     Size: {len(tflite_bytes):,} bytes ({len(tflite_bytes)/(1024*1024):.2f} MB)")
    print(f"     SHA-256: {hashlib.sha256(tflite_bytes).hexdigest()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
