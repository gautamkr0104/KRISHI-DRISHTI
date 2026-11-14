"""Zip PlantDoc_Solanaceae + split into tmpfiles-sized chunks for Colab staging."""
import subprocess
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = Path(r"C:\Users\DELL\.cache\PlantDoc_Solanaceae")
OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\colab_stage")
OUT.mkdir(exist_ok=True)
zip_path = OUT / "colab_bundle_v4.zip"

if not zip_path.exists():
    print("zipping...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        # normalize to forward slashes with a top-level PlantDoc_Solanaceae folder
        for f in sorted(SRC.rglob("*.jpg")):
            rel = "PlantDoc_Solanaceae/" + f.relative_to(SRC).as_posix()
            zf.write(f, rel)
        # also include the class subdirectories implicitly
    print(f"zip done: {zip_path.stat().st_size/1048576:.1f} MB")

CHUNK = 40 * 1024 * 1024
data = zip_path.read_bytes()
n_chunks = (len(data) + CHUNK - 1) // CHUNK
for i in range(n_chunks):
    c = OUT / f"chunk{i}.bin"
    c.write_bytes(data[i * CHUNK:(i + 1) * CHUNK])
    print(f"chunk{i}.bin  {c.stat().st_size/1048576:.1f} MB")
print(f"TOTAL {n_chunks} chunks, {len(data)/1048576:.1f} MB")
