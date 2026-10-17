import base64,subprocess,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).parent;FF=r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
out=ROOT/"spotlight_intro.mp4";fps=30;DUR=6.4;n=int(round(DUR*fps))
with sync_playwright() as p:
    b=p.chromium.launch(args=["--allow-file-access-from-files"])
    pg=b.new_page(viewport={"width":1920,"height":1080})
    pg.goto((ROOT/"index.html").resolve().as_uri());pg.wait_for_function("window.__ready===true")
    ff=subprocess.Popen([FF,"-y","-loglevel","error","-f","image2pipe","-framerate",str(fps),"-i","-",
     "-vf","scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p",
     "-c:v","libx264","-preset","slow","-crf","14","-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv","-movflags","+faststart",str(out)],stdin=subprocess.PIPE)
    for i in range(n):
        pg.evaluate(f"window.__render({i/fps})")
        u=pg.evaluate("document.getElementById('cv').toDataURL('image/png')")
        ff.stdin.write(base64.b64decode(u.split(",",1)[1]))
    ff.stdin.close();ff.wait();b.close()
print("done",n)
