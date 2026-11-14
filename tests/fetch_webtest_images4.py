"""Download remaining candidate images with strict per-request timeouts."""
import json
import sys
import urllib.request
import urllib.parse
import socket
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
socket.setdefaulttimeout(45)
OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
HDRS = {"User-Agent": "KRISHI-DRISHTI-external-validation/1.0 (educational project)"}
API = "https://commons.wikimedia.org/w/api.php"

TITLES = [
    "File:Tomato late blight leaf curl 2 (5816171413).jpg",
    "File:Phytophthora infestans on potato leaf.jpg",
    "File:Phytophthora infestans on potato leaf 2.jpg",
    "File:Tomato leaf.jpg",
    "File:Tomato leaf 2.jpg",
    "File:Tomato leaves.jpg",
    "File:Potato leaf.jpg",
    "File:Potato leaves.jpg",
    "File:Potato plant.jpg",
    "File:Potato plants.jpg",
    "File:Potato foliage.jpg",
]

def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HDRS)
    return json.loads(urllib.request.urlopen(req, timeout=45).read().decode())

params = {"action": "query", "format": "json", "titles": "|".join(TITLES),
          "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "800"}
urlmap = {}
for p in api(params).get("query", {}).get("pages", {}).values():
    ii = p.get("imageinfo", [{}])[0]
    u = ii.get("thumburl") or ii.get("url")
    if u:
        urlmap[p["title"]] = u
print("resolved:", len(urlmap))
for t in TITLES:
    if t not in urlmap:
        print("missing:", t)

results = []
for t, u in urlmap.items():
    safe = t.replace("File:", "").replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "")[:80]
    dest = OUT / safe
    if dest.exists():
        print("have:", t)
        continue
    try:
        req = urllib.request.Request(u, headers=HDRS)
        data = urllib.request.urlopen(req, timeout=45).read()
        dest.write_bytes(data)
        results.append(t)
        print(f"OK  {t}  {len(data)}")
    except Exception as e:
        print(f"ERR {t}: {e}")
