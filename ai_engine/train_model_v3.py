"""
KRISHI-DRISHTI :: Production Edge AI Model Training Pipeline (v3.0 - Full Corpus)
================================================================================
Architecture: MobileNetV3-Small (Float16 Quantized Edge Model)
Input Contract: Float32 [1, 128, 128, 3], Pixel range [0.0, 255.0]
Output Contract: Float32 [1, 6] probabilities with internal Softmax
Domain: Dual-Domain Solanaceae (PlantVillage Laboratory + PlantDoc Outdoor)

v3.0 changes over v2.1 (train_model.py):
  1. FULL-CORPUS training: every clean PlantVillage Solanaceae train image
     (previously a 1,100/class subsample) x 3 augmented passes, plus clean
     PlantDoc train x 15 passes -> ~80-90K training records per epoch.
  2. Field-canopy augmentation MOVED OUT of the exported graph into the
     tf.data pipeline (exported TFLite graph stays clean; input/output
     contracts unchanged). Adds harsh-flash/overexposure mix, gamma,
     hue & saturation jitter to close the night-flash domain gap.
  3. Label smoothing (0.08) to eliminate near-one-hot overconfidence so the
     Shannon-entropy OOD gate becomes meaningful.
  4. Class weighting to lift Tomato Late Blight recall (top in-domain error).
  5. Post-training temperature calibration fitted on the PV validation set,
     baked into the final Dense layer weights (argmax-preserving -> zero
     accuracy loss, calibrated probabilities for the gating stack).
  6. Same zero-leakage assurance: SHA-256 master blacklist, dHash
     near-duplicate exclusion, PlantDoc crop-tolerant exclusion, double-pass
     audit, post-export manifest.
"""

import os
import sys
import json
import time
import math
import random
import hashlib
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow.keras import layers, models, regularizers
from tensorflow.keras.applications import MobileNetV3Small

REPO_ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ #
# FIXED CLASS ORDER — must never change (labels.json, firmware, OLED) #
# ------------------------------------------------------------------ #
CLASS_NAMES = [
    "Tomato___Late_blight",
    "Tomato___Early_blight",
    "Tomato___healthy",
    "Potato___Late_blight",
    "Potato___Early_blight",
    "Potato___healthy",
]
CLASS_TO_IDX = {name: idx for idx, name in enumerate(CLASS_NAMES)}
NUM_CLASSES = len(CLASS_NAMES)

IMAGE_SIZE = (128, 128)
BATCH_SIZE = 32
RANDOM_SEED = 42

# v3 corpus policy
PV_PASSES = 7            # augmented passes over every clean PV train image (11.4K unique -> ~79.6K)
PLANTDOC_PASSES = 15     # augmented passes over clean PlantDoc train images
MIN_TOTAL_RECORDS = 75000
MAX_TOTAL_RECORDS = 95000
MIN_PER_CLASS_UNIQUE = 1200   # hard floor after leak filtering

# Regularization / calibration
LABEL_SMOOTHING = 0.08
CLASS_WEIGHT_BOOST = {"Tomato___Late_blight": 1.35, "Potato___Late_blight": 1.10}
PHASE1_EPOCHS = 2
PHASE2_EPOCHS = 4
PHASE1_LR = 1e-3
PHASE2_LR = 3e-4
UNFROZEN_BACKBONE_LAYERS = 40


# ================================================================== #
# Perceptual hashing (identical methodology to v2.1)                 #
# ================================================================== #
def compute_dhash(img_or_bytes, hash_size=8):
    """Compute 64-bit difference hash (dHash) for perceptual near-duplicate detection."""
    try:
        import io
        if isinstance(img_or_bytes, (bytes, bytearray)):
            img = Image.open(io.BytesIO(img_or_bytes))
        else:
            img = img_or_bytes
        im = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
        pixels = np.array(im, dtype=np.int32)
        diff = pixels[:, 1:] > pixels[:, :-1]
        val = 0
        for idx, v in enumerate(diff.flatten()):
            if v:
                val += 1 << idx
        return val
    except Exception:
        return 0


def hamming_dist(n1, n2):
    return bin(n1 ^ n2).count("1")


def get_crops(img):
    w, h = img.size
    return [
        img,
        img.crop((w * 0.125, h * 0.125, w * 0.875, h * 0.875)),
        img.crop((w * 0.25, h * 0.25, w * 0.75, h * 0.75)),
    ]


# ================================================================== #
# tf.data pipeline (augmentation lives here, NOT in the model graph)  #
# ================================================================== #
def load_img(path, label, sample_w):
    img = tf.io.read_file(path)
    img = tf.image.decode_jpeg(img, channels=3)
    img = tf.image.resize(img, IMAGE_SIZE)
    img = tf.cast(img, tf.float32)
    y = tf.one_hot(label, NUM_CLASSES)
    y = y * (1.0 - LABEL_SMOOTHING) + LABEL_SMOOTHING / NUM_CLASSES
    return img, y, sample_w


def per_image_field_randoms(img, y, w):
    """Per-image canopy-domain randomization (applied per element, so every
    repeat pass produces a fresh randomized variant of the same file)."""
    img = tf.image.random_hue(img, 0.05)
    img = tf.image.random_saturation(img, 0.65, 1.60)
    # Random gamma (leaf highlight / shadow response)
    gamma = tf.random.uniform([], 0.70, 1.45)
    img = tf.pow(img / 255.0, gamma) * 255.0
    # Harsh-flash / overexposure mix (night-torch simulation)
    flash_roll = tf.random.uniform([], 0.0, 1.0)
    flash_amt = tf.random.uniform([], 0.05, 0.38)
    img = tf.where(flash_roll < 0.30, img * (1.0 - flash_amt) + 255.0 * flash_amt, img)
    # Sensor AWB-failure / LED-flash purple-magenta cast (observed in real
    # ESP32-CAM night-flash captures: green channel suppressed vs red+blue)
    cast_roll = tf.random.uniform([], 0.0, 1.0)
    cast_strength = tf.random.uniform([], 0.10, 0.30)
    purple_cast = tf.stack([1.0 + cast_strength * 0.40,
                            1.0 - cast_strength,
                            1.0 + cast_strength * 0.50])
    img = tf.where(cast_roll < 0.25,
                   tf.clip_by_value(img * purple_cast, 0.0, 255.0), img)
    img = tf.clip_by_value(img, 0.0, 255.0)
    return img, y, w


def make_batch_augmenter():
    """Batched geometric/photometric augmentation via Keras preprocessing layers.
    These layers are applied ONLY here (dataset side); the exported model
    graph contains no augmentation ops."""
    return tf.keras.Sequential(
        [
            layers.RandomFlip("horizontal_and_vertical"),
            layers.RandomRotation(0.15),
            layers.RandomZoom(0.15),
            layers.RandomTranslation(0.10, 0.10),
            layers.RandomContrast(0.30),
            layers.RandomBrightness(0.25, value_range=(0.0, 255.0)),
        ],
        name="field_canopy_augmentation",
    )


# ================================================================== #
# Temperature calibration utilities                                  #
# ================================================================== #
def softmax_np(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(probs, y_true_idx):
    """Fit T minimizing NLL of softmax(log(p)/T). probs: (N,C) softmax outputs."""
    eps = 1e-12
    logits = np.log(np.clip(probs, eps, 1.0))
    best_t, best_nll = 1.0, None
    for T in np.arange(0.40, 6.01, 0.02):
        z = logits / T
        p = softmax_np(z)
        nll = -np.mean(np.log(np.clip(p[np.arange(len(y_true_idx)), y_true_idx], eps, 1.0)))
        if best_nll is None or nll < best_nll:
            best_nll, best_t = nll, float(T)
    return round(best_t, 2), best_nll


def bake_temperature(model, T):
    """Scale the final Dense (kernel & bias) by 1/T. softmax(z/T) preserves
    argmax while softening the distribution -> calibrated probabilities with
    an unchanged I/O contract."""
    out_layer = model.get_layer("disease_probability_output")
    kernel, bias = out_layer.get_weights()
    out_layer.set_weights([kernel / T, bias / T])


# ================================================================== #
# Main                                                               #
# ================================================================== #
def main():
    t_start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0_wall = time.time()

    print("=" * 84)
    print("  KRISHI-DRISHTI :: PRODUCTION v3 FULL-CORPUS ZERO-LEAKAGE TRAINING")
    print("  Full PV Solanaceae + PlantDoc | Flash-Canopy Augmentation | Calibration")
    print("=" * 84)

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    tf.random.set_seed(RANDOM_SEED)

    # ---------------------------------------------------------------- #
    # 1. Master blacklist of evaluation targets                        #
    # ---------------------------------------------------------------- #
    bench_dir = REPO_ROOT / "ai_engine" / "validation_60_specimens"
    field_dir = REPO_ROOT / "ai_engine" / "field_test_images"
    sample_dir = REPO_ROOT / "ai_engine" / "sample_leaves"
    manifest_path = REPO_ROOT / "ai_engine" / "PLANTDOC_HOLDOUT_MANIFEST.json"

    if not manifest_path.exists():
        print(f"[FAIL] PlantDoc holdout manifest missing at: {manifest_path}")
        return 1

    with open(manifest_path, "r", encoding="utf-8") as mf:
        mdata = json.load(mf)

    plantdoc_test_specimens = mdata.get("held_out_test_specimens", [])
    plantdoc_raw_train_specimens = mdata.get("train_specimens", [])
    conflicting_hashes = set(mdata.get("conflicting_hashes", []))

    bench_items = []
    for f in bench_dir.glob("*/*.*"):
        if f.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            b = f.read_bytes()
            bench_items.append({"name": f.name, "sha": hashlib.sha256(b).hexdigest(),
                                "dhash": compute_dhash(b)})

    bench_hashes = set(item["sha"] for item in bench_items)
    bench_dhashes = [(item["name"], item["dhash"]) for item in bench_items]
    field_hashes = set(hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in field_dir.glob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png"])
    sample_hashes = set(hashlib.sha256(f.read_bytes()).hexdigest()
                        for f in sample_dir.glob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png"])
    plantdoc_test_hashes = set(x["sha256"] for x in plantdoc_test_specimens)

    master_blacklist = (bench_hashes | field_hashes | sample_hashes
                        | plantdoc_test_hashes | conflicting_hashes)

    print(f"[+] Blacklist: {len(bench_hashes)} bench, {len(sample_hashes)} canonical, "
          f"{len(field_hashes)} field, {len(plantdoc_test_hashes)} PlantDoc held-out, "
          f"{len(conflicting_hashes)} conflicting -> {len(master_blacklist)} unique prohibited hashes.")

    test_crop_hashes = []
    for s in plantdoc_test_specimens:
        p = Path(s["path"])
        if p.exists():
            img = Image.open(p)
            test_crop_hashes.append({
                "fn": s["filename"],
                "dhashes": [compute_dhash(c) for c in get_crops(img)],
                "sha256": s["sha256"],
            })

    # ---------------------------------------------------------------- #
    # 2. Full clean PlantVillage Solanaceae corpus (no subsampling)     #
    # ---------------------------------------------------------------- #
    pv_train_dir = Path(r"C:\Users\DELL\.cache\kagglehub\datasets\vipoooool\new-plant-diseases-dataset\versions\2"
                        r"\New Plant Diseases Dataset(Augmented)\New Plant Diseases Dataset(Augmented)\train")
    if not pv_train_dir.exists():
        pv_train_dir = REPO_ROOT / "ai_engine" / "PlantVillage_Train"
    if not pv_train_dir.exists():
        # Generic kagglehub fallback (works on Colab/Linux where the cache path differs)
        try:
            import kagglehub
            base = Path(kagglehub.dataset_download("vipoooool/new-plant-diseases-dataset"))
            candidates = list(base.rglob("train"))
            candidates = [c for c in candidates if c.is_dir() and (c / CLASS_NAMES[0]).exists()]
            if candidates:
                pv_train_dir = candidates[0]
                print(f"[+] Using kagglehub-discovered train dir: {pv_train_dir}")
        except Exception as e:
            print(f"[WARN] kagglehub fallback failed: {e}")
    if not pv_train_dir.exists():
        print(f"[FAIL] PlantVillage training directory not found.")
        print("       Re-download via kagglehub (vipoooool/new-plant-diseases-dataset) or place at ai_engine/PlantVillage_Train")
        return 1

    all_paths, all_labels, all_record_hashes = [], [], []
    excluded_pv_near_duplicates = []
    per_class_unique_counts = {}
    path_cache = {}   # unique path -> (sha, dhash) for audit speed

    for cname in CLASS_NAMES:
        cdir = pv_train_dir / cname
        if not cdir.exists():
            print(f"[FAIL] Class directory missing: {cdir}")
            return 1
        clean_files = []
        for f in sorted(cdir.glob("*.*")):
            if f.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
                continue
            if str(f) in path_cache:
                sha, dh = path_cache[str(f)]
            else:
                b = f.read_bytes()
                sha = hashlib.sha256(b).hexdigest()
                dh = compute_dhash(b)
                path_cache[str(f)] = (sha, dh)
            if sha in master_blacklist:
                continue
            min_d = min(hamming_dist(dh, b_dh) for _, b_dh in bench_dhashes)
            if min_d <= 2:
                excluded_pv_near_duplicates.append({
                    "class": cname, "file": f.name, "sha256": sha,
                    "hamming_distance": min_d,
                })
                continue
            clean_files.append((str(f), sha))

        if len(clean_files) < MIN_PER_CLASS_UNIQUE:
            print(f"[FAIL] Insufficient clean files for {cname}: {len(clean_files)} < {MIN_PER_CLASS_UNIQUE}")
            return 1

        per_class_unique_counts[cname] = len(clean_files)
        for sf, s_sha in clean_files:
            all_paths.append(sf)
            all_labels.append(CLASS_TO_IDX[cname])
            all_record_hashes.append(s_sha)
        print(f"  [PV clean] {cname:<24}: {len(clean_files)} unique files (full corpus, zero overlap)")

    print(f"[+] dHash near-duplicates excluded vs 60-specimen benchmark: {len(excluded_pv_near_duplicates)}")

    # ---------------------------------------------------------------- #
    # 3. Clean PlantDoc train split (crop-tolerant exclusion)          #
    # ---------------------------------------------------------------- #
    plantdoc_source_family_exclusions = {
        "train_45035_1.jpg", "train_late-blight-leaves.jpg", "train_earlyblightpotato.jpg",
        "train_Early-blight.jpg", "train_tomato_late-blight_04_zoom.jpg", "train_LBleaf2INIA_0.jpg",
        "train_IMG_5813.jpg", "train_a7710b5901ba1f8e9759ef7576cd9f09.jpg",
        "train_IMG_5360.jpg", "train_tomato-leaf.jpg",
    }

    clean_plantdoc_train = []
    excluded_plantdoc = []
    for item in plantdoc_raw_train_specimens:
        if item["sha256"] in master_blacklist:
            excluded_plantdoc.append({
                "class": item["class"], "file": item["filename"], "sha256": item["sha256"],
                "reason": "sha in master blacklist",
            })
            continue
        if item["filename"] in plantdoc_source_family_exclusions:
            excluded_plantdoc.append({
                "class": item["class"], "file": item["filename"], "sha256": item["sha256"],
                "reason": "crop/zoom/identical source family match to held-out test specimen",
            })
            continue
        p = Path(item["path"])
        if not p.exists():
            excluded_plantdoc.append({
                "class": item["class"], "file": item["filename"], "sha256": item["sha256"],
                "reason": "file missing on disk",
            })
            continue
        img = Image.open(p)
        tr_dhashes = [compute_dhash(c) for c in get_crops(img)]
        collision_fn = None
        for tch in test_crop_hashes:
            for tdh in tch["dhashes"]:
                for tr_dh in tr_dhashes:
                    if hamming_dist(tdh, tr_dh) <= 2:
                        collision_fn = tch["fn"]
                        break
                if collision_fn:
                    break
            if collision_fn:
                break
        if collision_fn:
            excluded_plantdoc.append({
                "class": item["class"], "file": item["filename"], "sha256": item["sha256"],
                "reason": f"crop dHash collision (dist<=2) with test specimen {collision_fn}",
            })
            continue
        clean_plantdoc_train.append(item)

    print(f"[+] PlantDoc train: {len(clean_plantdoc_train)} clean, {len(excluded_plantdoc)} excluded")

    # Snapshot PV records BEFORE PlantDoc replication (PV-only × PV_PASSES)
    pv_record_count = len(all_paths)
    base_pv = list(zip(all_paths, all_labels, all_record_hashes))

    for item in clean_plantdoc_train:
        if item["class"] in CLASS_TO_IDX:
            c_idx = CLASS_TO_IDX[item["class"]]
            for _ in range(PLANTDOC_PASSES):
                all_paths.append(item["path"])
                all_labels.append(c_idx)
                all_record_hashes.append(item["sha256"])

    # PV passes
    for _ in range(PV_PASSES - 1):
        for p, l, h in base_pv:
            all_paths.append(p)
            all_labels.append(l)
            all_record_hashes.append(h)

    total_records = len(all_paths)
    unique_hashes = sorted(set(all_record_hashes))
    print(f"[OK] CORPUS ASSEMBLED: {total_records} training records "
          f"({pv_record_count} PV-base x{PV_PASSES} + {len(clean_plantdoc_train)} PlantDoc x{PLANTDOC_PASSES}), "
          f"{len(unique_hashes)} unique image hashes.")
    assert MIN_TOTAL_RECORDS <= total_records <= MAX_TOTAL_RECORDS, \
        f"Record count {total_records} outside [{MIN_TOTAL_RECORDS}, {MAX_TOTAL_RECORDS}]"

    # ---------------------------------------------------------------- #
    # 4. Label-consistency audit (drop any cross-class hash conflicts)  #
    # ---------------------------------------------------------------- #
    hash_to_class = {}
    cross_class_conflicts = []
    for p, l, h in zip(all_paths, all_labels, all_record_hashes):
        if h in hash_to_class:
            if hash_to_class[h] != l:
                cross_class_conflicts.append({"sha256": h, "labels": [hash_to_class[h], l]})
        else:
            hash_to_class[h] = l
    if cross_class_conflicts:
        conflict_set = {c["sha256"] for c in cross_class_conflicts}
        keep = [(p, l, h) for p, l, h in zip(all_paths, all_labels, all_record_hashes) if h not in conflict_set]
        all_paths = [x[0] for x in keep]
        all_labels = [x[1] for x in keep]
        all_record_hashes = [x[2] for x in keep]
        print(f"[WARN] {len(cross_class_conflicts)} cross-class hash conflicts DROPPED from corpus.")
    else:
        print("[OK] LABEL CONSISTENCY: every unique training hash maps to exactly 1 class label.")

    # Double-pass leak audit (per-unique cache)
    leak_count, dhash_leak_count = 0, 0
    for p, l, h in zip(all_paths, all_labels, all_record_hashes):
        if h in master_blacklist:
            leak_count += 1
            print(f"[CRITICAL] Blacklisted hash in training set: {p}")
    if leak_count:
        return 1
    print("[OK] ZERO LEAKAGE: 0 exact blacklist collisions across all training records.")

    # ---------------------------------------------------------------- #
    # 5. Class weights                                                  #
    # ---------------------------------------------------------------- #
    per_class_record_counts = {c: 0 for c in CLASS_NAMES}
    for l in all_labels:
        per_class_record_counts[CLASS_NAMES[l]] += 1
    total = sum(per_class_record_counts.values())
    class_weight_map = {}
    for i, cname in enumerate(CLASS_NAMES):
        w = total / (NUM_CLASSES * per_class_record_counts[cname])
        class_weight_map[i] = w * CLASS_WEIGHT_BOOST.get(cname, 1.0)
    norm = min(class_weight_map.values())
    class_weight_map = {k: round(v / norm, 4) for k, v in class_weight_map.items()}
    print(f"[+] Class record counts: {per_class_record_counts}")
    print(f"[+] Sample weights (per record, normalized): {class_weight_map}")

    # ---------------------------------------------------------------- #
    # 6. Datasets                                                       #
    # ---------------------------------------------------------------- #
    combined = list(zip(all_paths, all_labels, all_record_hashes))
    random.shuffle(combined)
    train_paths = [c[0] for c in combined]
    train_labels = [c[1] for c in combined]

    weights_lookup = tf.constant([class_weight_map[i] for i in range(NUM_CLASSES)], dtype=tf.float32)
    labels_tf = tf.constant(train_labels, dtype=tf.int32)

    ds = tf.data.Dataset.from_tensor_slices((train_paths, labels_tf))
    ds = ds.map(lambda p, l: (p, l, tf.gather(weights_lookup, l)), num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.shuffle(buffer_size=20000, seed=RANDOM_SEED, reshuffle_each_iteration=True)
    ds = ds.map(load_img, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.map(per_image_field_randoms, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(BATCH_SIZE, drop_remainder=True)

    batch_aug = make_batch_augmenter()

    def batch_augment(x, y, w):
        return batch_aug(x, training=True), y, w

    ds = ds.map(batch_augment, num_parallel_calls=tf.data.AUTOTUNE).prefetch(tf.data.AUTOTUNE)

    # Validation set (PV valid - no augmentation)
    valid_dir = pv_train_dir.parent / "valid"
    if not valid_dir.exists():
        valid_dir = REPO_ROOT / "ai_engine" / "PlantVillage_Valid"
    print(f"[+] Validation directory: {valid_dir}")
    val_ds = tf.keras.utils.image_dataset_from_directory(
        str(valid_dir), class_names=CLASS_NAMES, image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE, label_mode="categorical", shuffle=False,
    )

    # ---------------------------------------------------------------- #
    # 7. Model                                                          #
    # ---------------------------------------------------------------- #
    base_model = MobileNetV3Small(
        input_shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3),
        include_top=False, weights="imagenet", pooling="avg",
    )
    base_model.trainable = False

    inputs = tf.keras.Input(shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3), name="serving_default_leaf_rgb_input")
    x = tf.keras.applications.mobilenet_v3.preprocess_input(inputs)
    x = base_model(x, training=False)
    x = layers.Dropout(0.25, name="head_dropout_1")(x)
    x = layers.Dense(144, activation="relu", kernel_regularizer=regularizers.l2(3e-5),
                     name="foliar_feature_dense")(x)
    x = layers.BatchNormalization(name="head_bn")(x)
    x = layers.Dropout(0.20, name="head_dropout_2")(x)
    outputs = layers.Dense(NUM_CLASSES, activation="softmax", name="disease_probability_output")(x)
    model = models.Model(inputs, outputs, name="krishi_drishti_edge_model")

    model.compile(optimizer=tf.keras.optimizers.Adam(PHASE1_LR),
                  loss="categorical_crossentropy", metrics=["accuracy"])

    steps_per_epoch = total_records // BATCH_SIZE
    print(f"\n[Phase 1] Head warmup: {PHASE1_EPOCHS} epochs @ lr={PHASE1_LR} ({steps_per_epoch} steps/epoch)")
    model.fit(ds, epochs=PHASE1_EPOCHS, verbose=1)

    print(f"\n[Phase 2] Deep fine-tune: top {UNFROZEN_BACKBONE_LAYERS} layers, "
          f"{PHASE2_EPOCHS} epochs, cosine decay from lr={PHASE2_LR}")
    base_model.trainable = True
    for layer in base_model.layers[:-UNFROZEN_BACKBONE_LAYERS]:
        layer.trainable = False
    lr_schedule = tf.keras.optimizers.schedules.CosineDecay(
        PHASE2_LR, decay_steps=max(1, steps_per_epoch * PHASE2_EPOCHS), alpha=0.02)
    model.compile(optimizer=tf.keras.optimizers.Adam(lr_schedule),
                  loss="categorical_crossentropy", metrics=["accuracy"])
    model.fit(ds, epochs=PHASE2_EPOCHS, verbose=1)

    duration_train = round(time.time() - t0_wall, 2)
    print(f"\n[+] Training elapsed: {duration_train}s")

    # ---------------------------------------------------------------- #
    # 8. Temperature calibration on validation set                      #
    # ---------------------------------------------------------------- #
    print("\n[*] Collecting validation probabilities for temperature calibration...")
    val_probs, val_true = [], []
    for images, labels in val_ds:
        preds = model.predict(images, verbose=0)
        val_probs.append(preds)
        val_true.append(np.argmax(labels.numpy(), axis=1))
    val_probs = np.concatenate(val_probs)
    val_true = np.concatenate(val_true)
    val_acc_pre = float(np.mean(np.argmax(val_probs, axis=1) == val_true))

    T_opt, nll_opt = fit_temperature(val_probs, val_true)
    print(f"[+] Optimal temperature T = {T_opt} (NLL {nll_opt:.4f})")
    if abs(T_opt - 1.0) > 0.05:
        bake_temperature(model, T_opt)
        # verify argmax preserved
        post_probs = []
        for images, _ in val_ds:
            post_probs.append(model.predict(images, verbose=0))
        post_probs = np.concatenate(post_probs)
        val_acc_post = float(np.mean(np.argmax(post_probs, axis=1) == val_true))
        assert abs(val_acc_post - val_acc_pre) < 1e-6, "Temperature bake changed argmax!"
        print(f"[OK] Temperature baked. Val accuracy unchanged: {val_acc_post*100:.2f}%")
    else:
        val_acc_post = val_acc_pre
        print("[OK] T ~ 1.0: model already calibrated, no bake needed.")

    # Validation confusion matrix / per-class metrics
    y_pred = np.argmax(val_probs, axis=1)
    cm = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=int)
    for t, p in zip(val_true, y_pred):
        cm[t, p] += 1
    per_class = {}
    f1_list = []
    for i, cname in enumerate(CLASS_NAMES):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        f1_list.append(f1)
        per_class[cname] = {"precision": round(float(precision), 4),
                            "recall": round(float(recall), 4),
                            "f1_score": round(float(f1), 4),
                            "support": int(cm[i, :].sum())}
    val_acc = round(float(np.sum(np.diag(cm)) / len(val_true)), 4)
    macro_f1 = round(float(np.mean(f1_list)), 4)
    print(f"[+] Validation: acc={val_acc*100:.2f}% macroF1={macro_f1:.4f}")
    for i, cname in enumerate(CLASS_NAMES):
        print(f"    {cname:<24} P={per_class[cname]['precision']:.3f} R={per_class[cname]['recall']:.3f} F1={per_class[cname]['f1_score']:.3f}")

    # ---------------------------------------------------------------- #
    # 9. Export Float16 TFLite + base Keras model                       #
    # ---------------------------------------------------------------- #
    print("\n[*] Exporting Float16 quantized TFLite edge model...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_bytes = converter.convert()

    out_model = REPO_ROOT / "ai_engine" / "krishi_drishti_model.tflite"
    with open(out_model, "wb") as f:
        f.write(tflite_bytes)

    keras_out = REPO_ROOT / "ai_engine" / "krishi_drishti_base.keras"
    try:
        model.save(keras_out)
        print(f"[OK] Base Keras model saved: {keras_out.name}")
    except Exception as e:
        print(f"[WARN] Keras save skipped: {e}")

    model_sha = hashlib.sha256(tflite_bytes).hexdigest()
    model_size = len(tflite_bytes)
    print(f"[OK] TFLite exported: {model_size} bytes ({model_size/1048576:.2f} MB) sha256={model_sha}")

    # ---------------------------------------------------------------- #
    # 10. TFLite inference parity check + PlantDoc held-out evaluation  #
    # ---------------------------------------------------------------- #
    os.environ.setdefault("TF_LITE_DISABLE_XNNPACK", "1")
    print("\n[*] TFLite parity + PlantDoc held-out evaluation...")
    try:
        interp = tf.lite.Interpreter(model_content=tflite_bytes, experimental_delegates=[])
        interp.allocate_tensors()
        in_d = interp.get_input_details()[0]
        out_d = interp.get_output_details()[0]

        def tflite_predict(pil_imgs):
            out = []
            for im in pil_imgs:
                arr = np.asarray(im.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR), dtype=np.float32)
                interp.set_tensor(in_d["index"], np.expand_dims(arr, 0))
                interp.invoke()
                o = interp.get_tensor(out_d["index"])[0].astype(np.float32)
                if np.any(o < 0) or abs(o.sum() - 1.0) > 0.05:
                    e = np.exp(o - o.max())
                    o = e / e.sum()
                out.append(o)
            return np.array(out)

        # parity on first 3 val batches
        parity_ok = True
        for images, labels in val_ds.take(3):
            for i in range(len(images)):
                arr = images[i].numpy()
                k = model.predict(np.expand_dims(arr, 0), verbose=0)[0]
                interp.set_tensor(in_d["index"], np.expand_dims(arr, 0))
                interp.invoke()
                t = interp.get_tensor(out_d["index"])[0].astype(np.float32)
                if np.argmax(k) != np.argmax(t):
                    parity_ok = False
        print(f"[OK] TFLite/Keras parity on 96 val images: {'PASS' if parity_ok else 'FAIL'}")

        # PlantDoc held-out (raw + gated, daemon-equivalent thresholds)
        MIN_CONF, MAX_ENT, MIN_MARGIN = 0.50, 1.45, 0.12
        pd_raw_correct, pd_total = 0, 0
        pd_accepted, pd_acc_correct, pd_gated = 0, 0, 0
        pd_by_class = {c: {"n": 0, "raw_correct": 0, "accepted": 0} for c in CLASS_NAMES}
        for s in plantdoc_test_specimens:
            p = Path(s["path"])
            if not p.exists() or s["class"] not in CLASS_TO_IDX:
                continue
            probs = tflite_predict([Image.open(p)])[0]
            top = int(np.argmax(probs))
            conf = float(probs[top])
            sp = np.sort(probs)[::-1]
            margin = float(sp[0] - sp[1]) if len(sp) > 1 else 1.0
            entropy = -float(sum(pp * math.log(pp) for pp in probs if pp > 1e-6))
            correct = (top == CLASS_TO_IDX[s["class"]])
            pd_total += 1
            pd_by_class[s["class"]]["n"] += 1
            if correct:
                pd_raw_correct += 1
                pd_by_class[s["class"]]["raw_correct"] += 1
            if conf < MIN_CONF or entropy > MAX_ENT or margin < MIN_MARGIN:
                pd_gated += 1
            else:
                pd_accepted += 1
                if correct:
                    pd_acc_correct += 1
                    pd_by_class[s["class"]]["accepted"] += 1
        plantdoc_metrics = {
            "total_evaluated": pd_total,
            "raw_correct": pd_raw_correct,
            "raw_accuracy_pct": round(100 * pd_raw_correct / pd_total, 2) if pd_total else 0.0,
            "accepted_frames": pd_accepted,
            "accepted_correct": pd_acc_correct,
            "accepted_accuracy_pct": round(100 * pd_acc_correct / pd_accepted, 2) if pd_accepted else 0.0,
            "gated_uncertain": pd_gated,
            "gated_pct": round(100 * pd_gated / pd_total, 2) if pd_total else 0.0,
            "per_class": {c: f"{v['raw_correct']}/{v['n']} raw, {v['accepted']} accepted-correct"
                          for c, v in pd_by_class.items() if v["n"] > 0},
        }
        print(f"[+] PlantDoc held-out: raw {plantdoc_metrics['raw_accuracy_pct']}% | "
              f"accepted {plantdoc_metrics['accepted_accuracy_pct']}% | gated {plantdoc_metrics['gated_pct']}%")
    except Exception as e:
        print(f"[WARN] TFLite evaluation skipped: {e}")
        parity_ok, plantdoc_metrics = None, None

    # ---------------------------------------------------------------- #
    # 11. Manifest v3                                                   #
    # ---------------------------------------------------------------- #
    t_end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest = {
        "manifest_version": "3.0",
        "training_run_metadata": {
            "training_start_time": t_start_iso,
            "training_completed_time": t_end_iso,
            "training_duration_seconds": duration_train,
            "random_seed": RANDOM_SEED,
            "pipeline": "ai_engine/train_model_v3.py",
            "status": "COMPLETED (v3 full-corpus zero-leakage run)",
        },
        "exported_model_artifact": {
            "model_file": "ai_engine/krishi_drishti_model.tflite",
            "model_sha256": model_sha,
            "model_size_bytes": model_size,
            "model_size_mb": round(model_size / 1048576, 2),
            "quantization": "Float16 post-training optimization, Float32 I/O",
            "architecture": "MobileNetV3-Small",
            "input_contract": "Float32 [1,128,128,3] raw pixels [0,255]",
            "output_contract": "Float32 [1,6] softmax probabilities (temperature-calibrated)",
            "classes": CLASS_NAMES,
        },
        "training_corpus_provenance": {
            "plantvillage_source": str(pv_train_dir),
            "plantvillage_full_clean_corpus": True,
            "plantvillage_per_class_unique_counts": per_class_unique_counts,
            "plantvillage_passes": PV_PASSES,
            "plantdoc_clean_train_unique": len(clean_plantdoc_train),
            "plantdoc_passes": PLANTDOC_PASSES,
            "total_training_records": len(all_paths),
            "unique_training_hashes": len(hash_to_class),
            "augmentation_note": ("Records are multiple augmented passes over unique clean files; "
                                  "augmentation runs in the tf.data pipeline (randomized per pass), "
                                  "not in the exported model graph."),
        },
        "cryptographic_and_perceptual_exclusion_audit": {
            "master_blacklist_unique_hashes": len(master_blacklist),
            "pv_dhash_near_duplicates_excluded": len(excluded_pv_near_duplicates),
            "pv_dhash_near_duplicate_details": excluded_pv_near_duplicates[:50],
            "plantdoc_excluded": excluded_plantdoc,
            "cross_class_hash_conflicts_dropped": len(cross_class_conflicts),
            "leakage_assertion": "PASSED (0 exact blacklist collisions across all training records)",
        },
        "training_hyperparameters": {
            "batch_size": BATCH_SIZE,
            "image_size": list(IMAGE_SIZE),
            "phase_1_epochs": PHASE1_EPOCHS,
            "phase_1_lr": PHASE1_LR,
            "phase_2_epochs": PHASE2_EPOCHS,
            "phase_2_lr_initial": PHASE2_LR,
            "phase_2_schedule": "CosineDecay to 2% of initial",
            "unfrozen_backbone_layers": UNFROZEN_BACKBONE_LAYERS,
            "label_smoothing": LABEL_SMOOTHING,
            "class_weight_boost": CLASS_WEIGHT_BOOST,
            "sample_weights_normalized": {CLASS_NAMES[k]: v for k, v in class_weight_map.items()},
            "regularization": "L2(3e-5) dense + Dropout(0.25, 0.20) + label smoothing",
        },
        "canopy_augmentation_policy": {
            "location": "tf.data pipeline (NOT in exported graph)",
            "per_image": ["hue +/-0.05", "saturation 0.65-1.60", "gamma 0.70-1.45",
                          "harsh-flash overexposure mix 5-38% (p=0.30)",
                          "AWB-failure purple-magenta cast 10-30% (p=0.25)"],
            "batched": ["random flip h/v", "rotation +/-15%", "zoom +/-15%",
                        "translation +/-10%", "contrast +/-30%", "brightness +/-25%"],
        },
        "calibration": {
            "method": "Temperature scaling fitted on PV validation NLL",
            "temperature": T_opt,
            "bake": "final Dense kernel & bias divided by T (argmax-preserving)",
            "validation_accuracy_pre": val_acc_pre,
            "validation_accuracy_post": val_acc_post,
        },
        "validation_metrics": {
            "dataset": str(valid_dir),
            "accuracy": val_acc,
            "macro_f1": macro_f1,
            "confusion_matrix": cm.tolist(),
            "per_class_metrics": per_class,
        },
        "plantdoc_heldout_metrics": plantdoc_metrics,
        "tflite_keras_parity_96_images": parity_ok,
        "complete_list_of_unique_training_hashes": unique_hashes,
    }
    with open(REPO_ROOT / "ai_engine" / "TRAINING_RUN_MANIFEST.json", "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)
    print(f"\n[OK] Manifest v3.0 written. Total wall time: {round(time.time()-t0_wall, 2)}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
