"""Fetch outdoor field supplement candidates from Wikimedia Commons (round-3)."""
import hashlib
import json
import socket
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
socket.setdefaulttimeout(40)
HDRS = {"User-Agent": "KRISHI-DRISHTI-external-validation/1.0 (educational project)"}
API = "https://commons.wikimedia.org/w/api.php"
OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\supp_candidates")
OUT.mkdir(exist_ok=True)


def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=40).read().decode())


QUERIES = {
    "Potato___healthy": [
        "potato field plants Solanum tuberosum",
        "potato crop foliage rows",
        "potato plant leaves field",
    ],
    "Tomato___healthy": [
        "tomato field plants staked",
        "tomato greenhouse plants foliage",
        "tomato plantation rows",
    ],
    "Potato___Late_blight": [
        "phytophthora infestans potato field",
        "potato late blight field",
    ],
    "Tomato___Late_blight": [
        "tomato late blight field",
        "phytophthora infestans tomato",
    ],
    "Potato___Early_blight": [
        "alternaria solani potato leaf",
    ],
    "Tomato___Early_blight": [
        "alternaria solani tomato leaf lesion",
    ],
}

seen_titles = set()
downloaded = []
for cls, queries in QUERIES.items():
    for q in queries:
        params = {"action": "query", "format": "json", "generator": "search",
                  "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": "6", "gsrlimit": "10",
                  "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "1024"}
        try:
            pages = api(params).get("query", {}).get("pages", {})
        except Exception as e:
            print(f"[{cls}] '{q}' ERR {e}")
            continue
        for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
            t = p.get("title", "")
            if t in seen_titles:
                continue
            seen_titles.add(t)
            ii = p.get("imageinfo", [{}])[0]
            u = ii.get("thumburl") or ii.get("url")
            if not u:
                continue
            safe = t.replace("File:", "").replace("/", "_").replace(" ", "_")
            for ch in "()\",:'":
                safe = safe.replace(ch, "")
            safe = safe[:90] + ".jpg"
            dest = OUT / safe
            if dest.exists():
                continue
            try:
                data = urllib.request.urlopen(urllib.request.Request(u, headers=HDRS), timeout=40).read()
                dest.write_bytes(data)
                downloaded.append({"title": t, "class": cls, "file": safe,
                                   "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
                print(f"OK  [{cls}] {t} ({len(data)} B)")
            except Exception as e:
                print(f"ERR {t}: {e}")

(OUT / "candidates_manifest.json").write_text(json.dumps(downloaded, indent=1), encoding="utf-8")
print(f"\nTotal downloaded: {len(downloaded)} -> {OUT}")
