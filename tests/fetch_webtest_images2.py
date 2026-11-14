"""Round 2: query specific Commons file titles, then download the best candidates."""
import json
import urllib.request
import urllib.parse
from pathlib import Path

OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\webtest")
OUT.mkdir(exist_ok=True)
HDRS = {"User-Agent": "KRISHI-DRISHTI-external-validation/1.0 (educational project)"}
API = "https://commons.wikimedia.org/w/api.php"

SEARCHES = {
    "tomato_early_blight": "Alternaria solani tomato leaf",
    "potato_early_blight": "Alternaria solani potato",
    "tomato_healthy": "Tomato leaf underside",
    "potato_healthy": "potato plant foliage field",
}

def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HDRS)
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())

for tag, q in SEARCHES.items():
    params = {"action": "query", "format": "json", "generator": "search",
              "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": "6", "gsrlimit": "8",
              "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "800"}
    data = api(params)
    pages = data.get("query", {}).get("pages", {})
    print(f"\n=== {tag} ===")
    for p in pages.values():
        ii = p.get("imageinfo", [{}])[0]
        print(f"  {p.get('title')}  ({ii.get('width')}x{ii.get('height')})")
