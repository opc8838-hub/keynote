"""把任一预览页（canvas#cv + window.__render(t) + DUR）逐帧导出。
用法：python render_html.py <index.html> <输出.mp4> [帧率=30]
      python render_html.py <index.html> --stills 0,1.5,3 <输出目录>
      python render_html.py <index.html> --seq <输出目录> [帧率=30]   （PNG 序列，给合成脚本用）
      页面地址后可带 #参数（如 screen/index.html#act1open）
"""
import base64, subprocess, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

FFMPEG = r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
arg = sys.argv[1]
hash_ = ""
if "#" in arg: arg, hash_ = arg.split("#", 1)
html = Path(arg).resolve()
with sync_playwright() as p:
    browser = p.chromium.launch(args=["--allow-file-access-from-files"])
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    page.goto(html.as_uri() + (("#" + hash_) if hash_ else ""))
    page.wait_for_function("typeof DUR === 'number' && typeof window.__render === 'function' && window.__ready !== false")
    page.wait_for_timeout(800)
    grab = lambda: base64.b64decode(page.evaluate("document.getElementById('cv').toDataURL('image/png')").split(",", 1)[1])
    if sys.argv[2] == "--stills":
        od = Path(sys.argv[4]); od.mkdir(parents=True, exist_ok=True)
        for ts in sys.argv[3].split(","):
            page.evaluate(f"window.__render({float(ts)})")
            (od / f"{html.parent.name}{hash_.split(chr(58))[0]}_{float(ts):05.2f}.png").write_bytes(grab())
        browser.close(); sys.exit(0)
    if sys.argv[2] == "--seq":
        od = Path(sys.argv[3]); od.mkdir(parents=True, exist_ok=True)
        for old in od.glob("*.png"): old.unlink()
        fps = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        dur = page.evaluate("DUR"); n = int(round(dur * fps))
        for i in range(n):
            page.evaluate(f"window.__render({i / fps})")
            (od / f"{i:05d}.png").write_bytes(grab())
        browser.close(); print("seq", od, n); sys.exit(0)
    out = Path(sys.argv[2]); fps = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    dur = page.evaluate("DUR"); n = int(round(dur * fps))
    ff = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p",
        "-c:v", "libx264", "-threads", "2", "-filter_threads", "1", "-preset", "medium", "-crf", "15",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        page.evaluate(f"window.__render({i / fps})")
        ff.stdin.write(grab())
        if i % 60 == 0: print(f"{i}/{n}", flush=True)
    ff.stdin.close(); rc = ff.wait(); browser.close()
    if rc:
        raise RuntimeError(f"ffmpeg render failed with exit code {rc}")
print("done", out, f"{n} frames @ {fps}fps, {dur:.2f}s")
