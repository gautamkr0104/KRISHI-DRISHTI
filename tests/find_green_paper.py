"""Find a photo of flat green chart/construction paper on Commons."""
import json
import sys
import urllib.request
import urllib.parse
import socket
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
socket.setdefaulttimeout(40)
HDRS = {"User-Agent": "KRISHI-DRISHTI-external-validation/1.0 (educational project)"}
API = "https://commons.wikimedia.org/w/api.php"

def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=40).read().decode())

for q in ["green construction paper", "green chart paper", "green cardboard sheet", "green paper sheet plain"]:
    params = {"action": "query", "format": "json", "generator": "search",
              "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": "6", "gsrlimit": "8",
              "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "800"}
    try:
        pages = api(params).get("query", {}).get("pages", {})
        print(f"=== {q} ===")
        for p in sorted(pages.values(), key=lambda x: x.get("index", 99))[:8]:
            ii = p.get("imageinfo", [{}])[0]
            print(f"   {p.get('title')}  ({ii.get('width')}x{ii.get('height')})")
    except Exception as e:
        print(f"=== {q} === ERR {e}")
