import re
import socket
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
_orig = socket.getaddrinfo
_cache = {}


def cached(host, *a, **k):
    key = (str(host), tuple(a), tuple(sorted(k.items())))
    if key not in _cache:
        _cache[key] = _orig(host, *a, **k)
    return _cache[key]


socket.getaddrinfo = cached
HDRS = {"User-Agent": "Mozilla/5.0"}

pages = {
    0: "https://tmpfiles.org/wYAg7Ft3sX2w/chunk0.bin",
    1: "https://tmpfiles.org/wUAg7StQ40iq/chunk1.bin",
    2: "https://tmpfiles.org/wRAn7Ftaqh82/chunk2.bin",
    3: "https://tmpfiles.org/wgAa7BtEE178/chunk3.bin",
    4: "https://tmpfiles.org/wRAR7ltxE5hD/chunk4.bin",
}
direct = {}
for i, u in pages.items():
    # try direct /dl/ form first
    dl = u.replace("tmpfiles.org/", "tmpfiles.org/dl/")
    try:
        r = urllib.request.urlopen(urllib.request.Request(dl, headers=HDRS), timeout=90)
        ctype = r.headers.get("Content-Type", "")
        head = r.read(4)
        if "text/html" not in ctype:
            direct[i] = dl
            print(f"chunk{i}: DIRECT works ({ctype}, head={head!r})")
            continue
        print(f"chunk{i}: /dl/ returns html, extracting...")
    except Exception as e:
        print(f"chunk{i}: /dl/ err {e}; extracting from page...")
    html = urllib.request.urlopen(urllib.request.Request(u, headers=HDRS), timeout=90).read().decode("utf-8", "replace")
    cands = re.findall(r'["\'(](/dl/[^"\')\s]+)', html)
    cands += re.findall(r'href="(https://tmpfiles\.org/dl/[^"]+)"', html)
    print(f"chunk{i} candidates: {cands[:5]}")
    if cands:
        c = cands[0]
        direct[i] = "https://tmpfiles.org" + c if c.startswith("/") else c

import json
from pathlib import Path
Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\colab_stage\tmpfiles_links.json").write_text(
    json.dumps(direct, indent=1))
print(json.dumps(direct, indent=1))
