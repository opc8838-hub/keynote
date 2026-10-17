"""逐帧找白色大屏四边形。用法：python screenquad.py <clip> <out.json> [scale_w=960] [thr=215] [roi=x0,y0,x1,y1 归一化]
输出每帧（源帧率）四角（原始分辨率像素）：TL TR BR BL。"""
import subprocess, sys, json, numpy as np, cv2, re
FF = r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
clip, out = sys.argv[1], sys.argv[2]
sw = int(sys.argv[3]) if len(sys.argv) > 3 else 960
thr = int(sys.argv[4]) if len(sys.argv) > 4 else 215
info = subprocess.run([FF, "-hide_banner", "-i", clip], capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
w, h = map(int, re.search(r", (\d{3,5})x(\d{3,5})", info).groups())
sh = int(round(h * sw / w / 2) * 2)
p = subprocess.Popen([FF, "-loglevel", "error", "-i", clip, "-vf", f"scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
quads = []
k = w / sw
while True:
    b = p.stdout.read(sw * sh)
    if len(b) < sw * sh: break
    g = np.frombuffer(b, np.uint8).reshape(sh, sw)
    m = (g > thr).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2: quads.append(None); continue
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    ys, xs = np.nonzero(lab == i)
    pts = np.stack([xs, ys], 1).astype(np.float32)
    s, d = pts[:, 0] + pts[:, 1], pts[:, 0] - pts[:, 1]
    q = [pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]]
    quads.append([[float(x * k), float(y * k)] for x, y in q])
json.dump({"w": w, "h": h, "quads": quads}, open(out, "w"))
print(len(quads), "frames", quads[0], quads[-1])
