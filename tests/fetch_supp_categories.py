"""Round 2: fetch from specific Commons categories (field photos, not catalogs)."""
import hashlib
import json
import socket
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
socket.setdefaulttimeout(30)
HDRS = {"User-Agent": "KRISHI-DRISHTI-external-validation/1.0 (educational project)"}
API = "https://commons.wikimedia.org/w/api.php"

# DNS on this machine flaps mid-run; cache every successful resolution forever.
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache = {}


def _cached_getaddrinfo(host, *args, **kwargs):
    key = (str(host), tuple(args), tuple(sorted(kwargs.items())))
    if key not in _dns_cache:
        _dns_cache[key] = _orig_getaddrinfo(host, *args, **kwargs)
    return _dns_cache[key]


socket.getaddrinfo = _cached_getaddrinfo
OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\supp_candidates")
OUT.mkdir(exist_ok=True)


def api(params, attempts=3):
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for _ in range(attempts):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=30).read().decode())
        except Exception as e:
            last = e
            import time
            time.sleep(2)
    raise last


CATS = [
    ("Potato___healthy", "Category:Potato fields"),
    ("Potato___healthy", "Category:Solanum tuberosum foliage"),
    ("Potato___healthy", "Category:Potato plants"),
    ("Tomato___healthy", "Category:Tomato fields"),
    ("Tomato___healthy", "Category:Tomato plants"),
    ("Potato___Late_blight", "Category:Phytophthora infestans"),
    ("Tomato___Late_blight", "Category:Late blight of tomato"),
    ("Potato___Early_blight", "Category:Alternaria solani"),
    ("Tomato___Early_blight", "Category:Alternaria solani on tomato"),
]

downloaded = []
seen = set()
for cls, cat in CATS:
    params = {"action": "query", "format": "json", "generator": "categorymembers",
              "gcmtitle": cat, "gcmtype": "file", "gcmlimit": "25",
              "prop": "imageinfo", "iiprop": "url|size|mime", "iiurlwidth": "1024"}
    try:
        pages = api(params).get("query", {}).get("pages", {})
    except Exception as e:
        print(f"[{cls}] {cat} ERR {e}")
        continue
    got = 0
    for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
        t = p.get("title", "")
        ii = p.get("imageinfo", [{}])[0]
        mime = ii.get("mime", "")
        w, h = ii.get("width", 0), ii.get("height", 0)
        if mime not in ("image/jpeg", "image/png") or w < 500:
            continue
        if t in seen:
            continue
        seen.add(t)
        u = ii.get("thumburl") or ii.get("url")
        safe = t.replace("File:", "").replace("/", "_").replace(" ", "_")
        for ch in "()\",:'!":
            safe = safe.replace(ch, "")
        safe = safe[:90] + ".jpg"
        dest = OUT / safe
        if dest.exists():
            got += 1
            continue
        try:
            data = None
            for attempt in range(3):
                try:
                    data = urllib.request.urlopen(urllib.request.Request(u, headers=HDRS), timeout=30).read()
                    break
                except Exception:
                    import time
                    time.sleep(2)
            if data is None:
                raise RuntimeError("3 attempts failed")
            dest.write_bytes(data)
            downloaded.append({"title": t, "class": cls, "file": safe,
                               "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
            got += 1
            print(f"OK  [{cls}] {t[:75]}")
        except Exception as e:
            print(f"ERR {t[:60]}: {e}")
        if got >= 12:
            break
    print(f"--- {cat}: {got} files")

(OUT / "cat_manifest.json").write_text(json.dumps(downloaded, indent=1), encoding="utf-8")
print(f"\nTotal downloaded this run: {len(downloaded)}")
