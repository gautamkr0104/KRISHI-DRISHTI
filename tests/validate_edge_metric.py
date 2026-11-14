"""Validate edge-energy metric on ALL 44 SD scans + ALL 60 benchmark specimens + paper variants."""
import sys
import json
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parent.parent
WEBTEST = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")


def edge_energy(img):
    a = np.asarray(img.convert("RGB").resize((128, 128), Image.BILINEAR), dtype=np.float32)
    gray = a.mean(axis=2)
    gx = np.abs(np.diff(gray, axis=1))[:-1, :]
    gy = np.abs(np.diff(gray, axis=0))[:, :-1]
    return float(np.mean(np.hypot(gx, gy)))


results = {"paper": [], "scans": [], "bench": []}
for p in sorted(WEBTEST.glob("paper_*.jpg")) + sorted(WEBTEST.glob("green_chart_paper_*.jpg")):
    results["paper"].append({"name": p.name, "edge": round(edge_energy(Image.open(p)), 2)})
for n in range(1, 45):
    p = Path(f"E:/scan_{n:06d}.jpg")
    if p.exists():
        results["scans"].append({"scan": n, "edge": round(edge_energy(Image.open(p)), 2)})
bench = REPO / "ai_engine" / "validation_60_specimens"
for cls in sorted(bench.iterdir()):
    for f in sorted(cls.glob("*.jpg")):
        results["bench"].append({"name": f"{cls.name}/{f.name}", "edge": round(edge_energy(Image.open(f)), 2)})

print("PAPER (want ALL below threshold):")
for r in results["paper"]:
    print(f"   {r['name']:34s} {r['edge']:6.2f}")
lo_p = min(r["edge"] for r in results["paper"])
print(f"   paper max = {lo_p:.2f}")

print("\nSD SCANS below 4.0 (want: only 42/39/palms/vignettes low):")
for r in results["scans"]:
    if r["edge"] < 4.0:
        print(f"   scan_{r['scan']:06d}  {r['edge']:6.2f}")
edges = [r["edge"] for r in results["scans"]]
print(f"   scan min = {min(edges):.2f}, max = {max(edges):.2f}")

print("\nBENCHMARK specimens below 4.0 (want: NONE):")
low = [r for r in results["bench"] if r["edge"] < 4.0]
for r in low:
    print(f"   {r['name']:44s} {r['edge']:6.2f}")
if not low:
    print("   none")
be = [r["edge"] for r in results["bench"]]
print(f"   bench min = {min(be):.2f}  ({min(results['bench'], key=lambda r: r['edge'])['name']})")
print(f"   bench max = {max(be):.2f}")

Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\edge_metric_full.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
