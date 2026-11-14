"""Assemble verified outdoor field supplements into ai_engine/field_supplements/."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(r"C:\Users\DELL\Downloads\KRISHI-DRISHTI")
SUPP = REPO / "ai_engine" / "field_supplements"
CAND = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\supp_candidates")
WEBTEST = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
SUPP.mkdir(exist_ok=True)

# (source file, class, commons title, verified_by)
ENTRIES = [
    ("194_-_PEI_Potatoes.JPG.jpg", "Potato___healthy", "File:194 - PEI Potatoes.JPG", "GM"),
    ("Aardappelveld_bij_Heusden.jpg.jpg", "Potato___healthy", "File:Aardappelveld bij Heusden.jpg", "GM"),
    ("Bjare_Peninsula_Cultivation.jpg.jpg", "Potato___healthy", "File:Bjare Peninsula Cultivation.jpg", "GM"),
    ("Berezhany-_65.jpg.jpg", "Potato___healthy", "File:Berezhany- (65).jpg", "GM"),
    ("Bozköyde_bir_patates_tarlası.JPG.jpg", "Potato___healthy", "File:Bozköy'de bir patates tarlası.JPG", "GM"),
    ("-2018-09-04_Flowering_potato_plant_Trimingham_Norfolk.JPG.jpg", "Potato___healthy",
     "File:-2018-09-04 Flowering potato plant, Trimingham, Norfolk.JPG", "GM"),
    ("Potato_plantations_in_Phobjikha.jpg.jpg", "Potato___healthy", "File:Potato plantations in Phobjikha.jpg", "GM"),
    ("Maris_Piper_side_view.jpg.jpg", "Potato___healthy", "File:Maris Piper side view.jpg", "GM"),
    ("Potato_Flower_on_the_field.jpg.jpg", "Potato___healthy", "File:Potato Flower on the field.jpg", "GM"),
    ("../webtest/Potato_leaves.jpg", "Potato___healthy", "File:Potato leaves.jpg", "GM"),
    ("../webtest/Potato_plant.jpg", "Potato___healthy", "File:Potato plant.jpg", "GM"),
    ("../webtest/Potato_plants.jpg", "Potato___healthy", "File:Potato plants.jpg", "GM"),
    ("Alternaria_solani_01.JPG.jpg", "Potato___Early_blight", "File:Alternaria solani 01.JPG", "GM"),
    ("Alternaria_solani_IMG_1661.jpg.jpg", "Potato___Early_blight", "File:Alternaria solani IMG 1661.jpg", "GM"),
    ("Alternaria_solani_a1_2.jpg.jpg", "Tomato___Early_blight", "File:Alternaria solani a1 (2).jpg", "GM"),
    ("Tomato_Support_5843173257.jpg.jpg", "Tomato___healthy", "File:Tomato Support 5843173257.jpg", "GM"),
]

manifest = []
for src, cls, title, ver in ENTRIES:
    p = (CAND / src) if not src.startswith("..") else (WEBTEST / Path(src).name)
    if not p.exists():
        print(f"MISSING: {src}")
        continue
    data = p.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    dest = SUPP / f"{cls}__{sha[:12]}.jpg"
    dest.write_bytes(data)
    manifest.append({
        "file": dest.name, "class": cls, "source": title,
        "sha256": sha, "bytes": len(data), "verified": ver,
        "license": "Wikimedia Commons (see source page)",
    })
    print(f"OK  {dest.name}  <- {title[:60]}")

(SUPP / "field_supplements_manifest.json").write_text(json.dumps({
    "purpose": "Round-3 outdoor-domain supplement set: hand-verified real field photos "
               "(healthy outdoor Solanaceae foliage + outdoor blight lesions). Fixes the "
               "zero-outdoor-Potato-healthy gap found in the internet-image audit.",
    "added": "2026-11-14",
    "images": manifest,
}, indent=1), encoding="utf-8")
print(f"\nTotal: {len(manifest)} images -> {SUPP}")
