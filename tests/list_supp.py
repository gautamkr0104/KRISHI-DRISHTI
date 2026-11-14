import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"C:\Users\DELL\AppData\Local\Temp\opencode\supp_candidates\candidates_manifest.json", encoding="utf-8"))
for x in d:
    print(f"[{x['class']:22s}] {x['title'][:78]}")
