"""
================================================================================
 KRISHI-DRISHTI :: ONE-SHOT AUTONOMOUS PIPELINE (run once when harvest completes)
================================================================================
 OFFLINE-SAFE (no internet needed). Steps:
   0. Baselines of the CURRENTLY DEPLOYED model (round-5 5de439ef) computed here:
        - fresh100 raw argmax (new honest web test)
        - benchmark-60 strict daemon score
        - OOD chart-paper + palm rejection
   1. split_fresh100 (seed 42)
   2. ai_engine/finetune_v7_web10k.py  (guarded head fine-tune on harvest-10k)
   3. Same three gates recomputed for the NEW model (from ROUND6 manifest +
      recomputed benchmark strict + OOD with the daemon)
   4. SHIP decision (no human in the loop):
        ship  iff  fresh100 >= baseline_fresh100 + 2
              and  benchmark strict >= baseline_bench_strict
              and  OOD reject == 6/6
        else: ai_engine deployment restored to previous tflite; SD untouched.
   5. If shipped and E:\ mounted: copy new tflite to SD (old one overwritten),
      SHA-verified. If E:\ not mounted: repo keeps winner; SD updated when the
      card returns.
   6. Writes ROUND6_COMPARISON.json + prints the comparison table.
   7. Best-effort git commit+push (skipped silently if offline).
================================================================================
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(r"C:\Users\DELL\Downloads\KRISHI-DRISHTI")
AI_DIR = REPO / "ai_engine"
TESTS_DIR = REPO / "tests"
BASE = Path(r"C:\Users\DELL\Documents\Default Project\webtest100")
PY = sys.executable
MODEL = AI_DIR / "krishi_drishti_model.tflite"
LABELS = AI_DIR / "labels.json"
PREV_BACKUP = AI_DIR / "krishi_drishti_model_round5_prev.tflite"
SPECIMEN_DIR = AI_DIR / "validation_60_specimens"
SD_MODEL = Path(r"E:\krishi_drishti_model.tflite")

CANONICAL_TO_IDX = {
    "Potato___Early_blight": 4, "Potato___Late_blight": 3, "Potato___healthy": 5,
    "Tomato___Early_blight": 1, "Tomato___Late_blight": 0, "Tomato___healthy": 2,
}

def sha16(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def merge_burst():
    """Validate + dedupe + absorb the burst-downloaded raw files (saved during
    the connectivity window; never PIL-validated or deduped until now)."""
    import io
    km_path = BASE / "harvest10k" / "kept_manifest.json"
    manifest = json.loads(km_path.read_text(encoding="utf-8"))
    prior_sha = {r["sha256"] for r in manifest}
    prior_ph = {r["phash"] for r in manifest}
    # project priors (same sets the harvest deduped against)
    for d in [BASE / "images", BASE / "supp_keep", BASE / "supp_pool",
              REPO / "ai_engine" / "web_supplements",
              REPO / "ai_engine" / "validation_60_specimens",
              REPO / "tests" / "sd_card_scans_archive_r3"]:
        if d.exists():
            for f in d.rglob("*"):
                if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and f.is_file():
                    try:
                        b = f.read_bytes()
                        prior_sha.add(hashlib.sha256(b).hexdigest())
                        im = Image.open(io.BytesIO(b)).convert("RGB")
                        prior_ph.add(hashlib.sha256(im.resize((64, 64)).tobytes()).hexdigest())
                    except Exception:
                        pass
    try:
        prior_sha.update(json.loads((BASE / "prior_hashes.json").read_text(encoding="utf-8"))["sha256"])
    except Exception:
        pass
    counter = len(manifest)
    added = 0

    def absorb(img, label, murl, turl):
        nonlocal counter, added
        w, h = img.size
        fsha = hashlib.sha256(img.tobytes()).hexdigest()
        phash = hashlib.sha256(img.resize((64, 64)).tobytes()).hexdigest()
        if fsha in prior_sha or phash in prior_ph:
            return False
        prior_sha.add(fsha)
        prior_ph.add(phash)
        counter += 1
        fname = f"{label}__{counter:06d}.jpg"
        fpath = BASE / "harvest10k" / "kept" / label / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)
        img.save(fpath, "JPEG", quality=92)
        manifest.append({"file": f"{label}/{fname}", "label": label, "query": "burst",
                         "murl": murl, "turl": turl, "sha256": fsha, "phash": phash,
                         "w": w, "h": h, "bytes": fpath.stat().st_size})
        added += 1
        return True

    LABELS_OK = {"Tomato___Late_blight", "Tomato___Early_blight", "Tomato___healthy",
                 "Potato___Late_blight", "Potato___Early_blight", "Potato___healthy"}

    for burst_name, burst_dir in (("burst", "burst"), ("burst2", "burst2")):
        bm_path = BASE / "harvest10k" / f"{burst_name}_manifest.json"
        rows = []
        if bm_path.exists():
            try:
                rows = json.loads(bm_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  [merge] {burst_name} manifest unreadable: {e}")
        for r in rows:
            p = BASE / r["file"]
            if not p.exists():
                continue
            try:
                img = Image.open(io.BytesIO(p.read_bytes())).convert("RGB")
                w, h = img.size
                if min(w, h) < 160 or not (0.35 <= w / h <= 2.8):
                    p.unlink(missing_ok=True)
                    continue
            except Exception:
                p.unlink(missing_ok=True)
                continue
            if absorb(img, r["label"], r.get("murl"), r.get("turl")):
                p.unlink(missing_ok=True)
        # sweep burst files missing from the manifest (flush window at kill time)
        for f in (BASE / "harvest10k" / burst_dir).glob("*/*.jpg"):
            label = f.parent.name
            if label not in LABELS_OK:
                continue
            try:
                img = Image.open(io.BytesIO(f.read_bytes())).convert("RGB")
                w, h = img.size
                if min(w, h) < 160 or not (0.35 <= w / h <= 2.8):
                    f.unlink(missing_ok=True)
                    continue
            except Exception:
                f.unlink(missing_ok=True)
                continue
            if absorb(img, label, None, None):
                f.unlink(missing_ok=True)
    km_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for burst_name in ("burst", "burst2"):
        (BASE / "harvest10k" / f"{burst_name}_manifest.json").unlink(missing_ok=True)
    return added


def daemon():
    sys.path.insert(0, str(AI_DIR))
    import ai_engine.krishi_ai_daemon as K
    return K.KrishiAIDaemon(str(MODEL), str(LABELS))


def bench_strict(d):
    """Strict 6-class daemon score on the 60 held-out specimens."""
    exact = total = 0
    for folder in sorted(CANONICAL_TO_IDX):
        fdir = SPECIMEN_DIR / folder
        true_cls = folder.replace("___", " ").replace("_", " ")  # not used; map below
        true_label = {"Potato___Early_blight": "Potato Early Blight",
                      "Potato___Late_blight": "Potato Late Blight",
                      "Potato___healthy": "Potato Healthy",
                      "Tomato___Early_blight": "Tomato Early Blight",
                      "Tomato___Late_blight": "Tomato Late Blight",
                      "Tomato___healthy": "Tomato Healthy"}[folder]
        for f in sorted(fdir.iterdir()):
            if f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            res = d.run_inference(Image.open(f))
            pred = f"{res['crop']} {res['disease']}" if res["crop"] != "Unknown" else res["disease"]
            total += 1
            if pred == true_label:
                exact += 1
    return exact, total


def ood_reject(d):
    """Chart papers (synthesized, seed 7) + 4 archived palm scans. Returns rejected/total."""
    rng = np.random.default_rng(7)
    tmp = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
    tmp.mkdir(parents=True, exist_ok=True)

    def synth_paper(size, base=(58, 138, 68), grain=6.0, vignette=0.10, jitter=2.0):
        w, h = size
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        grad = 1.0 + vignette * ((xx / w - 0.35) * 0.6 + (yy / h - 0.45) * 0.4)
        img = np.zeros((h, w, 3), dtype=np.float32)
        for c in range(3):
            img[:, :, c] = base[c] * grad
        img += rng.normal(0, grain, (h, w, 3))
        img += np.array([jitter, 0, -jitter])
        return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

    paper_full = synth_paper((960, 1280))
    paper_full.save(tmp / "green_chart_paper_full.jpg", quality=92)
    paper_partial = Image.new("RGB", (960, 1280))
    paper_partial.paste(synth_paper((960, 900)), (0, 0))
    bg = np.zeros((1280 - 900, 960, 3), dtype=np.float32)
    bg[..., 0] = 96 + rng.normal(0, 8, (1280 - 900, 960))
    bg[..., 1] = 74 + rng.normal(0, 8, (1280 - 900, 960))
    bg[..., 2] = 52 + rng.normal(0, 8, (1280 - 900, 960))
    paper_partial.paste(Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)), (0, 900))
    paper_partial.save(tmp / "green_chart_paper_partial.jpg", quality=92)

    tests = [(tmp / "green_chart_paper_full.jpg", "reject"),
             (tmp / "green_chart_paper_partial.jpg", "reject")]
    arch = TESTS_DIR / "sd_card_scans_archive_r3"
    for n in (4, 5, 6, 7):
        tests.append((arch / f"scan_{n:06d}.jpg", "reject"))
    rejected = 0
    for p, _ in tests:
        res = d.run_inference(Image.open(p))
        if res["status"] == "UNCERTAIN" or res["crop"] == "Unknown":
            rejected += 1
    return rejected, len(tests)


def fresh100_raw():
    """Raw argmax on the fresh held-out pool with a tflite interpreter."""
    import tensorflow as tf
    CLASS_TO_IDX = {
        "Tomato___Late_blight": 0, "Tomato___Early_blight": 1, "Tomato___healthy": 2,
        "Potato___Late_blight": 3, "Potato___Early_blight": 4, "Potato___healthy": 5,
    }
    manifest = json.loads((BASE / "fresh100_manifest.json").read_text(encoding="utf-8"))
    interp = tf.lite.Interpreter(model_path=str(MODEL))
    interp.allocate_tensors()
    in_d, out_d = interp.get_input_details()[0], interp.get_output_details()[0]
    ok = 0
    pool = BASE / "harvest10k" / "kept"
    for r in manifest:
        arr = np.asarray(Image.open(pool / r["file"]).convert("RGB")
                         .resize((128, 128), Image.BILINEAR), dtype=np.float32)
        interp.set_tensor(in_d["index"], np.expand_dims(arr, 0))
        interp.invoke()
        probs = interp.get_tensor(out_d["index"])[0]
        if int(np.argmax(probs)) == CLASS_TO_IDX[r["label"]]:
            ok += 1
    return ok, len(manifest)


def main():
    t0 = time.time()
    print("=" * 84)
    print("  KRISHI-DRISHTI :: ONE-SHOT AUTONOMOUS PIPELINE (round-6 web-scale)")
    print("=" * 84)

    if not (BASE / "harvest10k" / "kept_manifest.json").exists():
        print("[FAIL] harvest10k kept_manifest.json missing - harvest not complete")
        return 1

    # -------- step -1: merge burst downloads (offline validate + dedupe) -------- #
    added = merge_burst()
    print(f"[merge] burst images merged into kept pool: +{added}")

    # -------- step 0a: split (MUST precede the fresh-pool baseline) -------- #
    print("\n[step 0a] Splitting harvest into held-out test pool + train pool (seed 42)...")
    subprocess.run([PY, str(BASE / "split_fresh100.py")], check=True)

    # -------- step 0: baselines of currently deployed model -------- #
    print("\n[step 0] Baselines with currently deployed model:", sha16(MODEL))
    d = daemon()
    b_pre, n_pre = bench_strict(d)
    o_pre, on_pre = ood_reject(d)
    print(f"  benchmark strict: {b_pre}/{n_pre} | OOD rejected: {o_pre}/{on_pre}")
    f_pre, fn_pre = fresh100_raw()
    print(f"  fresh100 raw:     {f_pre}/{fn_pre}")
    del d

    # -------- step 2: guarded fine-tune -------- #
    print("\n[step 2] Running guarded round-6 fine-tune (cached features)...")
    r = subprocess.run([PY, str(AI_DIR / "finetune_v7_web10k.py")])
    if r.returncode != 0:
        print(f"[ABORT] fine-tune exited {r.returncode}; deployment untouched, SD untouched.")
        return 2

    # -------- step 3: gates on the new model -------- #
    print("\n[step 3] Gates on the new model:", sha16(MODEL))
    d = daemon()
    b_post, n_post = bench_strict(d)
    o_post, on_post = ood_reject(d)
    del d
    m = json.loads((AI_DIR / "ROUND6_FINETUNE_MANIFEST.json").read_text(encoding="utf-8"))
    f_post = m["final_metrics"]["fresh100_raw_tflite"]
    fn_post = fn_pre
    print(f"  benchmark strict: {b_post}/{n_post} | OOD rejected: {o_post}/{on_post} | "
          f"fresh held-out raw: {f_post}/{fn_post}")

    # -------- step 4: ship decision -------- #
    margin = max(2, round(0.004 * fn_pre))   # >=0.4% of the held-out pool
    ship = (f_post >= f_pre + margin) and (b_post >= b_pre) and (o_post == on_post)
    print("\n[step 4] SHIP DECISION:")
    print(f"  held-out web pool: {f_pre} -> {f_post}  (need >= +{margin})   "
          f"{'PASS' if f_post >= f_pre + margin else 'FAIL'}")
    print(f"  benchmark: {b_pre}/{n_pre} -> {b_post}/{n_post} (need >=) "
          f"{'PASS' if b_post >= b_pre else 'FAIL'}")
    print(f"  OOD:       {o_pre}/{on_pre} -> {o_post}/{on_post} (need all rejected) "
          f"{'PASS' if o_post == on_post else 'FAIL'}")

    comparison = {
        "decided_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "previous_model_sha16": sha16(PREV_BACKUP) if PREV_BACKUP.exists() else None,
        "new_model_sha16": sha16(MODEL),
        "heldout_web_pool": {"size": fn_pre, "pre": f_pre, "post": f_post},
        "benchmark_strict": {"pre": b_pre, "post": b_post},
        "ood_rejected": {"pre": o_pre, "post": o_post},
        "scans_agreement": m["final_metrics"].get("audited_scan_agreement_tflite"),
        "ship": ship,
    }

    # -------- step 5: SD update / rollback -------- #
    if ship:
        print("\n[step 5] SHIPPED - updating SD card if mounted...")
        try:
            new_sha = hashlib.sha256(MODEL.read_bytes()).hexdigest()
            shutil.copy2(MODEL, SD_MODEL)
            sd_sha = hashlib.sha256(SD_MODEL.read_bytes()).hexdigest()
            print(f"  SD model: {sd_sha[:16]} {'MATCH' if sd_sha == new_sha else 'MISMATCH!'}")
            comparison["sd_updated"] = sd_sha == new_sha
        except Exception as e:
            print(f"  [WARN] SD not updated ({type(e).__name__}: {str(e)[:80]}); "
                  "repo + release hold the winner; copy when card returns.")
            comparison["sd_updated"] = False
    else:
        print("\n[step 5] NOT SHIPPED - restoring previous deployment in repo...")
        if PREV_BACKUP.exists():
            shutil.copy2(PREV_BACKUP, MODEL)
            print(f"  ai_engine deployment restored to {sha16(MODEL)} (round-5); SD untouched.")
        comparison["sd_updated"] = False

    (AI_DIR / "ROUND6_COMPARISON.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print("\n[OK] comparison written: ai_engine/ROUND6_COMPARISON.json")

    # -------- step 7: best-effort git push (offline-tolerant) -------- #
    print("\n[step 7] Best-effort git commit+push...")
    try:
        subprocess.run(["git", "-C", str(REPO), "add", "ai_engine/finetune_v7_web10k.py",
                        "ai_engine/ROUND6_FINETUNE_MANIFEST.json", "ai_engine/ROUND6_COMPARISON.json",
                        "ai_engine/krishi_drishti_model.tflite",
                        "tests/benchmark_60_specimens_report.json"], check=True, timeout=60)
        subprocess.run(["git", "-C", str(REPO), "commit", "-m",
                        f"round-6: web-scale weak-labeled fine-tune (harvest-10k). "
                        f"fresh100 {f_pre}->{f_post}, bench {b_pre}->{b_post}, OOD {o_post}/{on_post}. "
                        f"ship={ship}"], check=True, timeout=120)
        subprocess.run(["git", "-C", str(REPO), "push", "origin", "main"], check=True, timeout=180)
        print("  pushed.")
    except Exception as e:
        print(f"  [offline] git step skipped ({type(e).__name__}). Push when internet returns.")

    print(f"\n[DONE] wall {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
