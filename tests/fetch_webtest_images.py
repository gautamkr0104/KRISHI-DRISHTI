"""Download test leaf images from Wikimedia Commons for external validation."""
import json
import urllib.request
import urllib.parse
from pathlib import Path

OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
OUT.mkdir(exist_ok=True)

QUERIES = {
    "tomato_late_blight": "tomato late blight leaf",
    "tomato_early_blight": "tomato early blight leaf",
    "tomato_healthy": "tomato leaf healthy green",
    "potato_late_blight": "potato late blight leaf",
    "potato_early_blight": "potato early blight leaf alternaria",
    "potato_healthy": "potato leaf healthy",
}

API = "https://commons.wikimedia.org/w/api.php"
HDRS = {"User-Agent": "KRISHI-DRISHTI-external-validation/1.0 (educational project)"}

def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HDRS)
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())

manifest = {}
for tag, q in QUERIES.items():
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": "6", "gsrlimit": "6",
        "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "800",
    }
    try:
        data = api(params)
        pages = data.get("query", {}).get("pages", {})
        results = []
        for p in pages.values():
            ii = p.get("imageinfo", [{}])[0]
            results.append({"title": p.get("title"), "url": ii.get("thumburl") or ii.get("url"),
                            "w": ii.get("width"), "h": ii.get("height")})
        manifest[tag] = results
        print(f"{tag}: {len(results)} candidates")
        for r in results[:4]:
            print(f"   {r['title']}")
    except Exception as e:
        print(f"{tag}: ERROR {e}")
        manifest[tag] = []

Path(OUT / "candidates.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
