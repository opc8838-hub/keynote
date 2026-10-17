"""把素材库里 iPhone HDR（HLG/杜比视界）视频统一转成 SDR bt709，输出到 lianying-launch\src_sdr，目录结构不变。
  python tools_sdr.py            # 全部（已转的跳过）
"""
import pathlib, subprocess, re
FF = r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
SRC = pathlib.Path(r"E:\连盈科技素材"); DST = pathlib.Path(r"E:\claude工作区\lianying-launch\src_sdr")
TM = ("zscale=tin=arib-std-b67:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=100,format=gbrpf32le,"
      "zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
for f in sorted(SRC.rglob("*.mp4")):
    info = subprocess.run([FF, "-hide_banner", "-i", str(f)], capture_output=True, text=True, encoding="utf-8", errors="ignore").stderr
    out = DST / f.relative_to(SRC)
    if out.exists():
        continue
    out.parent.mkdir(parents=True, exist_ok=True)
    hdr = "arib-std-b67" in info or "smpte2084" in info
    vf = TM if hdr else "format=yuv420p"
    print(("HDR " if hdr else "SDR ") + str(f.relative_to(SRC)), flush=True)
    subprocess.run([FF, "-v", "error", "-y", "-i", str(f), "-vf", vf, "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-colorspace", "bt709", "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-c:a", "copy", str(out) + ".tmp.mp4"],
                   stdin=subprocess.DEVNULL)
    pathlib.Path(str(out) + ".tmp.mp4").rename(out)
print("all done")
