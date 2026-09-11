#!/usr/bin/env python3
"""Convert PRTS WebM exports into transparent PNG frames for a deskpet."""

import argparse
import base64
import functools
import http.server
import json
import os
import shutil
import socketserver
import sys
import threading
import urllib.parse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright is required: run 'pip install playwright' first")

FPS = 20
SIZE = 1000
STATE_MAP = [
    ("Relax", "idle"),
    ("Interact", "interact"),
    ("Move", "move"),
    ("Sit", "sit"),
    ("Sleep", "sleep"),
]

HTML = """<!doctype html>
<html>
<body style="margin:0">
<video id="v" muted playsinline preload="auto"></video>
<canvas id="c"></canvas>
<script>
const SIZE = %d;
const v = document.getElementById('v');
const c = document.getElementById('c');
c.width = SIZE;
c.height = SIZE;
const ctx = c.getContext('2d');
async function capture(src) {
  v.src = src;
  if (v.readyState < 1) {
    await new Promise((res) => v.addEventListener('loadedmetadata', res, { once: true }));
  }
  const frames = [];
  let minX = SIZE, minY = SIZE, maxX = -1, maxY = -1;
  let done;
  const ended = new Promise((res) => { done = res; });
  v.addEventListener('ended', done, { once: true });
  function step(now, meta) {
    ctx.clearRect(0, 0, SIZE, SIZE);
    ctx.drawImage(v, 0, 0, SIZE, SIZE);
    const pixels = ctx.getImageData(0, 0, SIZE, SIZE);
    const data = pixels.data;
    // WebM alpha compression can leave nearly-transparent colored speckles.
    for (let i = 3; i < data.length; i += 4) {
      if (data[i] <= 10) data[i] = 0;
    }
    ctx.putImageData(pixels, 0, 0);
    for (let y = 0; y < SIZE; y += 2) {
      for (let x = 0; x < SIZE; x += 2) {
        const a = data[(y * SIZE + x) * 4 + 3];
        if (a > 10) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }
    frames.push({ t: meta.mediaTime, url: c.toDataURL('image/png') });
    if (!v.ended) v.requestVideoFrameCallback(step);
  }
  v.requestVideoFrameCallback(step);
  await v.play();
  await ended;
  return {
    duration: v.duration,
    frames,
    bbox: maxX >= 0 ? [minX, minY, maxX, maxY] : null
  };
}
window.capture = capture;
</script>
</body>
</html>
""" % SIZE


def find_chrome():
    candidates = [
        os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def pick_frames(count, duration, frames):
    max_t = max(0.01, duration - 0.02)
    out = []
    for i in range(count):
        target = (i / count) * max_t
        best = min(frames, key=lambda f: abs(f["t"] - target))
        out.append(best["url"])
    return out


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            data = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass


def run(src, name, out):
    pet_dir = out
    frames_dir = os.path.join(pet_dir, "frames")
    webm_dir = os.path.join(pet_dir, "webm")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(webm_dir, exist_ok=True)

    state_files = {}
    for fname in sorted(os.listdir(src)):
        if not fname.lower().endswith(".webm"):
            continue
        full = os.path.join(src, fname)
        if os.path.getsize(full) < 1000:
            print("skip broken webm:", fname)
            continue
        for token, state in STATE_MAP:
            if token.lower() in fname.lower():
                state_files[state] = fname
                break
    if not state_files:
        sys.exit("no valid WebM files found in " + src)

    for fname in state_files.values():
        shutil.copy2(os.path.join(src, fname), os.path.join(webm_dir, fname))

    with sync_playwright() as p:
        chrome = find_chrome()
        if chrome:
            browser = p.chromium.launch(executable_path=chrome, headless=True)
        else:
            browser = p.chromium.launch(headless=True)
        handler = functools.partial(Handler, directory=src)
        httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}/"
        manifest = {"fps": FPS, "size": SIZE, "states": {}}
        try:
            page = browser.new_page(
                viewport={"width": 900, "height": 900}
            )
            page.goto(base, wait_until="domcontentloaded")
            for state, fname in state_files.items():
                print("capturing", state, fname)
                src_url = "/" + urllib.parse.quote(fname)
                result = page.evaluate("(src) => window.capture(src)", src_url)
                duration = float(result["duration"])
                count = max(1, round(duration * FPS))
                urls = pick_frames(count, duration, result["frames"])
                state_dir = os.path.join(frames_dir, state)
                os.makedirs(state_dir, exist_ok=True)
                for i, url in enumerate(urls):
                    png = base64.b64decode(url.split(",", 1)[1])
                    with open(
                        os.path.join(state_dir, f"frame_{i:04d}.png"), "wb"
                    ) as f:
                        f.write(png)
                manifest["states"][state] = {
                    "duration": round(duration * 1000),
                    "count": len(urls),
                    "bbox": result["bbox"] or [0, 0, SIZE - 1, SIZE - 1],
                    "source": fname,
                }
                print("  wrote", len(urls), "frames")
        finally:
            httpd.shutdown()
            browser.close()

    with open(
        os.path.join(pet_dir, "manifest.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("manifest", json.dumps(manifest, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, help="directory with WebM files")
    parser.add_argument("--name", required=True, help="operator name")
    parser.add_argument("--out", required=True, help="pet directory to write")
    args = parser.parse_args()
    run(args.src, args.name, args.out)


if __name__ == "__main__":
    main()
