"""Update the SD card (E:\) with the verified round-4 model.
Run ONLY after the full gate suite passes. SHA-verified copy; preserves history:
- current deployment -> krishi_drishti_model_round3_backup.tflite (new)
- existing v2/round2 backups untouched"""
import hashlib, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = Path(r"C:\Users\DELL\Downloads\KRISHI-DRISHTI\ai_engine\krishi_drishti_model.tflite")
SD = Path("E:/")
SD_MODEL = SD / "krishi_drishti_model.tflite"
SD_BACKUP = SD / "krishi_drishti_model_round3_backup.tflite"

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

src_sha = sha(SRC)
print(f"new model sha256: {src_sha}")

if SD_BACKUP.exists():
    print("round3 backup already on card:", SD_BACKUP.name)
else:
    if SD_MODEL.exists():
        shutil.copy2(SD_MODEL, SD_BACKUP)
        b = sha(SD_BACKUP)
        assert b == sha(SD_MODEL), "backup sha mismatch"
        print(f"[+] previous deployment backed up on SD: {SD_BACKUP.name} ({b[:16]}...)")

shutil.copy2(SRC, SD_MODEL)
sd_sha = sha(SD_MODEL)
assert sd_sha == src_sha, "SD copy sha mismatch!"
print(f"[OK] SD updated: E:\\krishi_drishti_model.tflite = {sd_sha}")
print("[OK] SHA-verified match with repo deployment model")
