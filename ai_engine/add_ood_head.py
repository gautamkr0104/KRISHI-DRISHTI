"""
Round-6b: add a Mahalanobis OOD head to the deployed model.

- Features: frozen 576-d prefix of krishi_drishti_base.keras (same as trainer).
- Centroids per class from harvest train pool (raw) + PV replay + audited scans.
- Shared pooled covariance with shrinkage; A = Sigma^-1.
- OOD score for x = min_c (x-mu_c)^T A (x-mu_c) = min_c (mu_c^T A mu_c - 2 (A mu_c)^T x)
  (the x^T A x term is class-independent, so argmin is exact).
- Bake as a fixed Dense(6) -> ReduceMin second output. Output 0 = probs (unchanged).
- Calibrate tau: all valid pools must sit below, OOD images above.
"""
import json, math, os, random, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image
import tensorflow as tf

REPO_ROOT = Path(r"C:\Users\DELL\Downloads\KRISHI-DRISHTI")
AI_DIR = REPO_ROOT / "ai_engine"
TESTS_DIR = REPO_ROOT / "tests"
BASE_DIR = Path(r"C:\Users\DELL\Documents\Default Project\webtest100")
BASE_MODEL_PATH = AI_DIR / "krishi_drishti_base.keras"
OUT_PATH = AI_DIR / "krishi_drishti_model.tflite"
BACKUP = AI_DIR / "krishi_drishti_model_round6_prev.tflite"
IMAGE_SIZE = (128, 128)
CLASS_NAMES = ["Tomato___Late_blight", "Tomato___Early_blight", "Tomato___healthy",
               "Potato___Late_blight", "Potato___Early_blight", "Potato___healthy"]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASS_NAMES)}
PV_DIR = Path(os.environ.get("KAGGLEHUB_CACHE", str(Path.home() / ".cache" / "kagglehub"))) \
    / "datasets" / "vipoooool" / "new-plant-diseases-dataset" / "versions" / "2" \
    / "New Plant Diseases Dataset(Augmented)" / "New Plant Diseases Dataset(Augmented)" / "train"
if not PV_DIR.exists():
    PV_DIR = AI_DIR / "PlantVillage_Train"
random.seed(42)

def load_img(path):
    return np.asarray(Image.open(path).convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR), dtype=np.float32)

def main():
    t0 = time.time()
    print("=" * 84)
    print("  ROUND-6b :: MAHALANOBIS OOD HEAD")
    print("=" * 84)
    base = tf.keras.models.load_model(BASE_MODEL_PATH, compile=False)
    feat_tensor = base.get_layer("head_dropout_1").input
    feat_model = tf.keras.Model(base.input, feat_tensor)
    feat_dim = int(feat_model.output_shape[-1])
    print(f"[+] feature dim: {feat_dim}")

    def feats(paths, tag):
        out = []
        B = 256
        for i in range(0, len(paths), B):
            batch = np.stack([load_img(p) for p in paths[i:i + B]])
            out.append(feat_model.predict(batch, verbose=0))
        arr = np.concatenate(out, axis=0)
        print(f"[feat] {tag}: {arr.shape}")
        return arr

    train_pool = json.loads((BASE_DIR / "train_pool_manifest.json").read_text(encoding="utf-8"))
    pool_dir = BASE_DIR / "harvest10k" / "kept"
    web = [(str(pool_dir / r["file"]), CLASS_TO_IDX[r["label"]]) for r in train_pool]

    replay = []
    for cname in CLASS_NAMES:
        files = sorted([f for f in (PV_DIR / cname).iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        random.shuffle(files)
        replay.extend((str(f), CLASS_TO_IDX[cname]) for f in files[:200])

    audit = json.loads((TESTS_DIR / "sd_scan_visual_audit.json").read_text(encoding="utf-8"))
    GT_MAP = {"Tomato Late Blight": 0, "Tomato Early Blight": 1, "Tomato Healthy": 2,
              "Potato Late Blight": 3, "Potato Early Blight": 4, "Potato Healthy": 5,
              "diseased leaf (late blight series)": 0, "healthy leaf": 2, "healthy leaf (host uncertain)": 2}
    scans, gate_pool = [], []
    for entry in audit["scans"]:
        p = TESTS_DIR / "sd_card_scans_archive_r3" / f"scan_{int(entry['id']):06d}.jpg"
        if not p.exists():
            continue
        if not entry.get("is_leaf", False) or entry.get("gt") not in GT_MAP:
            gate_pool.append(str(p))
        else:
            scans.append((str(p), GT_MAP[entry["gt"]]))

    spec_paths, spec_labels = [], []
    for cname in CLASS_NAMES:
        d = AI_DIR / "validation_60_specimens" / cname
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                spec_paths.append(str(f)); spec_labels.append(CLASS_TO_IDX[cname])

    fresh = json.loads((BASE_DIR / "fresh100_manifest.json").read_text(encoding="utf-8"))
    fresh_recs = [(str(pool_dir / r["file"]), CLASS_TO_IDX[r["label"]]) for r in fresh]

    # OOD calibration set
    ood_paths = [r"C:\Users\DELL\AppData\Local\Temp\opencode\whatsapp_leaf.jpeg"]
    for f in sorted((TESTS_DIR / "internet_test_images").glob("*ood*")):
        ood_paths.append(str(f))
    # synth chart papers (same as pipeline, seed 7)
    rng = np.random.default_rng(7)
    tmp = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest"); tmp.mkdir(parents=True, exist_ok=True)
    def synth_paper(size, base_rgb=(58, 138, 68), grain=6.0, vignette=0.10, jitter=2.0):
        w, h = size
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        grad = 1.0 + vignette * ((xx / w - 0.35) * 0.6 + (yy / h - 0.45) * 0.4)
        img = np.zeros((h, w, 3), dtype=np.float32)
        for c in range(3):
            img[:, :, c] = base_rgb[c] * grad
        img += rng.normal(0, grain, (h, w, 3))
        img += np.array([jitter, 0, -jitter])
        return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    paper_full = tmp / "green_chart_paper_full.jpg"
    synth_paper((960, 1280)).save(paper_full, quality=92)
    ood_paths.append(str(paper_full))
    for n in (4, 5, 6, 7):
        ood_paths.append(str(TESTS_DIR / "sd_card_scans_archive_r3" / f"scan_{n:06d}.jpg"))
    # extra people/fabric hard negatives (local only; used for threshold calibration)
    its_me = Path(r"D:\Images\its me")
    people = sorted([f for f in its_me.glob("*.jp*g")])[:6] if its_me.exists() else []
    for f in people:
        ood_paths.append(str(f))

    web_feats = feats([p for p, _ in web], "web")
    web_labels = np.array([l for _, l in web])
    pv_feats = feats([p for p, _ in replay], "pv")
    pv_labels = np.array([l for _, l in replay])
    scan_feats = feats([p for p, _ in scans], "scans")
    scan_labels = np.array([l for _, l in scans])
    spec_feats = feats(spec_paths, "bench60")
    fresh_feats = feats([p for p, _ in fresh_recs], "fresh100")
    ood_feats = feats(ood_paths, "ood")

    all_valid = np.concatenate([web_feats, pv_feats, scan_feats], axis=0)
    all_labels = np.concatenate([web_labels, pv_labels, scan_labels], axis=0)
    print(f"[+] valid calibration pool: {all_valid.shape}")

    mu = np.zeros((6, feat_dim), dtype=np.float64)
    for c in range(6):
        mu[c] = all_valid[all_labels == c].mean(axis=0)

    # pooled within-class covariance + shrinkage
    centered = all_valid - mu[all_labels]
    cov = (centered.T @ centered) / (len(centered) - 6)
    d = feat_dim
    alpha = 0.10
    cov_s = (1 - alpha) * cov + alpha * (np.trace(cov) / d) * np.eye(d)
    A = np.linalg.inv(cov_s)
    # symmetrize for numerics
    A = 0.5 * (A + A.T)

    # ood scores via s_c = mu_c^T A mu_c - 2 (A mu_c)^T x  (argmin == true Mahalanobis argmin)
    kernel = (-2.0 * (A @ mu.T)).T  # (6, d)
    bias = np.einsum("cd,de,ce->c", mu, A, mu)  # (6,)
    # sanity: compare true mahalanobis vs baked form on a few samples
    x0 = all_valid[:8].astype(np.float64)
    true_d = ((x0[:, None, :] - mu[None, :, :]) @ A * (x0[:, None, :] - mu[None, :, :])).sum(-1)
    baked = bias[None, :] + x0 @ kernel.T
    err = np.abs((true_d - baked)).max()
    print(f"[+] dense-vs-mahalanobis max abs offset (class-independent term): {err:.3f}")

    def min_dist(feat_matrix):
        s = feat_matrix.astype(np.float64) @ kernel.T + bias[None, :]
        return s.min(axis=1), s

    for name, fm in [("web", web_feats), ("pv", pv_feats), ("scans", scan_feats),
                     ("bench60", spec_feats), ("fresh100", fresh_feats), ("ood", ood_feats)]:
        m, _ = min_dist(fm)
        print(f"[dist] {name:9s} min={m.min():9.2f} p99={np.percentile(m, 99):9.2f} max={m.max():9.2f}")

    valid_all = np.concatenate([web_feats, pv_feats, scan_feats, spec_feats, fresh_feats], axis=0)
    mv, _ = min_dist(valid_all)
    mo, _ = min_dist(ood_feats)
    print(f"[dist] VALID combined: max={mv.max():.2f}   OOD set: min={mo.min():.2f}")
    for p, mm in zip(ood_paths, mo):
        print(f"   ood {Path(p).name[:50]:52s} {mm:10.2f}")

    ood_min = float(mo.min())
    valid_max = float(mv.max())
    if ood_min <= valid_max:
        print("[FAIL] OOD not separated from valid pools by Mahalanobis distance")
        return 1
    tau = round(math.sqrt(valid_max * ood_min), 3)  # geometric mean
    margin_lo = valid_max / tau
    margin_hi = ood_min / tau
    print(f"[+] tau = {tau}  (valid max {valid_max:.2f} = {1/margin_lo*100:.0f}% of tau; "
          f"closest OOD {ood_min:.2f} = {margin_hi*100:.0f}% of tau)")

    # ---------------- bake second output and export ---------------- #
    feats_in = feat_tensor
    ood_dense = tf.keras.layers.Dense(6, name="ood_mahalanobis_scores")
    ood_dense.build((None, feat_dim))
    ood_dense.set_weights([kernel.astype(np.float32), bias.astype(np.float32)])
    ood_dense.trainable = False
    s = ood_dense(feats_in)
    ood_scalar = tf.reduce_min(s, axis=1, keepdims=True, name="ood_min_dist")

    export_model = tf.keras.Model(base.input, [base.output, ood_scalar])
    converter = tf.lite.TFLiteConverter.from_keras_model(export_model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_bytes = converter.convert()
    import hashlib
    sha = hashlib.sha256(tflite_bytes).hexdigest()
    print(f"[+] new tflite: {len(tflite_bytes)} bytes sha256={sha[:16]}...")

    # ---------------- verify with interpreter ---------------- #
    interp = tf.lite.Interpreter(model_content=tflite_bytes)
    interp.allocate_tensors()
    outs = interp.get_output_details()
    print(f"[+] tflite outputs: {[(o['name'], o['shape'].tolist()) for o in outs]}")
    in_d = interp.get_input_details()[0]
    probs_idx = next((i for i, o in enumerate(outs) if len(o["shape"]) == 2 and o["shape"][-1] == 6), 0)
    dist_idx = 1 - probs_idx if len(outs) == 2 else None

    # probs must match the previously deployed model
    old = tf.lite.Interpreter(model_path=str(OUT_PATH))
    old.allocate_tensors()
    old_in = old.get_input_details()[0]
    old_out = old.get_output_details()[0]
    test_imgs = spec_paths[:20] + [ood_paths[0]]
    max_diff = 0.0
    for p in test_imgs:
        arr = np.expand_dims(load_img(p), 0)
        interp.set_tensor(in_d["index"], arr); interp.invoke()
        new_p = interp.get_tensor(outs[probs_idx]["index"])[0]
        old.set_tensor(old_in["index"], arr); old.invoke()
        old_p = old.get_tensor(old_out["index"])[0]
        max_diff = max(max_diff, float(np.abs(new_p - old_p).max()))
    print(f"[+] probs max abs diff vs deployed model: {max_diff:.6f}")
    if max_diff > 0.01:
        print("[FAIL] probs changed; aborting")
        return 1

    # tflite distance sanity on bedsheet + a valid specimen
    for tag, p in [("bedsheet", ood_paths[0]), ("specimen", spec_paths[0])]:
        interp.set_tensor(in_d["index"], np.expand_dims(load_img(p), 0)); interp.invoke()
        dval = float(interp.get_tensor(outs[dist_idx]["index"])[0])
        print(f"[+] tflite dist {tag}: {dval:.2f}")

    if OUT_PATH.exists():
        shutil.copy2(OUT_PATH, BACKUP)
        print(f"[+] previous deployment backed up: {BACKUP.name}")
    with open(OUT_PATH, "wb") as f:
        f.write(tflite_bytes)
    print(f"[OK] exported to {OUT_PATH}")

    manifest = {
        "manifest_version": "6.1-round6b-ood-head",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ood_gate": {
            "tau": tau,
            "metric": "min_c diagonal-full Mahalanobis (shared shrunk covariance, alpha=0.10)",
            "valid_pool_max": round(valid_max, 2),
            "closest_ood_min": round(ood_min, 2),
            "ood_set": [Path(p).name for p in ood_paths],
        },
        "round6b_tflite_sha256": sha,
        "io_contract": "Float32 [1,128,128,3] raw [0,255] -> outputs: [1,6] softmax (unchanged), [1,1] ood_min_dist",
    }
    (AI_DIR / "ROUND6B_OOD_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("[OK] manifest written: ROUND6B_OOD_MANIFEST.json")
    print(f"[DONE] wall {time.time() - t0:.1f}s")
    return 0

if __name__ == "__main__":
    sys.exit(main())
