"""Upload chunks to tmpfiles.org, then resolve direct /dl/ links."""
import json
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
socket.setdefaulttimeout(300)
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OUT = Path(r"C:\Users\DELL\AppData\Local\Temp\opencode\colab_stage")

# cache DNS once (flappy resolver)
_orig = socket.getaddrinfo
_cache = {}
def cached(host, *a, **k):
    key = (str(host), tuple(a), tuple(sorted(k.items())))
    if key not in _cache:
        _cache[key] = _orig(host, *a, **k)
    return _cache[key]
socket.getaddrinfo = cached

links_file = OUT / "tmpfiles_links.json"
links = {}
if links_file.exists():
    links = {int(k): v for k, v in json.loads(links_file.read_text()).items() if k.isdigit()}
    print("resuming, already uploaded:", sorted(links))
for i in range(5):
    if i in links:
        print(f"skip chunk{i} (done)")
        continue
    p = OUT / f"chunk{i}.bin"
    ok = False
    for attempt in range(3):
        try:
            boundary = "----kd" + str(int(time.time() * 1000))
            body = b""
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="file"; filename="{p.name}"\r\n'.encode()
            body += b"Content-Type: application/octet-stream\r\n\r\n"
            body += p.read_bytes()
            body += f"\r\n--{boundary}--\r\n".encode()
            req = urllib.request.Request(
                "https://tmpfiles.org/api/v1/upload", data=body,
                headers={**HDRS, "Content-Type": f"multipart/form-data; boundary={boundary}"})
            resp = urllib.request.urlopen(req, timeout=280)
            r = json.loads(resp.read().decode())
            url = r["data"]["url"]  # https://tmpfiles.org/<id>/<name>
            links[i] = url
            print(f"OK chunk{i}: {url}")
            ok = True
            break
        except Exception as e:
            print(f"chunk{i} attempt {attempt}: {e}")
            time.sleep(10)
    if not ok:
        # persist progress and exit softly; rerun to resume
        links_file.write_text(json.dumps(links, indent=1))
        print(f"FAILED chunk{i} — rerun to resume")
        sys.exit(1)

links_file.write_text(json.dumps(links, indent=1))

# resolve direct download links (page -> /dl/<ts>.<token>/<id>/<name>)
direct = {}
for i, url in links.items():
    page_url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")  # try direct first
    try:
        req = urllib.request.Request(page_url, headers=HDRS, method="GET")
        r = urllib.request.urlopen(req, timeout=120)
        head = r.read(16)
        if head[:2] == b"\x1f\x8b" or head[:3] == b"PK\x03\x04" or head[:2] == b"BM" or True:
            ctype = r.headers.get("Content-Type", "")
            if "text/html" not in ctype:
                direct[i] = page_url
                print(f"direct chunk{i}: {page_url} ({ctype})")
                continue
        raise RuntimeError("html page")
    except Exception:
        # fetch HTML page, extract /dl/ link
        req = urllib.request.Request(url, headers=HDRS)
        html = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
        m = re.search(r'href="(/dl/[^"]+)"', html)
        if m:
            direct[i] = "https://tmpfiles.org" + m.group(1)
            print(f"resolved chunk{i}: {direct[i]}")
        else:
            print(f"NO DL LINK chunk{i}")
            sys.exit(1)

(OUT / "tmpfiles_links.json").write_text(json.dumps(direct, indent=1), encoding="utf-8")
print(json.dumps(direct, indent=1))
