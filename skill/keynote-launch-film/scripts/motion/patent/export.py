"""把预览页逐帧渲染成 MP4。
用法：python export.py <输出.mp4> [帧率]
"""
import base64
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
FFMPEG = r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
out = Path(sys.argv[1])
fps = int(sys.argv[2]) if len(sys.argv) > 2 else 60

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--allow-file-access-from-files"])
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    page.goto((ROOT / "index.html").resolve().as_uri())
    page.wait_for_function("typeof DUR === 'number' && typeof window.__render === 'function'")
    page.wait_for_timeout(800)
    dur = page.evaluate("DUR")
    n = int(round(dur * fps))
    # 白底防发黄：accurate_rnd + full_chroma_int，并标 bt709
    ff = subprocess.Popen([
        FFMPEG, "-y", "-loglevel", "error",
        "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "14",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)
    for i in range(n):
        page.evaluate(f"window.__render({i / fps})")
        url = page.evaluate("document.getElementById('cv').toDataURL('image/png')")
        ff.stdin.write(base64.b64decode(url.split(",", 1)[1]))
        if i % 120 == 0:
            print(f"{i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    browser.close()
print("done", out, f"{n} frames @ {fps}fps")
