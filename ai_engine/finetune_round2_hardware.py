"""
================================================================================
 KRISHI-DRISHTI :: ROUND-2 HARDWARE-DOMAIN FINE-TUNE (ESP32-CAM SD SCANS)
================================================================================
 Round 1 (train_model_v3.py) produced the v3 base model from the full
 PV-Solanaceae + PlantDoc corpus on Colab T4.

 Round 2 (this script) adapts the base model to the *hardware domain* using
 the 44 SD-card scans captured with the actual ESP32-CAM:

   - 22 screen-scanned diseased leaves  -> pseudo-labeled by the v3 model
     (user decision: "Accept & classify" - screen scans are valid input)
   -  3 direct healthy leaves (38/39/43) -> forced Tomato___healthy
   -  1 direct yellow leaf  (44)         -> model pseudo-label (logged)
   -  1 unrecoverable haze  (42)         -> EXCLUDED (training + calibration)
   - 16 non-leaf frames (faces/palms/ceilings/blank vignettes) -> NOT trained;
     reserved as OOD-rejection calibration targets for the daemon gate
   -  1 mixed outdoor frame (35)         -> NOT trained; gate calibration only

 Pipeline:
   1. Load base .keras model (Float32 [1,128,128,3] raw [0,255] -> [1,6])
   2. Pseudo-label scans with the base model (confidence-logged)
   3. Light head-only fine-tune: 26 hardware scans (heavy screen/flash
      augmentation, up-weighted) + small PV replay set (drift guard)
   4. Re-fit temperature on the FULL local PV valid set, bake into head
   5. Export FP16 TFLite under the SAME filename + I/O contract
   6. Gate calibration sweep over the 44 scans -> recommended thresholds
   7. Round-2 manifest + before/after scan report

 Run:  python ai_engine/finetune_round2_hardware.py
================================================================================
"""

import json
import math
import os
import random
import shutil
import time
from pathlib import Path

import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow.keras import regularizers

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_DIR = REPO_ROOT / "ai_engine"
TESTS_DIR = REPO_ROOT / "tests"

BASE_MODEL_PATH = AI_DIR / "krishi_drishti_base.keras"
OUT_TFLITE_PATH = AI_DIR / "krishi_drishti_model.tflite"
BACKUP_TFLITE_PATH = AI_DIR / "krishi_drishti_model_round1.tflite"
SCAN_DIR = Path("E:/")
GROUND_TRUTH_PATH = TESTS_DIR / "sd_scan_ground_truth.json"

IMAGE_SIZE = (128, 128)
NUM_CLASSES = 6
CLASS_NAMES = [
    "Tomato___Late_blight",
    "Tomato___Early_blight",
    "Tomato___healthy",
    "Potato___Late_blight",
    "Potato___Early_blight",
    "Potato___healthy",
]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASS_NAMES)}

RANDOM_SEED = 42
SCAN_PASSES = 40          # augmented passes over each hardware scan
SCAN_SAMPLE_WEIGHT = 3.0  # hardware scans dominate the replay mix
REPLAY_PER_CLASS = 12     # PV replay images per class (drift guard)
REPLAY_PASSES = 3
BATCH_SIZE = 8
EPOCHS = 40
LR_HEAD = 2e-4
LABEL_SMOOTHING = 0.08

# Daemon gate grid (same semantics as krishi_ai_daemon.py)
CONF_GRID = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
ENTROPY_GRID = [1.20, 1.30, 1.45, 1.60, 1.75]
MARGIN_GRID = [0.08, 0.12, 0.16, 0.20, 0.25]


def softmax_np(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(probs, y_true_idx):
    """Fit T minimizing NLL of softmax(log(p)/T) (same method as v3)."""
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
    """Scale final Dense kernel & bias by 1/T (argmax-preserving)."""
    out_layer = model.get_layer("disease_probability_output")
    kernel, bias = out_layer.get_weights()
    out_layer.set_weights([kernel / T, bias / T])


def tflite_convert(model):
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    return converter.convert()


def make_tflite_predictor(tflite_bytes):
    """Interpreter predictor with the raw [0,255] float32 input contract."""
    interp = tf.lite.Interpreter(model_content=tflite_bytes)
    interp.allocate_tensors()
    in_d = interp.get_input_details()[0]
    out_d = interp.get_output_details()[0]

    def predict(pil_imgs):
        out = []
        for im in pil_imgs:
            arr = np.asarray(
                im.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR), dtype=np.float32
            )
            interp.set_tensor(in_d["index"], np.expand_dims(arr, 0))
            interp.invoke()
            o = interp.get_tensor(out_d["index"])[0].astype(np.float32)
            if np.any(o < 0) or abs(float(o.sum()) - 1.0) > 0.05:
                e = np.exp(o - o.max())
                o = e / e.sum()
            out.append(o)
        return np.array(out)

    return predict


def gate_stats(probs):
    top = int(np.argmax(probs))
    conf = float(probs[top])
    sp = np.sort(probs)[::-1]
    margin = float(sp[0] - sp[1]) if len(sp) > 1 else 1.0
    entropy = -float(sum(p * math.log(p) for p in probs if p > 1e-6))
    return top, conf, margin, entropy


def scan_augment_image(img):
    """Screen/hardware-domain augmentation mirroring the SD-scan artifacts:
    moire-like local contrast stress, harsh flash glare, purple/magenta AWB
    cast, jitter, mild blur. Operates on a PIL image; returns PIL."""
    arr = np.asarray(img.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR), dtype=np.float32)

    # harsh flash / overexposure blend
    if random.random() < 0.45:
        amt = random.uniform(0.08, 0.45)
        arr = arr * (1.0 - amt) + 255.0 * amt

    # purple-magenta cast (green suppressed vs red+blue)
    if random.random() < 0.45:
        s = random.uniform(0.10, 0.35)
        arr = arr * np.array([1.0 + s * 0.40, 1.0 - s, 1.0 + s * 0.50], dtype=np.float32)

    # gamma response
    if random.random() < 0.5:
        gamma = random.uniform(0.65, 1.55)
        arr = np.power(np.clip(arr / 255.0, 0, 1), gamma) * 255.0

    arr = np.clip(arr, 0, 255)
    im = Image.fromarray(arr.astype(np.uint8))

    # geometric jitter
    if random.random() < 0.85:
        im = im.transform(
            IMAGE_SIZE, Image.AFFINE,
            (1.0, random.uniform(-0.08, 0.08), random.uniform(-8, 8),
             random.uniform(-0.08, 0.08), 1.0, random.uniform(-8, 8)),
            resample=Image.BILINEAR,
        )
    if random.random() < 0.5:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)

    # slight defocus (camera/screen)
    if random.random() < 0.35:
        from PIL import ImageFilter
        im = im.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.4, 1.2)))

    return im


def main():
    t0 = time.time()
    print("=" * 84)
    print("  KRISHI-DRISHTI :: ROUND-2 HARDWARE-DOMAIN FINE-TUNE (SD SCANS)")
    print("=" * 84)
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    tf.random.set_seed(RANDOM_SEED)

    if not BASE_MODEL_PATH.exists():
        print(f"[FAIL] Base model not found: {BASE_MODEL_PATH}")
        return 1
    if not GROUND_TRUTH_PATH.exists():
        print(f"[FAIL] Ground truth not found: {GROUND_TRUTH_PATH}")
        return 1

    gt = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- #
    # 1. Collect scans + labels                                        #
    # ---------------------------------------------------------------- #
    screen_scans = gt["categories"]["screen_leaf_diseased"]["scans"]
    symptom_groups = gt["categories"]["screen_leaf_diseased"]["symptom_groups"]
    direct_leaf = gt["categories"]["direct_leaf"]["scans"]
    non_leaf = gt["categories"]["non_leaf_noise"]["scans"]
    mixed_outdoor = gt["categories"]["mixed_outdoor"]["scans"]

    def scan_path(n):
        return SCAN_DIR / f"scan_{n:06d}.jpg"

    # base-model pseudo-labeling (keras)
    print("\n[*] Loading base model for pseudo-labeling...")
    base_model = tf.keras.models.load_model(BASE_MODEL_PATH, compile=False)

    def keras_predict(paths):
        arrs = []
        for p in paths:
            img = Image.open(p).convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR)
            arrs.append(np.asarray(img, dtype=np.float32))
        return base_model.predict(np.array(arrs), verbose=0)

    hardware_train = []  # (scan_number, label_idx, pseudo_conf, source)
    print("\n[*] Pseudo-labeling hardware scans with the v3 base model...")

    # screen scans: model argmax (user-approved accept & classify)
    screen_paths = [scan_path(n) for n in screen_scans]
    screen_probs = keras_predict(screen_paths)
    for n, probs in zip(screen_scans, screen_probs):
        top, conf, margin, entropy = gate_stats(probs)
        hardware_train.append({
            "scan": n, "path": str(scan_path(n)), "label": top,
            "label_name": CLASS_NAMES[top], "pseudo_conf": round(conf, 4),
            "margin": round(margin, 4), "entropy": round(entropy, 4),
            "source": "screen_pseudo",
        })
        print(f"    scan_{n:06d} -> {CLASS_NAMES[top]:24s} conf={conf:.3f} margin={margin:.3f}")

    # direct healthy leaves: forced healthy
    for s in ("38", "39", "43"):
        p = scan_path(int(s))
        if p.exists():
            hardware_train.append({
                "scan": int(s), "path": str(p), "label": CLASS_TO_IDX["Tomato___healthy"],
                "label_name": "Tomato___healthy", "pseudo_conf": 1.0,
                "source": "direct_forced_healthy",
            })
            print(f"    scan_{s} -> Tomato___healthy (forced)")

    # scan 44: model pseudo-label
    p44 = scan_path(44)
    if p44.exists():
        probs = keras_predict([p44])[0]
        top, conf, _, _ = gate_stats(probs)
        hardware_train.append({
            "scan": 44, "path": str(p44), "label": top,
            "label_name": CLASS_NAMES[top], "pseudo_conf": round(conf, 4),
            "source": "direct_pseudo_44",
        })
        print(f"    scan_000044 -> {CLASS_NAMES[top]:24s} conf={conf:.3f} (pseudo)")

    print(f"[OK] Hardware training pool: {len(hardware_train)} scans "
          f"({sum(1 for h in hardware_train if h['source'] == 'screen_pseudo')} screen, "
          f"{sum(1 for h in hardware_train if h['source'] != 'screen_pseudo')} direct)")

    # gate-calibration pool: non-leaf + mixed + discard 42 (NOT trained)
    gate_pool = []
    for s in list(non_leaf.keys()) + list(mixed_outdoor.keys()) + ["42"]:
        n = int(s)
        p = scan_path(n)
        if p.exists():
            gate_pool.append({"scan": n, "path": str(p), "kind": non_leaf.get(s, mixed_outdoor.get(s, "discard_haze"))})
    print(f"[+] Gate calibration pool: {len(gate_pool)} non-leaf/OOD scans (excluded from training)")

    # ---------------------------------------------------------------- #
    # 2. Build fine-tune dataset: scans x passes + PV replay           #
    # ---------------------------------------------------------------- #
    print("\n[*] Assembling round-2 dataset (hardware scans + PV replay)...")
    pv_dir = Path(os.environ.get("KAGGLEHUB_CACHE", str(Path.home() / ".cache" / "kagglehub"))) \
        / "datasets" / "vipoooool" / "new-plant-diseases-dataset" / "versions" / "2" \
        / "New Plant Diseases Dataset(Augmented)" / "New Plant Diseases Dataset(Augmented)" / "train"
    if not pv_dir.exists():
        pv_dir = AI_DIR / "PlantVillage_Train"
    if not pv_dir.exists():
        print("[FAIL] PV train dir not found locally; cannot build replay set")
        return 1

    replay = []
    for cname in CLASS_NAMES:
        cdir = pv_dir / cname
        if not cdir.exists():
            print(f"[FAIL] Missing PV class dir: {cdir}")
            return 1
        files = sorted([f for f in cdir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        random.shuffle(files)
        for f in files[:REPLAY_PER_CLASS]:
            replay.append((str(f), CLASS_TO_IDX[cname]))

    records = []
    for h in hardware_train:
        for _ in range(SCAN_PASSES):
            records.append((h["path"], h["label"], SCAN_SAMPLE_WEIGHT))
    for p, l in replay:
        for _ in range(REPLAY_PASSES):
            records.append((p, l, 1.0))
    random.shuffle(records)
    print(f"[+] Round-2 corpus: {len(records)} records "
          f"({sum(1 for r in records if r[2] == SCAN_SAMPLE_WEIGHT)} scan-weighted, "
          f"{sum(1 for r in records if r[2] == 1.0)} PV replay)")

    counts = {}
    for h in hardware_train:
        counts[h["label_name"]] = counts.get(h["label_name"], 0) + 1
    print(f"[+] Hardware label distribution: {counts}")

    def load_and_aug(p):
        img = Image.open(p)
        return scan_augment_image(img)

    def ds_gen():
        for p, l, w in records:
            img = load_and_aug(p)
            arr = np.asarray(img, dtype=np.float32)
            y = np.zeros(NUM_CLASSES, dtype=np.float32)
            y[l] = 1.0 - LABEL_SMOOTHING + LABEL_SMOOTHING / NUM_CLASSES
            yield arr, y, np.float32(w)

    ds = tf.data.Dataset.from_generator(
        ds_gen,
        output_signature=(
            tf.TensorSpec(shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3), dtype=tf.float32),
            tf.TensorSpec(shape=(NUM_CLASSES,), dtype=tf.float32),
            tf.TensorSpec(shape=(), dtype=tf.float32),
        ),
    ).shuffle(2048, seed=RANDOM_SEED).batch(BATCH_SIZE, drop_remainder=False).prefetch(tf.data.AUTOTUNE)

    steps_per_epoch = math.ceil(len(records) / BATCH_SIZE)

    # PV valid for drift guard
    valid_dir = pv_dir.parent / "valid"
    if not valid_dir.exists():
        valid_dir = AI_DIR / "PlantVillage_Valid"
    val_ds = tf.keras.utils.image_dataset_from_directory(
        str(valid_dir), class_names=CLASS_NAMES, image_size=IMAGE_SIZE,
        batch_size=32, label_mode="categorical", shuffle=False,
    )

    # ---------------------------------------------------------------- #
    # 3. Head-only fine-tune                                           #
    # ---------------------------------------------------------------- #
    print(f"\n[Phase R2] Head-only fine-tune: {EPOCHS} epochs @ lr={LR_HEAD} "
          f"({steps_per_epoch} steps/epoch, backbone frozen)")
    base_model.trainable = True
    for layer in base_model.layers:
        name = layer.name.lower()
        if any(k in name for k in ("foliar_feature_dense", "head_bn", "disease_probability_output",
                                   "head_dropout")):
            layer.trainable = True
        else:
            layer.trainable = False
    trainable = [l.name for l in base_model.layers if l.trainable]
    print(f"[+] Trainable layers: {trainable}")

    lr_sched = tf.keras.optimizers.schedules.CosineDecay(LR_HEAD, decay_steps=max(1, steps_per_epoch * EPOCHS), alpha=0.05)
    base_model.compile(optimizer=tf.keras.optimizers.Adam(lr_sched),
                       loss="categorical_crossentropy", metrics=["accuracy"])

    # weighted loss via sample weights passed through the dataset
    history = base_model.fit(ds, epochs=EPOCHS, verbose=2)

    # ---------------------------------------------------------------- #
    # 4. Temperature re-calibration on FULL local PV valid             #
    # ---------------------------------------------------------------- #
    print("\n[*] Re-fitting temperature on full local PV valid...")
    val_probs, val_true = [], []
    for images, labels in val_ds:
        val_probs.append(base_model.predict(images, verbose=0))
        val_true.append(np.argmax(labels.numpy(), axis=1))
    val_probs = np.concatenate(val_probs)
    val_true = np.concatenate(val_true)
    val_acc_pre = float(np.mean(np.argmax(val_probs, axis=1) == val_true))
    print(f"[+] PV valid accuracy (pre-bake): {val_acc_pre:.4f}")

    T_opt, nll_opt = fit_temperature(val_probs, val_true)
    print(f"[+] Optimal temperature T = {T_opt} (NLL {nll_opt:.4f})")
    if abs(T_opt - 1.0) > 0.05:
        bake_temperature(base_model, T_opt)
        post = []
        for images, _ in val_ds:
            post.append(base_model.predict(images, verbose=0))
        post = np.concatenate(post)
        val_acc_post = float(np.mean(np.argmax(post, axis=1) == val_true))
        assert abs(val_acc_post - val_acc_pre) < 1e-6, "Temperature bake changed argmax!"
        print(f"[OK] Temperature baked (argmax preserved, acc {val_acc_post:.4f})")
    else:
        print("[OK] T ~ 1.0, no bake needed")

    # ---------------------------------------------------------------- #
    # 5. Export FP16 TFLite (same filename + contract)                  #
    # ---------------------------------------------------------------- #
    if OUT_TFLITE_PATH.exists() and not BACKUP_TFLITE_PATH.exists():
        shutil.copy2(OUT_TFLITE_PATH, BACKUP_TFLITE_PATH)
        print(f"[+] Round-1 model backed up: {BACKUP_TFLITE_PATH.name}")

    tflite_bytes = tflite_convert(base_model)
    with open(OUT_TFLITE_PATH, "wb") as f:
        f.write(tflite_bytes)
    import hashlib
    model_sha = hashlib.sha256(tflite_bytes).hexdigest()
    print(f"[OK] Round-2 TFLite exported: {len(tflite_bytes)} bytes sha256={model_sha}")

    keras_out = AI_DIR / "krishi_drishti_base.keras"
    try:
        base_model.save(keras_out)
        print(f"[OK] Round-2 Keras model saved: {keras_out.name}")
    except Exception as e:
        print(f"[WARN] Keras save skipped: {e}")

    # ---------------------------------------------------------------- #
    # 6. Scan re-evaluation (new model, raw + gate)                     #
    # ---------------------------------------------------------------- #
    tfl_predict = make_tflite_predictor(tflite_bytes)

    print("\n[*] Re-evaluating all 44 SD scans with the round-2 model...")
    all_scans = []
    for h in hardware_train:
        all_scans.append({**h, "kind": h["source"]})
    for g in gate_pool:
        all_scans.append({**g, "label": None, "label_name": None, "pseudo_conf": None})
    # ensure full coverage (44 scans minus any missing files)
    for n in range(1, 45):
        p = scan_path(n)
        if p.exists() and not any(s["scan"] == n for s in all_scans):
            all_scans.append({"scan": n, "path": str(p), "kind": "unlabeled", "label": None})

    rows = []
    for s in sorted(all_scans, key=lambda x: x["scan"]):
        probs = tfl_predict([Image.open(s["path"])])[0]
        top, conf, margin, entropy = gate_stats(probs)
        rows.append({
            "scan": s["scan"], "kind": s.get("kind", "?"),
            "pred": CLASS_NAMES[top], "conf": round(conf, 4),
            "margin": round(margin, 4), "entropy": round(entropy, 4),
            "expected": s.get("label_name"),
        })

    print(f"\n{'scan':>10} {'kind':22} {'prediction':24} {'conf':>6} {'margin':>7} {'entropy':>7}")
    for r in rows:
        print(f"{r['scan']:>10} {r['kind']:22} {r['pred']:24} {r['conf']:>6.3f} {r['margin']:>7.3f} {r['entropy']:>7.3f}")

    # pseudo-label agreement on hardware scans
    agree = sum(1 for r in rows if r["expected"] is not None and r["pred"] == r["expected"])
    labeled = sum(1 for r in rows if r["expected"] is not None)
    if labeled:
        print(f"[+] Pseudo-label agreement after fine-tune: {agree}/{labeled}")

    # ---------------------------------------------------------------- #
    # 7. Gate threshold sweep                                          #
    # ---------------------------------------------------------------- #
    print("\n[*] Gate threshold sweep (reject ALL non-leaf/OOD, accept hardware scans)...")
    ood_rows = [r for r in rows if r["kind"] in
                [g["kind"] for g in gate_pool] or r["scan"] in [g["scan"] for g in gate_pool]]
    hw_rows = [r for r in rows if r["expected"] is not None]
    best = None
    sweep = []
    for c in CONF_GRID:
        for e in ENTROPY_GRID:
            for m in MARGIN_GRID:
                rej_ood = sum(1 for r in ood_rows if r["conf"] < c or r["entropy"] > e or r["margin"] < m)
                acc_hw = sum(1 for r in hw_rows if r["conf"] >= c and r["entropy"] <= e and r["margin"] >= m)
                score = (rej_ood, acc_hw)
                sweep.append({"conf": c, "entropy": e, "margin": m,
                              "ood_rejected": rej_ood, "ood_total": len(ood_rows),
                              "hw_accepted": acc_hw, "hw_total": len(hw_rows)})
                if best is None or score > best[0]:
                    best = (score, {"conf": c, "entropy": e, "margin": m})
    print(f"[+] Best gate: reject {best[0][0]}/{len(ood_rows)} OOD, accept {best[0][1]}/{len(hw_rows)} hardware "
          f"-> MIN_CONFIDENCE={best[1]['conf']}, MAX_ENTROPY={best[1]['entropy']}, MIN_MARGIN={best[1]['margin']}")
    for s in sweep:
        if s["ood_rejected"] == len(ood_rows):
            print(f"    full-OOD-reject candidate: conf={s['conf']:.2f} ent={s['entropy']:.2f} marg={s['margin']:.2f}"
                  f" -> accepts {s['hw_accepted']}/{s['hw_total']}")

    # ---------------------------------------------------------------- #
    # 8. Manifest                                                      #
    # ---------------------------------------------------------------- #
    manifest = {
        "manifest_version": "3.1-round2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_model": "krishi_drishti_base.keras (v3 Colab full-corpus run)",
        "round2_tflite_sha256": model_sha,
        "round2_tflite_size_bytes": len(tflite_bytes),
        "temperature": T_opt,
        "hardware_scans_trained": len(hardware_train),
        "hardware_label_distribution": counts,
        "gate_sweep_best": best[1],
        "gate_sweep_full_ood_reject_candidates": [
            s for s in sweep if s["ood_rejected"] == len(ood_rows)
        ][:20],
        "pv_valid_accuracy_after_round2": round(val_acc_pre, 4),
        "scan_rows": rows,
        "wall_time_seconds": round(time.time() - t0, 1),
        "io_contract": "Float32 [1,128,128,3] raw [0,255] -> [1,6] softmax (unchanged)",
    }
    out_manifest = AI_DIR / "ROUND2_FINETUNE_MANIFEST.json"
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n[OK] Round-2 manifest written: {out_manifest.name}")
    print(f"[OK] Total wall time: {manifest['wall_time_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
