"""舞台镜头合成：解码一段素材（裁切/缩放到 1920x1080、30fps）→ 把大屏内容贴进白色大屏（透视 + 正片叠底）→ 特效 → 编码。
逐帧边读边写（倒放时临时帧落到磁盘），不把整段读进内存。
"""
import json, os, re, subprocess, tempfile
from pathlib import Path
import numpy as np
import cv2

FF = r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
OW, OH, FPS = 1920, 1080, 30
SCRATCH = Path(os.environ.get("STAGE_SCRATCH", tempfile.gettempdir())) / "stagecomp"
SCRATCH.mkdir(parents=True, exist_ok=True)
ENC_VF = "scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p"
ENC_TAIL = ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-colorspace", "bt709", "-color_primaries", "bt709",
            "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart"]


def src_size(src):
    info = subprocess.run([FF, "-hide_banner", "-i", str(src)], capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    return tuple(map(int, re.search(r"Video:.*?, (\d{3,5})x(\d{3,5})", info).groups()))


def ease(u):  # smoothstep 的柔一点版本
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _vf(crop, w, h, gray=False):
    vf = []
    if crop:
        x, y, cw, ch = crop
        vf.append(f"crop={cw}:{ch}:{x}:{y}")
    vf += [f"scale={w}:{h}:flags={'area' if gray else 'lanczos'}", f"fps={FPS}"]
    return ",".join(vf)


def frames_iter(src, ss, dur, crop=None, w=OW, h=OH, pix="rgb24"):
    """逐帧产出（边读边用，不占内存）；素材不够长就重复最后一帧"""
    n = int(round(dur * FPS))
    ch = 1 if pix == "gray" else 3
    p = subprocess.Popen([FF, "-loglevel", "quiet", "-ss", f"{ss:.4f}", "-i", str(src), "-t", f"{dur + 0.5:.4f}",
                          "-vf", _vf(crop, w, h, pix == "gray"), "-f", "rawvideo", "-pix_fmt", pix, "-"],
                         stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    fs = w * h * ch
    last = None
    for i in range(n):
        b = p.stdout.read(fs) if p else b""
        if len(b) == fs:
            last = np.frombuffer(b, np.uint8).reshape((h, w) if ch == 1 else (h, w, 3))
        elif p:
            p.stdout.close(); p.wait(); p = None
        yield last
    if p:
        p.kill(); p.wait()


def detect_quads(src, ss, dur, crop=None, thr=215, roi=None):
    """先单独解一遍小图（960x540 灰度）找大屏：最大的白色连通块 → 四角（输出像素），再稳健多项式拟合去抖"""
    sw, sh = 960, 540
    k = OW / sw
    raw = []
    for g in frames_iter(src, ss, dur, crop, sw, sh, "gray"):
        m = (g > thr).astype(np.uint8)
        if roi:
            x0, y0, x1, y1 = roi
            mm = np.zeros_like(m); mm[int(y0 * sh):int(y1 * sh), int(x0 * sw):int(x1 * sw)] = 1; m &= mm
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        ys, xs = np.nonzero(lab == i)
        pts = np.stack([xs, ys], 1).astype(np.float32) + 0.5
        s, d = pts[:, 0] + pts[:, 1], pts[:, 0] - pts[:, 1]
        q = [pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]]
        raw.append(np.array(q).reshape(8) * k)
    raw = np.array(raw)
    t = np.arange(len(raw))
    fit = np.zeros_like(raw)
    deg = min(4, max(1, len(raw) // 12))
    for j in range(8):
        keep = np.ones(len(t), bool)
        for _ in range(3):
            c = np.polyfit(t[keep], raw[keep, j], deg)
            r = raw[:, j] - np.polyval(c, t)
            keep = np.abs(r) < max(3.0, 2.5 * r[keep].std())
        fit[:, j] = np.polyval(c, t)
    return fit.reshape(-1, 4, 2)


def map_quad(q, src_wh, crop=None):
    """源像素四角 → 输出像素"""
    q = np.array(q, np.float32)
    if crop:
        x, y, w, h = crop
        q = (q - [x, y]) * [OW / w, OH / h]
    else:
        q = q * [OW / src_wh[0], OH / src_wh[1]]
    return q


def load_content(cdir):
    fs = sorted(Path(cdir).glob("*.png"))
    return fs


def composite(frame, content_png, quad, inset=0.0):
    c = cv2.imdecode(np.fromfile(str(content_png), np.uint8), cv2.IMREAD_COLOR)
    c = cv2.cvtColor(c, cv2.COLOR_BGR2RGB)
    h, w = c.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    q = np.float32(quad)
    if inset:
        ctr = q.mean(0); q = ctr + (q - ctr) * (1 - inset)
    P = cv2.getPerspectiveTransform(src, q)
    wc = cv2.warpPerspective(c, P, (OW, OH), flags=cv2.INTER_AREA if w > OW else cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return (frame.astype(np.uint16) * wc.astype(np.uint16) // 255).astype(np.uint8)


def apply_fx(img, t, fx):
    f = img.astype(np.float32)
    for e in fx:
        k = e["type"]
        if k == "towhite":
            u = ease((t - e["start"]) / (e["end"] - e["start"]))
            if u > 0:
                f = np.minimum(255, f * (1 + 2.5 * u))
                f = f + (255 - f) * (u ** 1.5)
        elif k == "fromwhite":
            u = 1 - ease((t - e["start"]) / (e["end"] - e["start"]))
            if u > 0:
                f = np.minimum(255, f * (1 + 2.5 * u))
                f = f + (255 - f) * (u ** 1.5)
        elif k == "bands":  # 一排排熄灭：[(y0, y1, 开始, 时长), ...]（输出像素）
            dark = np.zeros((OH, 1), np.float32)
            yy = np.arange(OH, dtype=np.float32)[:, None]
            for y0, y1, st, du in e["bands"]:
                u = ease((t - st) / du)
                if u <= 0:
                    continue
                band = np.clip(np.minimum(yy - y0 + 20, y1 - yy + 20) / 40.0, 0, 1)   # 相邻两排在交界处各 0.5，加起来正好 1
                dark += band * u
            mult = 1 - np.clip(dark, 0, 1) * (1 - e.get("floor", 0.0))
            f = f * mult[:, :, None] if f.ndim == 3 else f * mult
        elif k == "sharpen":   # 轻微锐化（掩盖放大糊）
            bl = cv2.GaussianBlur(f, (0, 0), e.get("sigma", 1.6))
            f = f + (f - bl) * e.get("amount", 0.6)
        elif k == "grain":     # 胶片颗粒（固定随机种子按帧变化）
            rng = np.random.default_rng(int(t * FPS) + 7)
            n = rng.normal(0, e.get("amt", 4.0), (OH // 2, OW // 2)).astype(np.float32)
            f = f + cv2.resize(n, (OW, OH), interpolation=cv2.INTER_LINEAR)[:, :, None]
        elif k == "zoom":      # 推镜：从 z0 推到 z1，以 (cx, cy)（比例坐标）为中心
            u = ease((t - e.get("start", 0)) / (e["end"] - e.get("start", 0)))
            z = e["z0"] + (e["z1"] - e["z0"]) * u
            cx, cy = e.get("cx", 0.5) * OW, e.get("cy", 0.5) * OH
            M = np.float32([[z, 0, cx - z * cx], [0, z, cy - z * cy]])
            f = cv2.warpAffine(f, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        elif k == "black":
            u = ease((t - e["start"]) / (e["end"] - e["start"]))
            f = f * (1 - u)
        elif k == "fadein_black":
            u = ease((t - e["start"]) / (e["end"] - e["start"]))
            f = f * u
    return np.clip(f, 0, 255).astype(np.uint8)


def encoder(out):
    return subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
                             "-r", str(FPS), "-i", "-", "-vf", ENC_VF] + ENC_TAIL + [str(out)], stdin=subprocess.PIPE)


def stage_segment(spec):
    """spec: src, ss, dur, out, [crop], [reverse], [freeze_at(秒,相对 ss)], [quad(源像素常量) | detect: {thr, roi}],
             [content: PNG 序列目录], [content_offset 帧], [inset], [fx: [...]], [src_dur]"""
    src = spec["src"]; dur = spec["dur"]; crop = spec.get("crop")
    sw, sh = src_size(src)
    src_dur = spec.get("src_dur", dur)
    n_src = int(round(src_dur * FPS))
    n = int(round(dur * FPS))
    quads = None
    if "detect" in spec:
        quads = detect_quads(src, spec["ss"], src_dur, crop, **spec["detect"])
    elif "quad" in spec:
        quads = np.repeat(map_quad(spec["quad"], (sw, sh), crop)[None], n_src, 0)
    content = load_content(spec["content"]) if spec.get("content") else None
    # 取帧顺序：正放 / 倒放 / 定格
    if "freeze_at" in spec:
        j0 = min(n_src - 1, int(round(spec["freeze_at"] * FPS)))
        fr = None
        for k, f in enumerate(frames_iter(src, spec["ss"], src_dur, crop)):
            if k == j0: fr = f.copy(); break
        order = [(j0, fr)] * n
        gen = iter(order)
    elif spec.get("reverse"):
        # 倒放：先把这段写成磁盘上的临时帧文件，再倒着读
        tmp = SCRATCH / f"rev_{Path(src).stem}_{spec['ss']:.2f}.u8"
        with open(tmp, "wb") as fh:
            for f in frames_iter(src, spec["ss"], src_dur, crop):
                fh.write(f.tobytes())
        fs = OW * OH * 3
        def rev():
            with open(tmp, "rb") as fh:
                for i in range(n):
                    j = max(0, n_src - 1 - i)
                    fh.seek(j * fs)
                    yield j, np.frombuffer(fh.read(fs), np.uint8).reshape(OH, OW, 3)
        gen = rev()
    else:
        gen = ((min(i, n_src - 1), f) for i, f in enumerate(frames_iter(src, spec["ss"], max(src_dur, dur), crop)))
    enc = encoder(spec["out"])
    for i in range(n):
        j, img = next(gen)
        img = np.array(img)
        if content is not None and quads is not None:
            ci = i + spec.get("content_offset", 0)
            if ci >= 0:
                img = composite(img, content[min(ci, len(content) - 1)], quads[min(j, len(quads) - 1)], spec.get("inset", 0.0))
        img = apply_fx(img, i / FPS, spec.get("fx", []))
        enc.stdin.write(img.tobytes())
    enc.stdin.close(); enc.wait()
    print("segment", spec["out"], f"{n / FPS:.2f}s")


def measure_lufs(path):
    r = subprocess.run([FF, "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    tail = r[r.rfind("Summary:"):]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1))


def fix_loudness(path, target=-16.0, tol=0.2):
    """实测整体响度，差多少补多少（只重编音频，画面直接拷贝）"""
    path = Path(path)
    for _ in range(3):
        cur = measure_lufs(path)
        print(f"loudness {path.name}: {cur:.1f} LUFS")
        if abs(cur - target) <= tol:
            return cur
        tmp = path.with_suffix(".tmp.mp4")
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(path), "-c:v", "copy",
                        "-af", f"volume={target - cur:.2f}dB,alimiter=limit=0.85:level=false", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(tmp)], check=True, stdin=subprocess.DEVNULL)
        os.replace(tmp, path)
    return measure_lufs(path)
