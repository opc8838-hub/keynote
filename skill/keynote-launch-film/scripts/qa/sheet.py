"""交片前自查：每隔 N 秒抽一帧拼成总览图 + 测整体响度。
  python sheet.py 成片.mp4 总览.png [--every 0.5] [--cols 8]
看总览图逐格过 references/qa-checklist.md；响度应在 -16 LUFS 左右。
"""
import os
import re
import subprocess
import sys

FF = os.environ.get('KEYNOTE_FFMPEG', r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe")
src, out = sys.argv[1], sys.argv[2]
every = float(sys.argv[sys.argv.index('--every') + 1]) if '--every' in sys.argv else 0.5
cols = int(sys.argv[sys.argv.index('--cols') + 1]) if '--cols' in sys.argv else 8

info = subprocess.run([FF, '-hide_banner', '-i', src], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
h, m, s = re.search(r'Duration: (\d+):(\d+):([\d.]+)', info).groups()
dur = int(h) * 3600 + int(m) * 60 + float(s)
n = int(dur / every) + 1
rows = (n + cols - 1) // cols
vf = (rf"fps=1/{every},scale=320:-2,drawtext=fontfile='C\:/Windows/Fonts/Deng.ttf':text='%{{pts\:hms}}':"
      rf"x=6:y=6:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.5,tile={cols}x{rows}:padding=4:color=white")
subprocess.run([FF, '-v', 'error', '-y', '-i', src, '-vf', vf, '-frames:v', '1', out], stdin=subprocess.DEVNULL, check=True)
ln = subprocess.run([FF, '-hide_banner', '-i', src, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True,
                    encoding='utf-8', errors='ignore', stdin=subprocess.DEVNULL).stderr
I = re.findall(r'I:\s+(-?[\d.]+) LUFS', ln)
print(f'{dur:.1f}s  {n} 格 -> {out}  响度 {I[-1] if I else "?"} LUFS')
