"""
================================================================================
 KRISHI-DRISHTI :: ROUND-6 WEB-SCALE FINE-TUNE (harvest-10k, cached features)
================================================================================
 Trains the v7-lineage head on ~10k weak-labeled (query-derived) fresh web
 images + 102 burned webtest100 + 41 supplements + 25 audited scans + PV replay.

 Efficiency: backbone is frozen, so image->feature is a FIXED function.
 All features are precomputed ONCE (with a few light-augmented copies), then
 head training epochs cost only seconds -> many epochs + aggressive guard.

 Held-out guard, per epoch (checkpoint eligible only if ALL pass):
   - benchmark-60 raw agreement >= base model's own (58/60)
   - PV valid accuracy >= 0.978
 Selection preference: (bench, pv, webtest-fit, scan-agreement) — webtest and
 scans are training data (burned by owner decision) so fitting them is a legal
 selection signal; fresh100 is NEVER in selection or training.

 Final gates (external):
   - fresh100 raw argmax must beat the deployed round-5 baseline (+2 margin)
   - benchmark-60 strict >= 57/60 (hold)
   - OOD chart/palm 6/6
 Run:  python ai_engine/finetune_v7_web10k.py
================================================================================
"""

import json
import math
import os
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
import tensorflow as tf

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_DIR = REPO_ROOT / "ai_engine"
TESTS_DIR = REPO_ROOT / "tests"
BASE_DIR = Path(r"C:\Users\DELL\Documents\Default Project\webtest100")

BASE_MODEL_PATH = AI_DIR / "krishi_drishti_base.keras"
OUT_TFLITE_PATH = AI_DIR / "krishi_drishti_model.tflite"
PREV_DEPLOY_BACKUP = AI_DIR / "krishi_drishti_model_round5_prev.tflite"
SPECIMEN_DIR = AI_DIR / "validation_60_specimens"
FRESH100_MANIFEST = BASE_DIR / "fresh100_manifest.json"
TRAIN_POOL_MANIFEST = BASE_DIR / "train_pool_manifest.json"
WEBTEST_RESULTS = BASE_DIR / "webtest100_results.json"
WEBTEST_IMAGES = BASE_DIR / "images"
AUDIT_PATH = TESTS_DIR / "sd_scan_visual_audit.json"
SCANS_ARCHIVE_DIR = TESTS_DIR / "sd_card_scans_archive_r3"
CACHE_DIR = AI_DIR / "_web10k_feature_cache"

IMAGE_SIZE = (128, 128)
NUM_CLASSES = 6
CLASS_NAMES = [
    "Tomato___Late_blight", "Tomato___Early_blight", "Tomato___healthy",
    "Potato___Late_blight", "Potato___Early_blight", "Potato___healthy",
]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASS_NAMES)}
CANONICAL_TO_IDX = {
    "Tomato Late Blight": 0, "Tomato Early Blight": 1, "Tomato Healthy": 2,
    "Potato Late Blight": 3, "Potato Early Blight": 4, "Potato Healthy": 5,
}

RANDOM_SEED = 42
AUG_COPIES_WEB = 2          # cached copies per web image (raw + N augmented)
WEB_WEIGHT = 0.75           # weak labels get slightly lower weight
PV_REPLAY_PER_CLASS = 200
PV_REPLAY_PASSES = 3
PV_REPLAY_WEIGHT = 2.0      # anchor against weak-label noise
WEBTEST_PASSES = 3
SCAN_PASSES = 6
SCAN_SAMPLE_WEIGHT = 1.5
WEB_SUPP_PASSES = 3
EPOCHS = 60
LR_HEAD = 3e-4              # feature-space training tolerates higher LR
LABEL_SMOOTHING = 0.08
PV_FLOOR = 0.978
BEST_WEIGHTS_PATH = AI_DIR / "_finetune_web10k_best.weights.h5"

HEAD_LAYERS = ["head_dropout_1", "foliar_feature_dense", "head_bn",
               "head_dropout_2", "disease_probability_output"]


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


def gate_stats(probs):
    top = int(np.argmax(probs))
    conf = float(probs[top])
    sp = np.sort(probs)[::-1]
    margin = float(sp[0] - sp[1]) if len(sp) > 1 else 1.0
    entropy = -float(sum(p * math.log(p) for p in probs if p > 1e-6))
    return top, conf, margin, entropy


def photo_augment_image(img, strong=False):
    im = img.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR)
    arr = np.asarray(im, dtype=np.float32)
    if random.random() < (0.55 if strong else 0.4):
        gamma = random.uniform(0.7, 1.45)
        arr = np.power(np.clip(arr / 255.0, 0, 1), gamma) * 255.0
    if random.random() < (0.45 if strong else 0.3):
        s = random.uniform(0.05, 0.22)
        arr = arr * np.array([1.0 + s, 1.0, 1.0 - s * 0.3], dtype=np.float32)
    arr = np.clip(arr, 0, 255)
    im = Image.fromarray(arr.astype(np.uint8))
    if random.random() < 0.85:
        im = im.transform(
            IMAGE_SIZE, Image.AFFINE,
            (1.0, random.uniform(-0.07, 0.07), random.uniform(-7, 7),
             random.uniform(-0.07, 0.07), 1.0, random.uniform(-7, 7)),
            resample=Image.BILINEAR,
        )
    if random.random() < 0.5:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


def scan_augment_image(img):
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


def load_benchmark_specimens():
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
        for f in sorted(fdir.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                specimens.append((str(f), CANONICAL_TO_IDX[folder_map[folder]]))
    return specimens


def main():
    t0 = time.time()
    print("=" * 84)
    print("  KRISHI-DRISHTI :: ROUND-6 WEB-SCALE FINE-TUNE (harvest-10k, cached features)")
    print("=" * 84)
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    tf.random.set_seed(RANDOM_SEED)

    if not BASE_MODEL_PATH.exists():
        print(f"[FAIL] base model missing: {BASE_MODEL_PATH}")
        return 1
    if not TRAIN_POOL_MANIFEST.exists() or not FRESH100_MANIFEST.exists():
        print("[FAIL] run split_fresh100.py first")
        return 1

    base_model = tf.keras.models.load_model(BASE_MODEL_PATH, compile=False)

    # ---------------- feature extractor = frozen prefix ---------------- #
    first_trainable = base_model.get_layer(HEAD_LAYERS[0])
    feat_tensor = first_trainable.input
    feat_model = tf.keras.Model(base_model.input, feat_tensor)
    feat_dim = int(feat_model.output_shape[-1])
    print(f"[+] feature extractor frozen prefix -> dim {feat_dim}")

    # warm up + measure throughput on 8 images
    def encode(paths_imgs):
        """paths_imgs: list of (path, augment_fn or None). Returns features."""
        arrs = []
        for p, aug in paths_imgs:
            img = Image.open(p)
            im = aug(img) if aug else img.convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR)
            arrs.append(np.asarray(im, dtype=np.float32))
        return feat_model.predict(np.array(arrs), verbose=0)

    spec_paths, spec_labels = map(list, zip(*load_benchmark_specimens()))
    spec_labels = np.array(spec_labels)
    bench_feats = encode([(p, None) for p in spec_paths])

    def head_chain(feats, model):
        x = feats
        for name in HEAD_LAYERS:
            x = model.get_layer(name)(x)
        return x.numpy()

    base_bench = int(np.sum(np.argmax(head_chain(bench_feats, base_model), axis=1) == spec_labels))
    print(f"[+] BASELINE benchmark-60 raw (cached features): {base_bench}/60")
    BENCH_FLOOR = base_bench

    # ---------------- build record lists ---------------- #
    train_pool = json.loads(TRAIN_POOL_MANIFEST.read_text(encoding="utf-8"))
    fresh100 = json.loads(FRESH100_MANIFEST.read_text(encoding="utf-8"))
    pool_dir = BASE_DIR / "harvest10k" / "kept"
    web_records = [(str(pool_dir / r["file"]), CLASS_TO_IDX[r["label"]]) for r in train_pool]
    fresh_recs = [(str(pool_dir / r["file"]), CLASS_TO_IDX[r["label"]], r["file"]) for r in fresh100]
    print(f"[+] harvest train pool: {len(web_records)} | fresh100 held out: {len(fresh_recs)}")

    results = json.loads(WEBTEST_RESULTS.read_text(encoding="utf-8"))
    webtest = [(str(WEBTEST_IMAGES / r["file"]), CLASS_TO_IDX[r["expected"]]) for r in results["rows"]]
    supp = []
    for f in sorted((AI_DIR / "web_supplements").glob("web7_*.jpg")):
        cls = f.name[len("web7_"):].rsplit("__", 1)[0]
        if cls in CLASS_TO_IDX:
            supp.append((str(f), CLASS_TO_IDX[cls]))
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    GT_MAP = {"Tomato Late Blight": "Tomato___Late_blight",
              "Tomato Early Blight": "Tomato___Early_blight",
              "Tomato Healthy": "Tomato___healthy",
              "diseased leaf (late blight series)": "Tomato___Late_blight",
              "healthy leaf": "Tomato___healthy",
              "healthy leaf (host uncertain)": "Tomato___healthy"}
    scans, gate_pool = [], []
    for entry in audit["scans"]:
        p = SCANS_ARCHIVE_DIR / f"scan_{int(entry['id']):06d}.jpg"
        if not p.exists():
            continue
        if not entry.get("is_leaf", False) or entry.get("gt") not in GT_MAP:
            gate_pool.append({"scan": entry["id"], "path": str(p), "kind": "ood_or_uncertain"})
            continue
        scans.append({"scan": entry["id"], "path": str(p), "label": CLASS_TO_IDX[GT_MAP[entry["gt"]]]})

    pv_dir = Path(os.environ.get("KAGGLEHUB_CACHE", str(Path.home() / ".cache" / "kagglehub"))) \
        / "datasets" / "vipoooool" / "new-plant-diseases-dataset" / "versions" / "2" \
        / "New Plant Diseases Dataset(Augmented)" / "New Plant Diseases Dataset(Augmented)" / "train"
    if not pv_dir.exists():
        pv_dir = AI_DIR / "PlantVillage_Train"
    replay = []
    for cname in CLASS_NAMES:
        files = sorted([f for f in (pv_dir / cname).iterdir()
                        if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        random.shuffle(files)
        replay.extend((str(f), CLASS_TO_IDX[cname]) for f in files[:PV_REPLAY_PER_CLASS])

    # ---------------- cache features (one-time) ---------------- #
    CACHE_DIR.mkdir(exist_ok=True)
    CACHE_TAG = "r6"

    def cache_group(tag, paths_imgs):
        """paths_imgs: list of (path, aug_fn|None). Returns np array."""
        fpath = CACHE_DIR / f"{tag}_{CACHE_TAG}.npy"
        if fpath.exists():
            return np.load(fpath)
        feats = []
        B = 256
        for i in range(0, len(paths_imgs), B):
            feats.append(encode(paths_imgs[i:i + B]))
        out = np.concatenate(feats, axis=0)
        np.save(fpath, out)
        print(f"[cache] {tag}: {out.shape} saved")
        return out

    print("\n[*] Caching features (one-time; backbone frozen)...")
    web_feats = cache_group("web", [(p, None) for p, _ in web_records]
                            + [(p, lambda im: photo_augment_image(im)) for p, _ in web_records]
                            + [(p, lambda im: photo_augment_image(im, strong=True)) for p, _ in web_records])
    web_labels = np.array([l for _, l in web_records] * 3)
    web_weights = np.full(len(web_records) * 3, WEB_WEIGHT, dtype=np.float32)

    wt_feats = cache_group("wt", [(p, None) for p, _ in webtest]
                           + [(p, lambda im: photo_augment_image(im)) for p, _ in webtest]
                           + [(p, lambda im: photo_augment_image(im)) for p, _ in webtest])
    wt_labels = np.array([l for _, l in webtest] * 3)

    supp_feats = cache_group("supp", [(p, None) for p, _ in supp]
                             + [(p, lambda im: photo_augment_image(im)) for p, _ in supp]
                             + [(p, lambda im: photo_augment_image(im)) for p, _ in supp])
    supp_labels = np.array([l for _, l in supp] * 3)

    scan_feats = cache_group("scan", [(h["path"], None) for h in scans]
                             + [(h["path"], lambda im: scan_augment_image(im)) for h in scans]
                             + [(h["path"], lambda im: scan_augment_image(im)) for h in scans]
                             + [(h["path"], lambda im: scan_augment_image(im)) for h in scans]
                             + [(h["path"], lambda im: scan_augment_image(im)) for h in scans])
    scan_labels = np.array([h["label"] for h in scans] * 5)
    scan_weights = np.full(len(scans) * 5, SCAN_SAMPLE_WEIGHT, dtype=np.float32)

    pv_feats = cache_group("pv", [(p, None) for p, _ in replay]
                           + [(p, lambda im: photo_augment_image(im)) for p, _ in replay]
                           + [(p, lambda im: photo_augment_image(im)) for p, _ in replay])
    pv_labels = np.array([l for _, l in replay] * 3)
    pv_weights = np.full(len(replay) * 3, PV_REPLAY_WEIGHT, dtype=np.float32)

    val_dir = pv_dir.parent / "valid"
    if not val_dir.exists():
        val_dir = AI_DIR / "PlantVillage_Valid"
    val_files = []
    for cname in CLASS_NAMES:
        for f in sorted((val_dir / cname).iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                val_files.append((str(f), CLASS_TO_IDX[cname]))
    val_feats = cache_group("val", [(p, None) for p, _ in val_files])
    val_labels = np.array([l for _, l in val_files])

    fresh_feats = cache_group("fresh", [(p, None) for p, _, _ in fresh_recs])
    fresh_labels = np.array([l for _, l, _ in fresh_recs])

    # ---------------- assemble training set ---------------- #
    all_feats = np.concatenate([web_feats, wt_feats, supp_feats, scan_feats, pv_feats], axis=0)
    all_labels = np.concatenate([web_labels, wt_labels, supp_labels, scan_labels, pv_labels])
    all_weights = np.concatenate([web_weights,
                                  np.ones(len(wt_feats), dtype=np.float32),
                                  np.ones(len(supp_feats), dtype=np.float32),
                                  scan_weights, pv_weights])
    idx = np.arange(len(all_feats))
    np.random.shuffle(idx)
    all_feats, all_labels, all_weights = all_feats[idx], all_labels[idx], all_weights[idx]
    print(f"[+] training matrix: {all_feats.shape}, weights: web={WEB_WEIGHT} pv={PV_REPLAY_WEIGHT} "
          f"scan={SCAN_SAMPLE_WEIGHT}")

    y_smooth = np.full((len(all_labels), NUM_CLASSES), LABEL_SMOOTHING / NUM_CLASSES, dtype=np.float32)
    y_smooth[np.arange(len(all_labels)), all_labels] += 1.0 - LABEL_SMOOTHING

    # fresh100 baseline for BOTH models (selection never sees these)
    def eval_fresh(model):
        return int(np.sum(np.argmax(head_chain(fresh_feats, model), axis=1) == fresh_labels))
    print(f"[+] fresh100 baseline of current deployed base: {eval_fresh(base_model)}/{len(fresh_labels)}")

    # ---------------- head training on cached features ---------------- #
    sub_in = tf.keras.Input(shape=(feat_dim,), dtype=tf.float32)
    x = sub_in
    for name in HEAD_LAYERS:
        x = base_model.get_layer(name)(x)
    sub = tf.keras.Model(sub_in, x)
    BATCH = 128
    steps = math.ceil(len(all_feats) / BATCH)
    lr_sched = tf.keras.optimizers.schedules.CosineDecay(LR_HEAD, decay_steps=max(1, steps * EPOCHS), alpha=0.05)
    sub.compile(optimizer=tf.keras.optimizers.Adam(lr_sched),
                loss="categorical_crossentropy", metrics=["accuracy"])

    ds = tf.data.Dataset.from_tensor_slices((all_feats, y_smooth, all_weights)) \
        .shuffle(8192, seed=RANDOM_SEED).batch(BATCH).prefetch(tf.data.AUTOTUNE)
    val_ds = tf.data.Dataset.from_tensor_slices((val_feats,)).batch(256)

    print(f"\n[Phase R6] feature-space head training: {EPOCHS} epochs @ lr={LR_HEAD}, "
          f"{math.ceil(len(all_feats)/BATCH)} steps/epoch")
    best = {"epoch": -1, "pv": 0.0, "bench": -1, "wt": -1, "scan": -1}
    bench_floor = BENCH_FLOOR
    for epoch in range(1, EPOCHS + 1):
        sub.fit(ds, epochs=1, verbose=2)
        vp = head_chain(val_feats, sub)
        pv_acc = float(np.mean(np.argmax(vp, axis=1) == val_labels))
        bench = int(np.sum(np.argmax(head_chain(bench_feats, sub), axis=1) == spec_labels))
        wt_fit = int(np.sum(np.argmax(head_chain(wt_feats, sub), axis=1) == wt_labels))
        scan_a = int(np.sum(np.argmax(head_chain(scan_feats, sub), axis=1) == scan_labels))
        eligible = (pv_acc >= PV_FLOOR) and (bench >= bench_floor)
        better = (bench, pv_acc, wt_fit, scan_a) > (best["bench"], best["pv"], best["wt"], best["scan"])
        star = " * best" if (eligible and better) else ""
        print(f"[epoch {epoch:02d}] PV={pv_acc:.4f} bench={bench}/60 wt-fit={wt_fit}/306 "
              f"scans={scan_a}/{len(scan_labels)} fresh100={eval_fresh(sub)}/100 (info only){star}")
        if eligible and better:
            best.update(epoch=epoch, pv=pv_acc, bench=bench, wt=wt_fit, scan=scan_a)
            sub.save_weights(str(BEST_WEIGHTS_PATH))
    if best["epoch"] < 0:
        print(f"[FAIL] No epoch met guard (PV>={PV_FLOOR}, bench>={bench_floor}). "
              "Deployment NOT touched.")
        return 2
    print(f"[+] Restoring best epoch {best['epoch']} "
          f"(PV {best['pv']:.4f}, bench {best['bench']}/60)")
    sub.load_weights(str(BEST_WEIGHTS_PATH))
    BEST_WEIGHTS_PATH.unlink(missing_ok=True)

    # ---------------- temperature on PV valid (feature space) ---------------- #
    vp = head_chain(val_feats, sub)
    pv_acc_pre = float(np.mean(np.argmax(vp, axis=1) == val_labels))
    T_opt, nll_opt = fit_temperature(vp, val_labels)
    print(f"[+] PV valid acc {pv_acc_pre:.4f}; optimal T={T_opt} (NLL {nll_opt:.4f})")
    if abs(T_opt - 1.0) > 0.05:
        bake_temperature(sub, T_opt)
        post = head_chain(val_feats, sub)
        assert abs(float(np.mean(np.argmax(post, axis=1) == val_labels)) - pv_acc_pre) < 1e-6
        print("[OK] temperature baked (argmax preserved)")

    # ---------------- export ---------------- #
    if OUT_TFLITE_PATH.exists():
        shutil.copy2(OUT_TFLITE_PATH, PREV_DEPLOY_BACKUP)
        print(f"[+] previous deployment backed up: {PREV_DEPLOY_BACKUP.name}")
    tflite_bytes = tflite_convert(base_model)
    with open(OUT_TFLITE_PATH, "wb") as f:
        f.write(tflite_bytes)
    import hashlib
    model_sha = hashlib.sha256(tflite_bytes).hexdigest()
    print(f"[OK] Round-6 TFLite exported: {len(tflite_bytes)} bytes sha256={model_sha}")
    try:
        base_model.save(AI_DIR / "krishi_drishti_base.keras")
        print("[OK] keras base saved")
    except Exception as e:
        print(f"[WARN] keras save skipped: {e}")

    # ---------------- post-export evaluation ---------------- #
    interp = tf.lite.Interpreter(model_content=tflite_bytes)
    interp.allocate_tensors()
    in_d, out_d = interp.get_input_details()[0], interp.get_output_details()[0]

    def tfl_probs(paths):
        out = []
        for p in paths:
            arr = np.asarray(Image.open(p).convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR),
                             dtype=np.float32)
            interp.set_tensor(in_d["index"], np.expand_dims(arr, 0))
            interp.invoke()
            out.append(interp.get_tensor(out_d["index"])[0].astype(np.float32))
        return np.array(out)

    fb = int(np.sum(np.argmax(tfl_probs(spec_paths), axis=1) == spec_labels))
    fr = int(np.sum(np.argmax(tfl_probs([p for p, _, _ in fresh_recs]), axis=1) == fresh_labels))
    sa = int(np.sum(np.argmax(tfl_probs([h["path"] for h in scans]), axis=1)
                    == np.array([h["label"] for h in scans])))
    print(f"\n[FINAL-TFLite] benchmark raw={fb}/60  fresh-pool raw={fr}/{len(fresh_labels)}  scans={sa}/{len(scans)}")

    rows = []
    for s in sorted(scans, key=lambda x: int(x["scan"])):
        probs = tfl_probs([s["path"]])[0]
        top, conf, margin, entropy = gate_stats(probs)
        rows.append({"scan": s["scan"], "kind": "visual_audit_verified",
                     "pred": CLASS_NAMES[top], "conf": round(conf, 4),
                     "margin": round(margin, 4), "entropy": round(entropy, 4),
                     "expected": CLASS_NAMES[s["label"]]})
    for g in gate_pool:
        probs = tfl_probs([g["path"]])[0]
        top, conf, margin, entropy = gate_stats(probs)
        rows.append({"scan": g["scan"], "kind": g["kind"],
                     "pred": CLASS_NAMES[top], "conf": round(conf, 4),
                     "margin": round(margin, 4), "entropy": round(entropy, 4),
                     "expected": None})
    CONF_GRID = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
    ENTROPY_GRID = [1.20, 1.30, 1.45, 1.60, 1.75]
    MARGIN_GRID = [0.08, 0.12, 0.16, 0.20, 0.25]
    ood_rows = [r for r in rows if r["expected"] is None]
    hw_rows = [r for r in rows if r["expected"] is not None]
    best_gate = None
    for c in CONF_GRID:
        for e in ENTROPY_GRID:
            for m in MARGIN_GRID:
                rej = sum(1 for r in ood_rows if r["conf"] < c or r["entropy"] > e or r["margin"] < m)
                acc = sum(1 for r in hw_rows if r["conf"] >= c and r["entropy"] <= e and r["margin"] >= m)
                if best_gate is None or (rej, acc) > best_gate[0]:
                    best_gate = ((rej, acc), {"conf": c, "entropy": e, "margin": m})
    print(f"[+] Best gate: reject {best_gate[0][0]}/{len(ood_rows)} OOD, "
          f"accept {best_gate[0][1]}/{len(hw_rows)} scans")

    manifest = {
        "manifest_version": "6.0-round6-web10k",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_model": "krishi_drishti_base.keras (round-5 lineage 5de439ef)",
        "trained_on": {
            "harvest10k_weak_labeled": len(web_records),
            "webtest100_burned": len(webtest),
            "web_supplements": len(supp),
            "audited_scans": len(scans),
            "pv_replay_per_class": PV_REPLAY_PER_CLASS,
        },
        "held_out_never_trained": ["fresh100 (100 images)", "benchmark-60", "PV valid", "OOD chart/palm"],
        "round6_tflite_sha256": model_sha,
        "temperature": T_opt,
        "guard": {"bench_floor_raw": bench_floor, "pv_floor": PV_FLOOR,
                  "best_epoch": best["epoch"], "best_bench_raw": best["bench"],
                  "best_pv": round(best["pv"], 4)},
        "final_metrics": {
            "benchmark60_raw_tflite": fb,
            "fresh100_raw_tflite": fr,
            "audited_scan_agreement_tflite": sa,
        },
        "gate_sweep_best": best_gate[1],
        "wall_time_seconds": round(time.time() - t0, 1),
        "io_contract": "Float32 [1,128,128,3] raw [0,255] -> [1,6] softmax (unchanged)",
    }
    out_manifest = AI_DIR / "ROUND6_FINETUNE_MANIFEST.json"
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n[OK] Round-6 manifest written: {out_manifest.name}")
    print(f"[OK] Total wall time: {manifest['wall_time_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
