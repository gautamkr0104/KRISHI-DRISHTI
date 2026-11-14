"""Download candidate leaf images from Wikimedia Commons by exact title."""
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
OUT.mkdir(exist_ok=True)
HDRS = {"User-Agent": "KRISHI-DRISHTI-external-validation/1.0 (educational project)"}
API = "https://commons.wikimedia.org/w/api.php"

TITLES = [
    # late blight
    "File:Late blight on tomato leaf (7871756748).jpg",
    "File:Tomato late blight leaf curl 2 (5816171413).jpg",
    "File:Late blight on potato leaf 2.jpg",
    "File:Phytophthora infestans on potato leaf.jpg",
    "File:Phytophthora infestans on potato leaf 2.jpg",
    # early blight
    "File:Alternaria solani - leaf lesions.jpg",
]

def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HDRS)
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())

def search_first(title_contains, q, n=8):
    params = {"action": "query", "format": "json", "generator": "search",
              "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": "6", "gsrlimit": str(n),
              "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "800"}
    pages = api(params).get("query", {}).get("pages", {})
    out = []
    for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
        t = p.get("title", "")
        ii = p.get("imageinfo", [{}])[0]
        out.append((t, ii.get("thumburl") or ii.get("url"), ii.get("width"), ii.get("height")))
    return out

# gather candidates
targets = list(TITLES)
for q in ["tomato leaf green", "tomato foliage", "Solanum tuberosum leaves plant"]:
    hits = search_first("", q)
    print(f"SEARCH: {q}")
    for t, u, w, h in hits[:6]:
        print(f"   {t} ({w}x{h})")
        targets.append(t)

# resolve URLs for exact titles (chunked)
urlmap = {}
for i in range(0, len(targets), 20):
    chunk = targets[i:i + 20]
    params = {"action": "query", "format": "json", "titles": "|".join(chunk),
              "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "800"}
    for p in api(params).get("query", {}).get("pages", {}).values():
        ii = p.get("imageinfo", [{}])[0]
        u = ii.get("thumburl") or ii.get("url")
        if u:
            urlmap[p["title"]] = u

# download
downloaded = []
for t, u in urlmap.items():
    safe = t.replace("File:", "").replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "")[:80]
    dest = OUT / safe
    try:
        req = urllib.request.Request(u, headers=HDRS)
        data = urllib.request.urlopen(req, timeout=90).read()
        dest.write_bytes(data)
        downloaded.append({"title": t, "path": str(dest), "bytes": len(data)})
        print(f"OK  {t}")
    except Exception as e:
        print(f"ERR {t}: {e}")

(OUT / "downloaded.json").write_text(json.dumps(downloaded, indent=1), encoding="utf-8")
print(f"\nDownloaded {len(downloaded)} images to {OUT}")
