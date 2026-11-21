"""Verify final daemon gate constants against all 44 scans."""
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
stats_path = Path(os.environ.get("TEMP", "/tmp")) / "opencode" / "scan_gate_stats.json"
if not stats_path.exists():
    stats_path = REPO / "tests" / "sd_scan_visual_audit.json"

if stats_path.exists():
    data = json.loads(stats_path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("scans", [])
else:
    rows = []

# PROPOSED daemon constants
MIN_CONFIDENCE = 0.50
MAX_ENTROPY = 1.20
MIN_FOLIAR_RATIO = 0.21
MIN_MARGIN = 0.12
MAX_DARK_FRACTION = 0.35


def gate(row):
    if row["dark"] > MAX_DARK_FRACTION:
        return "REJ_DARK"
    if row["foliar"] < MIN_FOLIAR_RATIO:
        return "REJ_FOLIAR"
    if row["conf"] < MIN_CONFIDENCE or row["ent"] > MAX_ENTROPY or row["margin"] < MIN_MARGIN:
        return "REJ_PROB"
    return "ACCEPT"


nonleaf = [x for x in rows if x["kind"].startswith("non_leaf_noise")]
hw = [x for x in rows if x["kind"].startswith(("screen_leaf_diseased", "direct_leaf"))]
screen = [x for x in rows if x["kind"].startswith("screen_leaf_diseased")]

acc_hw = [x for x in hw if gate(x) == "ACCEPT"]
rej_nl = sum(1 for x in nonleaf if gate(x) != "ACCEPT")
acc_screen = sum(1 for x in screen if gate(x) == "ACCEPT")

print(f"non-leaf rejected : {rej_nl}/{len(nonleaf)}")
print(f"screen accepted   : {acc_screen}/{len(screen)}")
print(f"hardware accepted : {len(acc_hw)}/{len(hw)}  (42 discard + 39 glare are the 2 wanted rejections)")
print("accepted scans    :", sorted(x["scan"] for x in acc_hw))
print("rejected hw scans :", sorted(x["scan"] for x in hw if gate(x) != "ACCEPT"))
