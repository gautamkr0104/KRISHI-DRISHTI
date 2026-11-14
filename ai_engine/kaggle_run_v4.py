"""KRISHI-DRISHTI v4 round-3 training runner (Kaggle notebook script).

Runs inside a Kaggle GPU notebook:
  1. Unzips the staged PlantDoc bundle (attached as a Kaggle dataset).
  2. Clones the public KRISHI-DRISHTI repo (v4 pipeline + field supplements).
  3. Downloads the PV corpus via kagglehub.
  4. Patches Windows paths in the PlantDoc manifest to the staged location.
  5. Runs train_model_v4.py; copies artifacts to /kaggle/working for export.
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORK = Path("/kaggle/working")
STAGE = Path("/content/stage")
REPO = Path("/content/KRISHI-DRISHTI")

# 1. locate staged PlantDoc tree (Kaggle mounts datasets under
#    /kaggle/input/datasets/<owner>/<slug>/ — search recursively) ---------------
pd_root = None
for cand in sorted(Path("/kaggle/input").rglob("PlantDoc_Solanaceae")):
    if cand.is_dir() and any(cand.rglob("*.jpg")):
        pd_root = cand
        break
if pd_root is None:  # fallback: raw zip still present
    zips = list(Path("/kaggle/input").rglob("colab_bundle_v4.zip"))
    print("found bundles:", zips)
    assert zips, "PlantDoc staging not attached"
    STAGE.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zips[0]) as zf:
        zf.extractall(STAGE)
    pd_root = STAGE / "PlantDoc_Solanaceae"
pd_count = len(list(pd_root.rglob("*.jpg")))
print(f"PlantDoc staged: {pd_count} jpgs at {pd_root}")
assert pd_count > 400, "PlantDoc staging incomplete"

# 2. clone repo ---------------------------------------------------------------
subprocess.run(["git", "clone", "--depth", "1",
                "https://github.com/gautamkr0104/KRISHI-DRISHTI.git", str(REPO)], check=True)

# 3. PV corpus — attached via Kaggle dataset_sources (vipoooool dataset).
#    New Kaggle mount layout: /kaggle/input/datasets/<owner>/<slug>/...
pv_known = Path("/kaggle/input/datasets/vipoooool/new-plant-diseases-dataset/"
                "new plant diseases dataset(augmented)/New Plant Diseases Dataset(Augmented)/train")
if pv_known.exists() and (pv_known / "Tomato___Late_blight").exists():
    pv_train_dir = pv_known
else:
    print("scanning mounts for PV train dir (slow, ~5 min)...")
    pv_train_dir = None
    for c in Path("/kaggle/input").rglob("train"):
        if c.is_dir() and (c / "Tomato___Late_blight").exists():
            pv_train_dir = c
            break
print("PV train dir:", pv_train_dir)
assert pv_train_dir, "PV dataset not attached"

# 4. patch manifest paths -----------------------------------------------------
man = REPO / "ai_engine" / "PLANTDOC_HOLDOUT_MANIFEST.json"
d = man.read_text(encoding="utf-8")
winprefix = "C:" + ("\\" * 2) + "Users" + ("\\" * 2) + "DELL" + ("\\" * 2) + ".cache" + ("\\" * 2) + "PlantDoc_Solanaceae"
d = d.replace(winprefix, str(pd_root))
# normalize remaining Windows separators (JSON raw text holds them as \\ pairs)
d = d.replace("\\" * 2, "/")
man.write_text(d, encoding="utf-8")
print("manifest patched:", d.count(str(pd_root)), "staged refs")

# 5. run v4 training ----------------------------------------------------------
os.chdir(REPO)
import tensorflow as tf
print("TensorFlow:", tf.__version__)
print("GPUs:", tf.config.list_physical_devices("GPU"))
r = subprocess.run([sys.executable, "ai_engine/train_model_v4.py"], cwd=REPO,
                   env={**os.environ, "KRISHI_PV_TRAIN_DIR": str(pv_train_dir)})
print("train exit code:", r.returncode)
if r.returncode != 0:
    raise SystemExit(r.returncode)

# 6. export artifacts to /kaggle/working --------------------------------------
for f in ["krishi_drishti_model.tflite", "krishi_drishti_base.keras",
          "TRAINING_RUN_MANIFEST.json", "ROUND2_FINETUNE_MANIFEST.json"]:
    p = REPO / "ai_engine" / f
    if p.exists():
        shutil.copy2(p, WORK / f)
        print("exported:", f, (WORK / f).stat().st_size, "bytes")
print("DONE")
