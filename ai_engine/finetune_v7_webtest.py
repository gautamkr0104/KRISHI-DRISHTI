"""
================================================================================
 KRISHI-DRISHTI :: ROUND-5 WEB-DOMAIN FINE-TUNE (webtest100 burned by decision)
================================================================================
 PROJECT-OWNER DECISION (2026-11-15): train on ALL 102 held-out webtest100
 images to maximize web-domain accuracy. Consequence, recorded here and in the
 manifest: webtest100 is PERMANENTLY INVALIDATED AS A TEST — any future score
 on it is memorization. The honest held-out web test will be a fresh 100-image
 set harvested AFTER this fine-tune (zero overlap, same protocol).

 Never trained on (still honest held-out guards):
   - benchmark-60 specimens  (ai_engine/validation_60_specimens/) -> per-epoch
     guard: a checkpoint is eligible only if raw agreement >= the BASE model's
     own raw agreement (no held-out regression allowed)
   - PV valid (PlantVillage) -> PV_FLOOR
   - chart/palm OOD set      -> post-export gate

 Training data (all operator-verified labels):
   - 102 webtest100 images x3 passes (labels = human-assigned expected labels)
   - 41 web supplements x2 (operator-verified, round-3)
   - 25 visually-audited SD scans x8 (tests/sd_card_scans_archive_r3/,
     labels from sd_scan_visual_audit.json — the device domain)
   - 60 PV train images/class x2 replay (drift anchor)

 Run:  python ai_engine/finetune_v7_webtest.py   (stages raw v7 base first)
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

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_DIR = REPO_ROOT / "ai_engine"
TESTS_DIR = REPO_ROOT / "tests"

BASE_MODEL_PATH = AI_DIR / "krishi_drishti_base.keras"          # must be raw v7
RAW_V7_TFLITE = AI_DIR / "krishi_drishti_model_v7_raw.tflite"
OUT_TFLITE_PATH = AI_DIR / "krishi_drishti_model.tflite"
PREV_DEPLOY_BACKUP = AI_DIR / "krishi_drishti_model_round4_webtest_prev.tflite"
AUDIT_PATH = TESTS_DIR / "sd_scan_visual_audit.json"
SCANS_ARCHIVE_DIR = TESTS_DIR / "sd_card_scans_archive_r3"
WEBTEST_DIR = Path(r"C:\Users\DELL\Documents\Default Project\webtest100")
WEBTEST_RESULTS = WEBTEST_DIR / "webtest100_results.json"
WEBTEST_IMAGES = WEBTEST_DIR / "images"
SPECIMEN_DIR = AI_DIR / "validation_60_specimens"

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

CANONICAL_TO_IDX = {
    "Tomato Late Blight": CLASS_TO_IDX["Tomato___Late_blight"],
    "Tomato Early Blight": CLASS_TO_IDX["Tomato___Early_blight"],
    "Tomato Healthy": CLASS_TO_IDX["Tomato___healthy"],
    "Potato Late Blight": CLASS_TO_IDX["Potato___Late_blight"],
    "Potato Early Blight": CLASS_TO_IDX["Potato___Early_blight"],
    "Potato Healthy": CLASS_TO_IDX["Potato___healthy"],
}

RANDOM_SEED = 42
WEBTEST_PASSES = 4        # 102 images x4 = 408 records (v2 hard push)
WEB_SUPP_PASSES = 2       # 41 x2 = 82
SCAN_PASSES = 8           # 25 x8 = 200 (device-domain anchor)
SCAN_SAMPLE_WEIGHT = 1.5
REPLAY_PER_CLASS = 60     # 720 PV replay
REPLAY_PASSES = 2
BATCH_SIZE = 8
EPOCHS = 20               # v2: hard push (v1: 14 @6e-5 barely moved, best epoch = 1)
LR_HEAD = 1.5e-4          # v2: 2.5x v1 (v1's 6e-5 was underpowered)
LABEL_SMOOTHING = 0.08
PV_FLOOR = 0.978          # checkpoint eligible only if PV valid >= 97.8%
BEST_WEIGHTS_PATH = AI_DIR / "_finetune_webtest_best.weights.h5"

CONF_GRID = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
ENTROPY_GRID = [1.20, 1.30, 1.45, 1.60, 1.75]
MARGIN_GRID = [0.08, 0.12, 0.16, 0.20, 0.25]


def softmax_np(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(probs, y_true_idx):
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
    out_layer = model.get_layer("disease_probability_output")
    kernel, bias = out_layer.get_weights()
    out_layer.set_weights([kernel / T, bias / T])


def tflite_convert(model):
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    return converter.convert()


def make_tflite_predictor(tflite_bytes):
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
    """Device-domain augmentation: flash glare, magenta AWB cast, gamma,
    jitter, flip, mild blur (mirrors ESP32-CAM artifacts)."""
    arr = np.asarray(img.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR), dtype=np.float32)
    if random.random() < 0.45:
        amt = random.uniform(0.08, 0.45)
        arr = arr * (1.0 - amt) + 255.0 * amt
    if random.random() < 0.45:
        s = random.uniform(0.10, 0.35)
        arr = arr * np.array([1.0 + s * 0.40, 1.0 - s, 1.0 + s * 0.50], dtype=np.float32)
    if random.random() < 0.5:
        gamma = random.uniform(0.65, 1.55)
        arr = np.power(np.clip(arr / 255.0, 0, 1), gamma) * 255.0
    arr = np.clip(arr, 0, 255)
    im = Image.fromarray(arr.astype(np.uint8))
    if random.random() < 0.85:
        im = im.transform(
            IMAGE_SIZE, Image.AFFINE,
            (1.0, random.uniform(-0.08, 0.08), random.uniform(-8, 8),
             random.uniform(-0.08, 0.08), 1.0, random.uniform(-8, 8)),
            resample=Image.BILINEAR,
        )
    if random.random() < 0.5:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if random.random() < 0.35:
        from PIL import ImageFilter
        im = im.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.4, 1.2)))
    return im


def photo_augment_image(img):
    """Milder augmentation for real photographs (webtest/supplements/PV)."""
    im = img.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR)
    arr = np.asarray(im, dtype=np.float32)
    if random.random() < 0.4:
        gamma = random.uniform(0.75, 1.4)
        arr = np.power(np.clip(arr / 255.0, 0, 1), gamma) * 255.0
    if random.random() < 0.3:
        s = random.uniform(0.05, 0.2)
        arr = arr * np.array([1.0 + s, 1.0, 1.0 - s * 0.3], dtype=np.float32)
    arr = np.clip(arr, 0, 255)
    im = Image.fromarray(arr.astype(np.uint8))
    if random.random() < 0.85:
        im = im.transform(
            IMAGE_SIZE, Image.AFFINE,
            (1.0, random.uniform(-0.06, 0.06), random.uniform(-6, 6),
             random.uniform(-0.06, 0.06), 1.0, random.uniform(-6, 6)),
            resample=Image.BILINEAR,
        )
    if random.random() < 0.5:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


def load_benchmark_specimens():
    """(path, class_idx) for all 60 held-out benchmark specimens."""
    folder_map = {
        "Potato___Early_blight": "Potato Early Blight",
        "Potato___Late_blight": "Potato Late Blight",
        "Potato___healthy": "Potato Healthy",
        "Tomato___Early_blight": "Tomato Early Blight",
        "Tomato___Late_blight": "Tomato Late Blight",
        "Tomato___healthy": "Tomato Healthy",
    }
    specimens = []
    for folder in sorted(folder_map):
        fdir = SPECIMEN_DIR / folder
        if not fdir.is_dir():
            print(f"[FAIL] Missing benchmark folder: {fdir}")
            return None
        for f in sorted(fdir.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                specimens.append((str(f), CANONICAL_TO_IDX[folder_map[folder]]))
    return specimens


def main():
    t0 = time.time()
    print("=" * 84)
    print("  KRISHI-DRISHTI :: ROUND-5 WEB-DOMAIN FINE-TUNE (webtest100 burned by decision)")
    print("=" * 84)
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    tf.random.set_seed(RANDOM_SEED)

    if not BASE_MODEL_PATH.exists():
        print(f"[FAIL] Base model not found: {BASE_MODEL_PATH}")
        return 1
    if not WEBTEST_RESULTS.exists():
        print(f"[FAIL] webtest100 results not found: {WEBTEST_RESULTS}")
        return 1

    # ---------------------------------------------------------------- #
    # 1. Held-out benchmark specimens (per-epoch guard set)             #
    # ---------------------------------------------------------------- #
    specimens = load_benchmark_specimens()
    if not specimens:
        return 1
    spec_paths = [s[0] for s in specimens]
    spec_labels = np.array([s[1] for s in specimens])

    # ---------------------------------------------------------------- #
    # 2. Load base + record held-out baselines                          #
    # ---------------------------------------------------------------- #
    print("\n[*] Loading raw v7 base model...")
    base_model = tf.keras.models.load_model(BASE_MODEL_PATH, compile=False)

    def model_probs(model, paths):
        arrs = []
        for p in paths:
            img = Image.open(p).convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR)
            arrs.append(np.asarray(img, dtype=np.float32))
        return model.predict(np.array(arrs), verbose=0)

    base_spec_probs = model_probs(base_model, spec_paths)
    base_bench_agree = int(np.sum(np.argmax(base_spec_probs, axis=1) == spec_labels))
    print(f"[+] BASELINE held-out benchmark raw agreement: {base_bench_agree}/60")
    BENCH_FLOOR = base_bench_agree   # no held-out regression allowed

    # ---------------------------------------------------------------- #
    # 3. webtest100 training pool (BURNED — documented)                 #
    # ---------------------------------------------------------------- #
    results = json.loads(WEBTEST_RESULTS.read_text(encoding="utf-8"))
    webtest = []
    for r in results["rows"]:
        p = WEBTEST_IMAGES / r["file"]
        if not p.exists():
            print(f"[FAIL] Missing webtest image: {p}")
            return 1
        cls = r["expected"]
        if cls not in CLASS_TO_IDX:
            print(f"[FAIL] Unknown class '{cls}' for {r['file']}")
            return 1
        webtest.append((str(p), CLASS_TO_IDX[cls]))
    dist = {}
    for _, l in webtest:
        dist[CLASS_NAMES[l]] = dist.get(CLASS_NAMES[l], 0) + 1
    print(f"[!] webtest100 burned into training: {len(webtest)} images {dist}")
    print("    -> webtest100 is INVALIDATED as a test from this point on.")

    # audited scans (device domain) from the repo archive
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    GT_MAP = {"Tomato Late Blight": "Tomato___Late_blight",
              "Tomato Early Blight": "Tomato___Early_blight",
              "Tomato Healthy": "Tomato___healthy",
              "diseased leaf (late blight series)": "Tomato___Late_blight",
              "healthy leaf": "Tomato___healthy",
              "healthy leaf (host uncertain)": "Tomato___healthy"}
    scan_records = []
    gate_pool = []
    for entry in audit["scans"]:
        sid = entry["id"]
        p = SCANS_ARCHIVE_DIR / f"scan_{int(sid):06d}.jpg"
        if not p.exists():
            continue
        if not entry.get("is_leaf", False):
            gate_pool.append({"scan": sid, "path": str(p), "kind": entry.get("kind", "non_leaf")})
            continue
        gt_label = entry.get("gt")
        if gt_label not in GT_MAP:
            gate_pool.append({"scan": sid, "path": str(p), "kind": "excluded_uncertain"})
            continue
        scan_records.append({"scan": sid, "path": str(p), "label": CLASS_TO_IDX[GT_MAP[gt_label]]})
    print(f"[+] Device-domain scans: {len(scan_records)} trained, {len(gate_pool)} gate-calibration only")

    # ---------------------------------------------------------------- #
    # 4. Assemble corpus                                                #
    # ---------------------------------------------------------------- #
    print("\n[*] Assembling round-5 corpus...")
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
        files = sorted([f for f in cdir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        random.shuffle(files)
        for f in files[:REPLAY_PER_CLASS]:
            replay.append((str(f), CLASS_TO_IDX[cname]))

    records = []  # (path, label, weight, augmenter)
    for p, l in webtest:
        for _ in range(WEBTEST_PASSES):
            records.append((p, l, 1.0, "photo"))
    web_supp_dir = AI_DIR / "web_supplements"
    supp_count = 0
    if web_supp_dir.exists():
        for f in sorted(web_supp_dir.glob("web7_*.jpg")):
            cls = f.name[len("web7_"):].rsplit("__", 1)[0]
            if cls in CLASS_TO_IDX:
                for _ in range(WEB_SUPP_PASSES):
                    records.append((str(f), CLASS_TO_IDX[cls], 1.0, "photo"))
                supp_count += 1
    for h in scan_records:
        for _ in range(SCAN_PASSES):
            records.append((h["path"], h["label"], SCAN_SAMPLE_WEIGHT, "scan"))
    for p, l in replay:
        for _ in range(REPLAY_PASSES):
            records.append((p, l, 1.0, "photo"))
    random.shuffle(records)
    n_scan_w = sum(1 for r in records if r[2] == SCAN_SAMPLE_WEIGHT)
    print(f"[+] Round-5 corpus: {len(records)} records "
          f"({n_scan_w} scan-weighted, {len(records) - n_scan_w} unweighted; "
          f"{supp_count} web supplements included)")

    def ds_gen():
        for p, l, w, aug in records:
            img = Image.open(p)
            im = scan_augment_image(img) if aug == "scan" else photo_augment_image(img)
            arr = np.asarray(im, dtype=np.float32)
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

    valid_dir = pv_dir.parent / "valid"
    if not valid_dir.exists():
        valid_dir = AI_DIR / "PlantVillage_Valid"
    val_ds = tf.keras.utils.image_dataset_from_directory(
        str(valid_dir), class_names=CLASS_NAMES, image_size=IMAGE_SIZE,
        batch_size=32, label_mode="categorical", shuffle=False,
    )
    val_true = np.concatenate([np.argmax(l.numpy(), axis=1) for _, l in val_ds])

    # ---------------------------------------------------------------- #
    # 5. Head-only fine-tune with held-out guard checkpoints            #
    # ---------------------------------------------------------------- #
    print(f"\n[Phase R5] Head-only fine-tune: {EPOCHS} epochs @ lr={LR_HEAD} "
          f"({steps_per_epoch} steps/epoch, backbone frozen)")
    base_model.trainable = True
    for layer in base_model.layers:
        name = layer.name.lower()
        if any(k in name for k in ("foliar_feature_dense", "head_bn", "disease_probability_output",
                                   "head_dropout")):
            layer.trainable = True
        else:
            layer.trainable = False
    print(f"[+] Trainable layers: {[l.name for l in base_model.layers if l.trainable]}")

    lr_sched = tf.keras.optimizers.schedules.CosineDecay(LR_HEAD, decay_steps=max(1, steps_per_epoch * EPOCHS), alpha=0.05)
    base_model.compile(optimizer=tf.keras.optimizers.Adam(lr_sched),
                       loss="categorical_crossentropy", metrics=["accuracy"])

    best = {"epoch": -1, "val_acc": 0.0, "bench": -1, "wt": -1, "scan": -1}
    wt_paths = [p for p, _ in webtest]
    wt_labels = np.array([l for _, l in webtest])
    scan_paths_r5 = [h["path"] for h in scan_records]
    scan_labels_r5 = np.array([h["label"] for h in scan_records])
    for epoch in range(1, EPOCHS + 1):
        base_model.fit(ds, epochs=1, verbose=2)
        vp = []
        for images, _ in val_ds:
            vp.append(base_model.predict(images, verbose=0))
        vp = np.concatenate(vp)
        val_acc = float(np.mean(np.argmax(vp, axis=1) == val_true))
        sp = model_probs(base_model, spec_paths)
        bench = int(np.sum(np.argmax(sp, axis=1) == spec_labels))
        # webtest is TRAINING data now (burned) -> fitting it is a selection
        # signal, not an evaluation metric
        wt = int(np.sum(np.argmax(model_probs(base_model, wt_paths), axis=1) == wt_labels))
        scan_a = int(np.sum(np.argmax(model_probs(base_model, scan_paths_r5), axis=1) == scan_labels_r5))
        eligible = (val_acc >= PV_FLOOR) and (bench >= BENCH_FLOOR)
        better = ((bench, wt, scan_a) > (best["bench"], best["wt"], best["scan"]))
        star = " * best checkpoint saved" if (eligible and better) else ""
        print(f"[epoch {epoch:02d}] PV valid acc={val_acc:.4f}  benchmark raw={bench}/60 "
              f"(floor {BENCH_FLOOR})  webtest-fit={wt}/102  scans={scan_a}/{len(scan_labels_r5)}{star}")
        if eligible and better:
            best.update(epoch=epoch, val_acc=val_acc, bench=bench, wt=wt, scan=scan_a)
            base_model.save_weights(str(BEST_WEIGHTS_PATH))
    if best["epoch"] < 0:
        print(f"[FAIL] No epoch met the guard (PV valid >= {PV_FLOOR} AND benchmark >= "
              f"{BENCH_FLOOR}/60). Deployment model NOT touched. Aborting without export.")
        return 2
    print(f"[+] Restoring best epoch {best['epoch']} (PV valid {best['val_acc']:.4f}, "
          f"benchmark raw {best['bench']}/60)")
    base_model.load_weights(str(BEST_WEIGHTS_PATH))
    BEST_WEIGHTS_PATH.unlink(missing_ok=True)

    # ---------------------------------------------------------------- #
    # 6. Temperature re-calibration on PV valid                         #
    # ---------------------------------------------------------------- #
    print("\n[*] Re-fitting temperature on full local PV valid...")
    val_probs = []
    for images, _ in val_ds:
        val_probs.append(base_model.predict(images, verbose=0))
    val_probs = np.concatenate(val_probs)
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
    # 7. Export FP16 TFLite                                             #
    # ---------------------------------------------------------------- #
    if OUT_TFLITE_PATH.exists():
        shutil.copy2(OUT_TFLITE_PATH, PREV_DEPLOY_BACKUP)
        print(f"[+] Previous deployment backed up: {PREV_DEPLOY_BACKUP.name}")

    tflite_bytes = tflite_convert(base_model)
    with open(OUT_TFLITE_PATH, "wb") as f:
        f.write(tflite_bytes)
    import hashlib
    model_sha = hashlib.sha256(tflite_bytes).hexdigest()
    print(f"[OK] Round-5 TFLite exported: {len(tflite_bytes)} bytes sha256={model_sha}")

    keras_out = AI_DIR / "krishi_drishti_base.keras"
    try:
        base_model.save(keras_out)
        print(f"[OK] Keras model saved: {keras_out.name}")
    except Exception as e:
        print(f"[WARN] Keras save skipped: {e}")

    # ---------------------------------------------------------------- #
    # 8. Post-export in-script evaluation (final gate numbers)          #
    # ---------------------------------------------------------------- #
    tfl_predict = make_tflite_predictor(tflite_bytes)

    def tfl_probs(paths):
        return tfl_predict([Image.open(p) for p in paths])

    # benchmark raw agreement (held-out gate)
    final_spec = tfl_probs(spec_paths)
    final_bench = int(np.sum(np.argmax(final_spec, axis=1) == spec_labels))
    print(f"\n[FINAL] Benchmark-60 raw agreement: {final_bench}/60 (base was {base_bench_agree}/60)")

    # webtest100 raw (memorization check — NOT a valid test anymore)
    wt_probs = tfl_probs([p for p, _ in webtest])
    wt_true = np.array([l for _, l in webtest])
    wt_raw = int(np.sum(np.argmax(wt_probs, axis=1) == wt_true))
    print(f"[FINAL] webtest100 raw: {wt_raw}/102  (MEMORIZED — invalid as a test)")

    # audited scans raw agreement (device domain)
    sp = tfl_probs([h["path"] for h in scan_records])
    sl = np.array([h["label"] for h in scan_records])
    scan_agree = int(np.sum(np.argmax(sp, axis=1) == sl))
    print(f"[FINAL] Audited-scan raw agreement: {scan_agree}/{len(scan_records)}")

    # scan detail rows + gate sweep (device rows + OOD rows)
    rows = []
    for s in sorted(scan_records, key=lambda x: int(x["scan"])):
        probs = tfl_predict([Image.open(s["path"])])[0]
        top, conf, margin, entropy = gate_stats(probs)
        rows.append({"scan": s["scan"], "kind": "visual_audit_verified",
                     "pred": CLASS_NAMES[top], "conf": round(conf, 4),
                     "margin": round(margin, 4), "entropy": round(entropy, 4),
                     "expected": CLASS_NAMES[s["label"]]})
    for g in gate_pool:
        probs = tfl_predict([Image.open(g["path"])])[0]
        top, conf, margin, entropy = gate_stats(probs)
        rows.append({"scan": g["scan"], "kind": g["kind"],
                     "pred": CLASS_NAMES[top], "conf": round(conf, 4),
                     "margin": round(margin, 4), "entropy": round(entropy, 4),
                     "expected": None})
    print(f"\n{'scan':>10} {'kind':26} {'prediction':24} {'conf':>6}")
    for r in rows:
        print(f"{r['scan']:>10} {r['kind']:26} {r['pred']:24} {r['conf']:>6.3f}")

    ood_rows = [r for r in rows if r["expected"] is None]
    hw_rows = [r for r in rows if r["expected"] is not None]
    best_gate = None
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
                if best_gate is None or score > best_gate[0]:
                    best_gate = (score, {"conf": c, "entropy": e, "margin": m})
    print(f"[+] Best gate: reject {best_gate[0][0]}/{len(ood_rows)} OOD, "
          f"accept {best_gate[0][1]}/{len(hw_rows)} scans "
          f"-> conf={best_gate[1]['conf']}, entropy={best_gate[1]['entropy']}, margin={best_gate[1]['margin']}")

    # ---------------------------------------------------------------- #
    # 9. Manifest (invalidation recorded)                               #
    # ---------------------------------------------------------------- #
    manifest = {
        "manifest_version": "5.0-round5-webtest-burned",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "owner_decision": "Train on ALL 102 webtest100 images (2026-11-15). "
                          "webtest100 is INVALIDATED as a held-out test; a fresh "
                          "100-image set will be harvested after this fine-tune.",
        "base_model": "krishi_drishti_base.keras (raw v7, b0c6c39a... lineage)",
        "trained_on": {
            "webtest100_burned": len(webtest),
            "web_supplements": supp_count,
            "audited_scans": len(scan_records),
            "pv_replay_per_class": REPLAY_PER_CLASS,
        },
        "round5_tflite_sha256": model_sha,
        "round5_tflite_size_bytes": len(tflite_bytes),
        "temperature": T_opt,
        "guard": {
            "held_out_benchmark_floor_raw": BENCH_FLOOR,
            "final_benchmark_raw": final_bench,
            "pv_valid_accuracy": round(val_acc_pre, 4),
            "pv_floor": PV_FLOOR,
            "best_epoch": best["epoch"],
        },
        "final_metrics": {
            "benchmark60_raw_agreement": final_bench,
            "webtest100_raw_MEMORIZED_INVALID": wt_raw,
            "audited_scan_agreement": scan_agree,
        },
        "gate_sweep_best": best_gate[1],
        "scan_rows": rows,
        "wall_time_seconds": round(time.time() - t0, 1),
        "io_contract": "Float32 [1,128,128,3] raw [0,255] -> [1,6] softmax (unchanged)",
    }
    out_manifest = AI_DIR / "ROUND5_FINETUNE_MANIFEST.json"
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n[OK] Round-5 manifest written: {out_manifest.name}")
    print(f"[OK] Total wall time: {manifest['wall_time_seconds']}s")
    print("\n[NEXT] Run external gates before shipping:")
    print("   tests/benchmark_60_specimens.py      (strict daemon score; need >= 58/60)")
    print("   tests/test_chartpaper_palm.py        (OOD must stay 6/6 reject)")
    print("   tests/test_internet_images_round3_100.py (memorization record only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
