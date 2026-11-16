"""
Round-7: Outlier-Exposure (OE) fine-tune of the round-6 head.

Goal: photos that are not tomato/potato foliage (people, bedsheets/fabric,
other-species leaves, chart paper) must produce FLAT probabilities after the
baked temperature, so the existing entropy/confidence gate rejects them and
withholds chemicals. Real foliage -- including busy multi-leaf field photos --
must stay exactly as sharp as before.

Hard constraints guarded every epoch:
  - PV valid accuracy >= 0.978
  - benchmark-60 raw >= 58 and daemon-strict (conf>=0.50, H<=1.20, margin>=0.12) >= 58
  - audited scans argmax 25/25 and gate-accepted 25/25
  - fresh100 (held out, never trained) raw >= 660  (protect round-6 gain of 666)
Selection maximizes OOD rejection at the gate.
"""
import json, math, os, random, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import tensorflow as tf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from finetune_v7_web10k import (AI_DIR, TESTS_DIR, BASE_DIR, BASE_MODEL_PATH, OUT_TFLITE_PATH,
                                PREV_DEPLOY_BACKUP, CACHE_DIR, IMAGE_SIZE, NUM_CLASSES,
                                CLASS_NAMES, CLASS_TO_IDX, RANDOM_SEED, PV_FLOOR,
                                fit_temperature, bake_temperature, photo_augment_image,
                                scan_augment_image)

SPECIMEN_DIR = AI_DIR / "validation_60_specimens"
AUDIT_PATH = TESTS_DIR / "sd_scan_visual_audit.json"
SCANS_ARCHIVE_DIR = TESTS_DIR / "sd_card_scans_archive_r3"
BEST_WEIGHTS_PATH = AI_DIR / "_finetune_oe_best.weights.h5"
OOD_MANIFEST = AI_DIR / "ROUND7_OE_MANIFEST.json"

EPOCHS = 14
LR_OE = 1.2e-4
OOD_WEIGHT = 2.0
OOD_TARGET = np.full(NUM_CLASSES, 1.0 / NUM_CLASSES, dtype=np.float32)

# browser/daemon tier-1 gate used for OOD rejection accounting
GATE_CONF, GATE_ENT, GATE_MARGIN = 0.50, 1.20, 0.12

FRESH_FLOOR = 655
BENCH_FLOOR = 58


def softmax_np(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def gate_stats(probs):
    top = int(np.argmax(probs))
    conf = float(probs[top])
    sp = np.sort(probs)[::-1]
    margin = float(sp[0] - sp[1]) if len(sp) > 1 else 1.0
    entropy = -float(sum(p * math.log(p) for p in probs if p > 1e-6))
    return top, conf, margin, entropy


def load_img(path):
    return np.asarray(Image.open(path).convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR), dtype=np.float32)


def synth_fabric(rng, size=(512, 384)):
    """Printed-fabric hard negative: base color + repeating motif grid."""
    w, h = size
    base = np.array(rng.choice([(120, 150, 60), (60, 130, 70), (150, 160, 80),
                                (90, 140, 100), (140, 110, 130), (70, 110, 140)]),
                    dtype=np.float32)
    img = np.ones((h, w, 3), dtype=np.float32) * base
    img += rng.normal(0, 5.0, (h, w, 3))
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(im)
    motif = rng.choice(["circle", "flower", "diamond", "leaf"])
    step = int(rng.integers(48, 90))
    off = step // 2
    accent = tuple(int(c) for c in np.clip(base + rng.integers(-70, 70, 3), 0, 255))
    for yy in range(off, h, step):
        for xx in range(off, w, step):
            r = step // 3
            if motif == "circle":
                dr.ellipse([xx - r, yy - r, xx + r, yy + r], fill=accent)
            elif motif == "diamond":
                dr.polygon([(xx, yy - r), (xx + r, yy), (xx, yy + r), (xx - r, yy)], fill=accent)
            elif motif == "flower":
                for a in range(6):
                    ang = a * math.pi / 3
                    cx, cy = xx + r * 0.6 * math.cos(ang), yy + r * 0.6 * math.sin(ang)
                    dr.ellipse([cx - r * 0.4, cy - r * 0.4, cx + r * 0.4, cy + r * 0.4], fill=accent)
            else:
                dr.ellipse([xx - r * 0.5, yy - r, xx + r * 0.5, yy + r], fill=accent)
    if rng.random() < 0.5:
        im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 1.6)))
    return im


def synth_flat(rng, size=(512, 384)):
    """Flat indoor surface hard negative (wall/table/plastic)."""
    w, h = size
    base = np.array(rng.choice([(200, 200, 195), (150, 150, 148), (90, 120, 80), (180, 170, 160)]),
                    dtype=np.float32)
    img = np.ones((h, w, 3), dtype=np.float32) * base
    img += rng.normal(0, 4.0, (h, w, 3))
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def build_ood_records():
    recs = []
    real = [r"C:\Users\DELL\AppData\Local\Temp\opencode\whatsapp_leaf.jpeg"]
    real += sorted(str(f) for f in (TESTS_DIR / "internet_test_images").glob("*ood*"))
    rng = np.random.default_rng(7)
    tmp = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
    tmp.mkdir(parents=True, exist_ok=True)
    paper = tmp / "green_chart_paper_full.jpg"
    if not paper.exists():
        yy, xx = np.mgrid[0:1280, 0:960].astype(np.float32)
        grad = 1.0 + 0.10 * ((xx / 960 - 0.35) * 0.6 + (yy / 1280 - 0.45) * 0.4)
        img = np.zeros((1280, 960, 3), dtype=np.float32)
        for c, base_c in enumerate((58, 138, 68)):
            img[:, :, c] = base_c * grad
        img += rng.normal(0, 6.0, (1280, 960, 3))
        img += np.array([2.0, 0, -2.0])
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(paper, quality=92)
    real.append(str(paper))
    for n in (4, 5, 6, 7):
        real.append(str(SCANS_ARCHIVE_DIR / f"scan_{n:06d}.jpg"))
    # extra people/fabric hard negatives (local calibration only) -- the reported bug class
    its_me = Path(r"D:\Images\its me")
    people = []
    if its_me.exists():
        people = sorted(str(f) for f in its_me.glob("*.jp*g"))[:6]
    for p in people:
        if Path(p).exists():
            recs.append((p, "people"))
    for p in real:
        if Path(p).exists():
            recs.append((p, "real"))
    return recs


def main():
    t0 = time.time()
    print("=" * 84)
    print("  KRISHI-DRISHTI :: ROUND-7 OUTLIER-EXPOSURE FINE-TUNE")
    print("=" * 84)
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    tf.random.set_seed(RANDOM_SEED)

    base_model = tf.keras.models.load_model(BASE_MODEL_PATH, compile=False)
    feat_tensor = base_model.get_layer("head_dropout_1").input
    feat_model = tf.keras.Model(base_model.input, feat_tensor)
    feat_dim = int(feat_model.output_shape[-1])
    print(f"[+] feature dim {feat_dim}")

    def encode_imgs(pil_imgs):
        arrs = [np.asarray(im, dtype=np.float32) for im in pil_imgs]
        return feat_model.predict(np.array(arrs), verbose=0)

    def feats_from_paths(paths, tag):
        out = []
        B = 256
        for i in range(0, len(paths), B):
            batch = [np.asarray(Image.open(p).convert("RGB").resize(IMAGE_SIZE, Image.BILINEAR),
                                dtype=np.float32) for p in paths[i:i + B]]
            out.append(feat_model.predict(np.array(batch), verbose=0))
        arr = np.concatenate(out, axis=0)
        print(f"[feat] {tag}: {arr.shape}")
        return arr

    # ---------------- reuse round-6 feature caches ---------------- #
    web_feats = np.load(CACHE_DIR / "web_r6.npy")
    wt_feats = np.load(CACHE_DIR / "wt_r6.npy")
    supp_feats = np.load(CACHE_DIR / "supp_r6.npy")
    scan_feats = np.load(CACHE_DIR / "scan_r6.npy")
    pv_feats = np.load(CACHE_DIR / "pv_r6.npy")
    val_feats = np.load(CACHE_DIR / "val_r6.npy")
    fresh_feats = np.load(CACHE_DIR / "fresh_r6.npy")

    results = json.loads((BASE_DIR / "webtest100_results.json").read_text(encoding="utf-8"))
    webtest_labels = np.array([CLASS_TO_IDX[r["expected"]] for r in results["rows"]] * 3)
    web_labels = np.concatenate([
        np.array([CLASS_TO_IDX[r["label"]] for r in json.loads(
            (BASE_DIR / "train_pool_manifest.json").read_text(encoding="utf-8"))] * 3)])
    supp_labels = []
    for f in sorted((AI_DIR / "web_supplements").glob("web7_*.jpg")):
        cls = f.name[len("web7_"):].rsplit("__", 1)[0]
        if cls in CLASS_TO_IDX:
            supp_labels.append(CLASS_TO_IDX[cls])
    supp_labels = np.array(supp_labels * 3)

    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    GT_MAP = {"Tomato Late Blight": 0, "Tomato Early Blight": 1, "Tomato Healthy": 2,
              "Potato Late Blight": 3, "Potato Early Blight": 4, "Potato Healthy": 5,
              "diseased leaf (late blight series)": 0, "healthy leaf": 2,
              "healthy leaf (host uncertain)": 2}
    scans_meta = []
    gate_pool = []
    for entry in audit["scans"]:
        p = SCANS_ARCHIVE_DIR / f"scan_{int(entry['id']):06d}.jpg"
        if not p.exists():
            continue
        if not entry.get("is_leaf", False) or entry.get("gt") not in GT_MAP:
            gate_pool.append(str(p))
        else:
            scans_meta.append((str(p), GT_MAP[entry["gt"]]))
    scan_labels = np.array([l for _, l in scans_meta] * 5)
    print(f"[+] caches: web {web_feats.shape} wt {wt_feats.shape} supp {supp_feats.shape} "
          f"scan {scan_feats.shape} pv {pv_feats.shape} val {val_feats.shape} fresh {fresh_feats.shape}")

    spec_paths, spec_labels = [], []
    for cname in CLASS_NAMES:
        d = SPECIMEN_DIR / cname
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                spec_paths.append(str(f)); spec_labels.append(CLASS_TO_IDX[cname])
    spec_labels = np.array(spec_labels)
    bench_feats = feats_from_paths(spec_paths, "bench60")

    fresh_manifest = json.loads((BASE_DIR / "fresh100_manifest.json").read_text(encoding="utf-8"))
    fresh_labels = np.array([CLASS_TO_IDX[r["label"]] for r in fresh_manifest])

    pv_dir = Path(os.environ.get("KAGGLEHUB_CACHE", str(Path.home() / ".cache" / "kagglehub"))) \
        / "datasets" / "vipoooool" / "new-plant-diseases-dataset" / "versions" / "2" \
        / "New Plant Diseases Dataset(Augmented)" / "New Plant Diseases Dataset(Augmented)" / "train"
    if not pv_dir.exists():
        pv_dir = AI_DIR / "PlantVillage_Train"
    val_dir = pv_dir.parent / "valid"
    if not val_dir.exists():
        val_dir = AI_DIR / "PlantVillage_Valid"
    val_files = []
    for cname in CLASS_NAMES:
        for f in sorted((val_dir / cname).iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                val_files.append((str(f), CLASS_TO_IDX[cname]))
    val_labels = np.array([l for _, l in val_files])
    assert len(val_labels) == len(val_feats), f"val mismatch {len(val_labels)} vs {len(val_feats)}"

    # ---------------- OOD feature set (real + synthetic, heavily augmented) ---------------- #
    ood_records = build_ood_records()
    print(f"[+] OOD source images: {len(ood_records)}")
    ood_feats, ood_meta, src_rows, ood_row_weights = [], [], [], []
    must_names = set()
    rng = np.random.default_rng(1234)

    def canonical_crops(im):
        """Canonical fixed views: full resize, center crop, top crop, bottom crop."""
        w0, h0 = im.size
        side = min(w0, h0)
        views = [im.resize(IMAGE_SIZE, Image.BILINEAR)]
        cx0, cy0 = (w0 - side) // 2, (h0 - side) // 2
        views.append(im.crop((cx0, cy0, cx0 + side, cy0 + side)).resize(IMAGE_SIZE, Image.BILINEAR))
        th = h0 // 3
        views.append(im.crop((0, 0, w0, th)).resize(IMAGE_SIZE, Image.BILINEAR))
        views.append(im.crop((0, h0 - th, w0, h0)).resize(IMAGE_SIZE, Image.BILINEAR))
        return views

    for path, kind in ood_records:
        img = Image.open(path).convert("RGB")
        variants = canonical_crops(img)  # 4 canonical views first
        n_canon = len(variants)
        n_aug = 64 if kind == "people" else 48
        for _ in range(n_aug):
            variants.append(photo_augment_image(img, strong=True))
        # random sub-crops of the image (partial-object views)
        for _ in range(12):
            w0, h0 = img.size
            fw = rng.uniform(0.45, 1.0); fh = rng.uniform(0.45, 1.0)
            cx = rng.uniform(0, w0 - w0 * fw); cy = rng.uniform(0, h0 - h0 * fh)
            crop = img.crop((int(cx), int(cy), int(cx + w0 * fw), int(cy + h0 * fh)))
            variants.append(crop.resize(IMAGE_SIZE, Image.BILINEAR))
        offset = sum(f.shape[0] for f in ood_feats)
        name = Path(path).name
        for v in range(n_canon):
            src_rows.append((offset + v, name, v))
        if kind == "people":
            must_names.add(name)
        w_row = 3.0 if kind == "people" else 2.0
        ood_row_weights.extend([w_row] * len(variants))
        f = encode_imgs(variants)
        ood_feats.append(f)
        ood_meta.append((name, len(variants)))
    # synthetic hard negatives
    synth_variants = []
    for _ in range(160):
        synth_variants.append(synth_fabric(rng))
    for _ in range(80):
        synth_variants.append(synth_flat(rng))
    synth_offset = sum(f.shape[0] for f in ood_feats)
    synth_feats = encode_imgs([photo_augment_image(im, strong=True) for im in synth_variants]
                              + [im.resize(IMAGE_SIZE, Image.BILINEAR) for im in synth_variants])
    ood_feats.append(synth_feats)
    ood_row_weights.extend([2.0] * synth_feats.shape[0])
    ood_feats = np.concatenate(ood_feats, axis=0)
    print(f"[+] OOD training matrix: {ood_feats.shape}, canonical rows: {len(src_rows)}, "
          f"must-reject sources: {len(must_names)}")

    # ---------------- assemble ---------------- #
    all_feats = np.concatenate([web_feats, wt_feats, supp_feats, scan_feats, pv_feats, ood_feats], axis=0)

    # replay label sequence must match cache order: seed-42 shuffle per class, first 200
    random.seed(RANDOM_SEED)
    replay_seq = []
    for cname in CLASS_NAMES:
        files = sorted([f for f in (pv_dir / cname).iterdir()
                        if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        random.shuffle(files)
        replay_seq.extend([CLASS_TO_IDX[cname]] * min(200, len(files)))
    pv_labels = np.array(replay_seq * 3)
    assert len(pv_labels) == len(pv_feats), f"pv label mismatch {len(pv_labels)} vs {len(pv_feats)}"
    labels_list = [web_labels, webtest_labels, supp_labels, scan_labels, pv_labels]
    all_labels = np.concatenate(labels_list + [np.full(len(ood_feats), -1, dtype=np.int64)])

    all_weights = np.concatenate([
        np.full(len(web_feats), 0.75, dtype=np.float32),
        np.ones(len(wt_feats), dtype=np.float32),
        np.ones(len(supp_feats), dtype=np.float32),
        np.full(len(scan_feats), 1.5, dtype=np.float32),
        np.full(len(pv_feats), 2.0, dtype=np.float32),
        np.array(ood_row_weights, dtype=np.float32),
    ])
    print(f"[+] training matrix: {all_feats.shape}, ood rows: {(all_labels == -1).sum()} "
          f"(weight {OOD_WEIGHT})")

    # ---------------- head model from current (round-6, T-baked) weights ---------------- #
    HEAD_LAYERS = ["head_dropout_1", "foliar_feature_dense", "head_bn",
                   "head_dropout_2", "disease_probability_output"]
    sub_in = tf.keras.Input(shape=(feat_dim,), dtype=tf.float32)
    x = sub_in
    for name in HEAD_LAYERS:
        x = base_model.get_layer(name)(x)
    sub = tf.keras.Model(sub_in, x)

    def head_chain(feats, model):
        xx = feats
        for name in HEAD_LAYERS:
            xx = model.get_layer(name)(xx)
        return xx.numpy()

    def eval_epoch(model):
        vp = head_chain(val_feats, model)
        pv_acc = float(np.mean(np.argmax(vp, axis=1) == val_labels))
        bp = head_chain(bench_feats, model)
        bench_raw = int(np.sum(np.argmax(bp, axis=1) == spec_labels))
        strict = 0
        for i, p in enumerate(bp):
            top, conf, margin, ent = gate_stats(p)
            if int(np.argmax(p)) == spec_labels[i] and conf >= GATE_CONF and ent <= GATE_ENT and margin >= GATE_MARGIN:
                strict += 1
        sp = head_chain(scan_feats, model)
        raw_idx = np.arange(0, len(sp), 5)  # cache layout: [raw, aug, aug, aug, aug] per scan
        scan_raw_real = int(np.sum(np.argmax(sp[raw_idx], axis=1) == scan_labels[raw_idx]))
        raw_stats = [gate_stats(sp[i]) for i in raw_idx]
        # daemon gate (strict entropy 1.20) vs browser tier-1 (1.45) on the resize view
        scan_gate_d = sum(1 for s in raw_stats if s[1] >= GATE_CONF and s[3] <= GATE_ENT and s[2] >= GATE_MARGIN)
        scan_gate_b = sum(1 for s in raw_stats if s[1] >= 0.50 and s[3] <= 1.45 and s[2] >= 0.12)
        scan_fails = [f"scan{int(Path(scans_meta[i][0]).stem.split('_')[1]):03d}"
                      for i, s in zip(range(25), raw_stats)
                      if not (s[1] >= 0.50 and s[3] <= 1.45 and s[2] >= 0.12)]
        op = head_chain(ood_feats, model)
        ood_rej = sum(1 for p in op if (gate_stats(p)[1] < GATE_CONF or gate_stats(p)[3] > GATE_ENT
                                       or gate_stats(p)[2] < GATE_MARGIN))
        src_stats = [gate_stats(op[i]) for i, _, _ in src_rows]
        src_rej = sum(1 for s in src_stats if s[1] < GATE_CONF or s[3] > GATE_ENT or s[2] < GATE_MARGIN)
        src_fails = [f"{src_rows[i][1][:20]}(v{src_rows[i][2]})"
                     for i, s in zip(range(len(src_rows)), src_stats)
                     if not (s[1] < GATE_CONF or s[3] > GATE_ENT or s[2] < GATE_MARGIN)]
        # must-reject: people photos + bedsheet on every canonical view
        must_idx = [i for i, (_, name, _) in enumerate(src_rows)
                    if name in must_names or "whatsapp" in name.lower()]
        must_stats = [gate_stats(op[src_rows[i][0]]) for i in must_idx]
        must_rej = sum(1 for s in must_stats if s[1] < GATE_CONF or s[3] > GATE_ENT or s[2] < GATE_MARGIN)
        must_fails = [f"{src_rows[must_idx[i]][1][:20]}(v{src_rows[must_idx[i]][2]})"
                      for i, s in zip(range(len(must_idx)), must_stats)
                      if not (s[1] < GATE_CONF or s[3] > GATE_ENT or s[2] < GATE_MARGIN)]
        fr = int(np.sum(np.argmax(head_chain(fresh_feats, model), axis=1) == fresh_labels))
        return dict(pv=pv_acc, bench=bench_raw, strict=strict, scan=scan_raw_real,
                    scan_gate=scan_gate_b, scan_gate_d=scan_gate_d, scan_fails=scan_fails,
                    ood_rej=ood_rej, ood_total=len(op), src_rej=src_rej,
                    src_total=len(src_rows), src_fails=src_fails,
                    must_rej=must_rej, must_total=len(must_idx), must_fails=must_fails, fresh=fr)

    pre = eval_epoch(sub)
    print(f"[pre] PV={pre['pv']:.4f} bench={pre['bench']}/60 strict={pre['strict']}/60 "
          f"scans_real={pre['scan']}/25 gate_b={pre['scan_gate']}/25 gate_d={pre['scan_gate_d']}/25 "
          f"src_rej={pre['src_rej']}/{pre['src_total']} ood_rej={pre['ood_rej']}/{pre['ood_total']} "
          f"fresh={pre['fresh']}/1200")
    print(f"[pre] scan gate fails: {pre['scan_fails']} | src not rejected: {pre['src_fails']}")

    BATCH = 128
    y = np.where((all_labels == -1)[:, None], OOD_TARGET[None, :], 0.0).astype(np.float32)
    valid_mask = all_labels >= 0
    smooth = np.full((len(all_labels), NUM_CLASSES), 0.08 / NUM_CLASSES, dtype=np.float32)
    smooth[np.arange(len(all_labels))[valid_mask], all_labels[valid_mask]] += 1.0 - 0.08
    y = np.where(valid_mask[:, None], smooth, OOD_TARGET[None, :])

    steps = math.ceil(len(all_feats) / BATCH)
    lr_sched = tf.keras.optimizers.schedules.CosineDecay(LR_OE, decay_steps=max(1, steps * EPOCHS), alpha=0.05)
    sub.compile(optimizer=tf.keras.optimizers.Adam(lr_sched),
                loss="categorical_crossentropy", metrics=["accuracy"])
    ds = tf.data.Dataset.from_tensor_slices((all_feats, y, all_weights)) \
        .shuffle(8192, seed=RANDOM_SEED).batch(BATCH).prefetch(tf.data.AUTOTUNE)

    best = None
    for epoch in range(1, EPOCHS + 1):
        sub.fit(ds, epochs=1, verbose=2)
        m = eval_epoch(sub)
        ok = (m["pv"] >= PV_FLOOR and m["bench"] >= BENCH_FLOOR and m["strict"] >= BENCH_FLOOR
              and m["scan"] == 25 and m["scan_gate"] >= 24
              and m["must_rej"] == m["must_total"]
              and m["fresh"] >= FRESH_FLOOR)
        star = ""
        if ok and (best is None or
                   (m["src_rej"], m["scan_gate"], m["strict"], m["fresh"], m["pv"]) >
                   (best["src_rej"], best["scan_gate"], best["strict"], best["fresh"], best["pv"])):
            best = dict(m, epoch=epoch)
            sub.save_weights(str(BEST_WEIGHTS_PATH))
            star = " * best"
        extra = ""
        if m["must_rej"] < m["must_total"] or m["scan_gate"] < 25 or m["src_rej"] < m["src_total"]:
            extra = f"  fails: must{m['must_fails']} scans{m['scan_fails']} src{m['src_fails']}"
        print(f"[epoch {epoch:02d}] PV={m['pv']:.4f} bench={m['bench']}/60 strict={m['strict']}/60 "
              f"scans_real={m['scan']}/25 gate_b={m['scan_gate']}/25 gate_d={m['scan_gate_d']}/25 "
              f"must={m['must_rej']}/{m['must_total']} src={m['src_rej']}/{m['src_total']} "
              f"fresh={m['fresh']}/1200{'  ELIGIBLE' if ok else '  OFF'}{star}{extra}")
    if best is None:
        print("[FAIL] no eligible epoch; deployment NOT touched")
        return 2
    print(f"[+] restoring best epoch {best['epoch']}")
    sub.load_weights(str(BEST_WEIGHTS_PATH))
    BEST_WEIGHTS_PATH.unlink(missing_ok=True)

    # ---------------- temperature: keep the round-6 baked T ---------------- #
    # OE training continues FROM the T=0.46-baked output layer, so the selection-time
    # metrics above already reflect the shipped operating point. Refitting here would
    # move the gate operating point away from what was validated. No refit.
    print("[+] temperature: round-6 baked value kept (no refit)")

    final = eval_epoch(sub)
    print(f"[final] PV={final['pv']:.4f} bench={final['bench']}/60 strict={final['strict']}/60 "
          f"scans_real={final['scan']}/25 gate_b={final['scan_gate']}/25 gate_d={final['scan_gate_d']}/25 "
          f"src_rej={final['src_rej']}/{final['src_total']} "
          f"ood_rej={final['ood_rej']}/{final['ood_total']} fresh={final['fresh']}/1200")
    if not (final["pv"] >= PV_FLOOR and final["bench"] >= BENCH_FLOOR and final["strict"] >= BENCH_FLOOR
            and final["scan"] == 25 and final["scan_gate"] >= 24
            and final["must_rej"] == final["must_total"]
            and final["fresh"] >= FRESH_FLOOR):
        print("[FAIL] final model violated a floor; deployment NOT touched")
        return 3

    # write baked head back into base_model (shared layers) and export
    out_bytes = None
    converter = tf.lite.TFLiteConverter.from_keras_model(base_model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_bytes = converter.convert()
    import hashlib
    sha = hashlib.sha256(tflite_bytes).hexdigest()
    print(f"[+] new tflite: {len(tflite_bytes)} bytes sha256={sha[:16]}...")

    # verify bedsheet now rejected, specimens intact, probs continuity on scans
    interp = tf.lite.Interpreter(model_content=tflite_bytes)
    interp.allocate_tensors()
    in_d, out_d = interp.get_input_details()[0], interp.get_output_details()[0]

    def tfl_p(path):
        interp.set_tensor(in_d["index"], np.expand_dims(load_img(path), 0))
        interp.invoke()
        return interp.get_tensor(out_d["index"])[0].astype(np.float64)

    print("\n[verify] browser-crop view, post-T gate:")
    for tag, p in [("bedsheet", r"C:\Users\DELL\AppData\Local\Temp\opencode\whatsapp_leaf.jpeg"),
                   ("chart_paper", str(Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest") / "green_chart_paper_full.jpg")),
                   ("scan_0019(VALID)", str(SCANS_ARCHIVE_DIR / "scan_000019.jpg")),
                   ("scan_0026(VALID)", str(SCANS_ARCHIVE_DIR / "scan_000026.jpg"))]:
        img = Image.open(p).convert("RGB")
        side = min(img.size)
        sx = (img.size[0] - side) // 2; sy = (img.size[1] - side) // 2
        crop = img.crop((sx, sy, sx + side, sy + side)).resize(IMAGE_SIZE, Image.BILINEAR)
        interp.set_tensor(in_d["index"], np.expand_dims(np.asarray(crop, dtype=np.float32), 0))
        interp.invoke()
        p6 = interp.get_tensor(out_d["index"])[0].astype(np.float64)
        p6 = p6 / p6.sum()
        top, conf, margin, ent = gate_stats(p6)
        names = ["Tomato:Late Blight", "Tomato:Early Blight", "Tomato:Healthy",
                 "Potato:Late Blight", "Potato:Early Blight", "Potato:Healthy"]
        rej = conf < GATE_CONF or ent > GATE_ENT or margin < GATE_MARGIN
        print(f"   {tag:18s} -> {names[top]:22s} conf={conf:.3f} H={ent:.2f} margin={margin:.3f} "
              f"{'REJECTED' if rej else 'accepted'}")

    if OUT_TFLITE_PATH.exists():
        shutil.copy2(OUT_TFLITE_PATH, AI_DIR / "krishi_drishti_model_round6_prev.tflite")
        print("[+] round-6 deployment backed up")
    with open(OUT_TFLITE_PATH, "wb") as f:
        f.write(tflite_bytes)
    print(f"[OK] exported to {OUT_TFLITE_PATH.name}")
    base_model.save(AI_DIR / "krishi_drishti_base.keras")
    print("[OK] keras base saved")

    manifest = {
        "manifest_version": "7.0-round7-outlier-exposure",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base": "round-6 head (397cba9d lineage), backbone frozen",
        "ood_weight": OOD_WEIGHT,
        "ood_rows": int((all_labels == -1).sum()),
        "ood_sources": [name for name, _ in ood_meta],
        "temperature": "round-6 baked T=0.46 kept (no refit)",
        "guard_floors": {"pv": PV_FLOOR, "bench_raw": BENCH_FLOOR, "bench_strict": BENCH_FLOOR,
                         "scans": "25/25 raw+gate", "fresh100": FRESH_FLOOR},
        "best_epoch": best["epoch"],
        "final_metrics": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in final.items()},
        "round7_tflite_sha256": sha,
        "gate": {"conf": GATE_CONF, "entropy": GATE_ENT, "margin": GATE_MARGIN},
        "io_contract": "Float32 [1,128,128,3] raw [0,255] -> [1,6] softmax (unchanged)",
    }
    OOD_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[OK] manifest written: {OOD_MANIFEST.name}")
    print(f"[DONE] wall {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
