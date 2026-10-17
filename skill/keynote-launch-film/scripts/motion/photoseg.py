"""照片段：慢推（Ken Burns）、加框照片 + 大数字、两排反向漂移的照片墙（视差）。逐帧边算边写。"""
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from stagecomp import encoder, OW, OH, FPS, ease

FONT_EN_L = r"C:\Windows\Fonts\segoeuil.ttf"
FONT_CN = r"C:\Windows\Fonts\Deng.ttf"
FONT_CN_L = r"C:\Windows\Fonts\Dengl.ttf"


def rd(p):
    im = cv2.imdecode(np.fromfile(str(p), np.uint8), 1)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def upscale(im, w):
    """低清照片放大：Lanczos + 轻微锐化"""
    h = int(round(im.shape[0] * w / im.shape[1]))
    big = cv2.resize(im, (w, h), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(big, (0, 0), 2.0)
    return cv2.addWeighted(big, 1.35, blur, -0.35, 0)


def grain(rng, amt=4.0):
    n = rng.normal(0, amt, (OH // 2, OW // 2)).astype(np.float32)
    return cv2.resize(n, (OW, OH), interpolation=cv2.INTER_LINEAR)[:, :, None]


def text_layer(items):
    """items: [(text, font, size, (x,y), gray, anchor)] → RGBA numpy"""
    L = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    for s, font, size, xy, gray, anchor in items:
        d.text(xy, s, font=ImageFont.truetype(font, size), fill=(gray, gray, gray, 255), anchor=anchor)
    return np.array(L)


def over(img, layer, alpha, dy=0):
    if alpha <= 0:
        return img
    lay = layer
    if dy:
        lay = np.roll(layer, int(round(dy)), axis=0)
    a = lay[:, :, 3:4].astype(np.float32) / 255 * alpha
    return (img.astype(np.float32) * (1 - a) + lay[:, :, :3].astype(np.float32) * a)


def framed(photo, dur, out, label=None, bg=11, box=(600, 160, 1820, 920), z=(1.0, 1.06), label_t=0.35, seed=1, label_size=170):
    """黑底，右边一张照片慢推，左下大数字（白色细字）"""
    im = rd(photo)
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    big = upscale(im, int(bw * z[1] * 1.15))
    rng = np.random.default_rng(seed)
    lay = text_layer([(label, FONT_EN_L, label_size, (110, y1 - 10), 245, "ls")]) if label else None
    n = int(round(dur * FPS)); enc = encoder(out)
    for i in range(n):
        t = i / FPS
        zz = z[0] + (z[1] - z[0]) * (t / dur)
        # 照片区域：按比例 cover 填满 box，再按 zz 放大，中心不动
        sc = max(bw / big.shape[1], bh / big.shape[0]) * zz
        M = np.float32([[sc, 0, x0 + bw / 2 - big.shape[1] * sc / 2], [0, sc, y0 + bh / 2 - big.shape[0] * sc / 2]])
        canvas = np.full((OH, OW, 3), bg, np.uint8)
        ph = cv2.warpAffine(big, M, (OW, OH), flags=cv2.INTER_AREA if sc < 1 else cv2.INTER_LINEAR, borderValue=(bg, bg, bg))
        canvas[y0:y1, x0:x1] = ph[y0:y1, x0:x1]
        f = canvas.astype(np.float32)
        if lay is not None:
            q = ease((t - label_t) / 0.7)
            f = over(f, lay, q, dy=(1 - q) * 18)
        f = f + grain(rng, 3.0)
        enc.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait(); print("framed", out)


def mosaic(photos, dur, out, rows=2, row_h=430, gap=22, bg=10, speed=70, seed=2):
    """两排照片反向慢慢漂移（视差），黑底；照片保持原色（这些本来就是黑白照）"""
    ims = [rd(p) for p in photos]
    strips = []
    per = int(np.ceil(len(ims) / rows))
    for r in range(rows):
        row = ims[r * per:(r + 1) * per]
        row = row + row[:2]  # 多拼两张，漂移时不露底
        tiles = []
        for im in row:
            w = int(round(im.shape[1] * row_h / im.shape[0]))
            tiles.append(upscale(im, w)[:row_h])
            tiles.append(np.full((row_h, gap, 3), bg, np.uint8))
        strips.append(np.hstack(tiles))
    total_h = rows * row_h + (rows - 1) * gap
    top = (OH - total_h) // 2
    rng = np.random.default_rng(seed)
    n = int(round(dur * FPS)); enc = encoder(out)
    for i in range(n):
        t = i / FPS
        canvas = np.full((OH, OW, 3), bg, np.float32)
        for r, s in enumerate(strips):
            dirn = -1 if r % 2 == 0 else 1
            start = 120 if dirn < 0 else (s.shape[1] - OW - 120)
            x = start - dirn * speed * t * (1.0 if r % 2 == 0 else 0.8)
            M = np.float32([[1, 0, -x], [0, 1, 0]])
            band = cv2.warpAffine(s, M, (OW, row_h), flags=cv2.INTER_LINEAR, borderValue=(bg, bg, bg))
            y = top + r * (row_h + gap)
            canvas[y:y + row_h] = band
        canvas = canvas + grain(rng, 3.5)
        enc.stdin.write(np.clip(canvas, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait(); print("mosaic", out)


def vintage_clip(src, ss, dur, crop, out, warm=0.06, grain_amt=7.0, seed=3, speed=1.0):
    """年代感片段：裁出 4:3 画面 → 放大到 1440x1080 居中黑边，稍暖、颗粒、暗角、轻微抖动和闪烁"""
    from stagecomp import frames_iter
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:1080, 0:1440].astype(np.float32)
    vig = 1 - 0.35 * (((xx - 720) / 720) ** 2 + ((yy - 540) / 540) ** 2) ** 1.2
    vig = np.clip(vig, 0.45, 1)[:, :, None]
    n = int(round(dur * FPS)); enc = encoder(out)
    src_frames = list(frames_iter(src, ss, dur * speed + 0.2, crop, 1440, 1080)) if speed != 1.0 else None
    it = None if src_frames else frames_iter(src, ss, dur, crop, 1440, 1080)
    for i in range(n):
        fr = src_frames[min(len(src_frames) - 1, int(i * speed))] if src_frames else next(it)
        f = fr.astype(np.float32)
        bl = cv2.GaussianBlur(f, (0, 0), 1.4); f = f + (f - bl) * 0.5
        f[:, :, 0] *= 1 + warm; f[:, :, 2] *= 1 - warm * 1.2
        f *= vig * (1 + rng.normal(0, 0.015))
        g = rng.normal(0, grain_amt, (540, 720)).astype(np.float32)
        f += cv2.resize(g, (1440, 1080))[:, :, None]
        dx, dy = rng.normal(0, 0.8, 2)
        f = cv2.warpAffine(np.clip(f, 0, 255), np.float32([[1, 0, dx], [0, 1, dy]]), (1440, 1080), borderMode=cv2.BORDER_REFLECT)
        canvas = np.zeros((OH, OW, 3), np.uint8)
        canvas[:, 240:1680] = np.clip(f, 0, 255).astype(np.uint8)
        enc.stdin.write(canvas.tobytes())
    enc.stdin.close(); enc.wait(); print("vintage", out)


def photo_sequence(photos, dur, out, bg=11, seed=4, layout=None, step=None):
    """德国研讨照片一张张错落滑入（拼贴逐步搭起来）：每张从不同方向滑进固定卡位，旧照片逐渐压暗；
    整体镜头慢推 + 轻微横移。layout: [(cx, cy, w, 方向)]，方向 in/left/right/up/down"""
    ims = [rd(p) for p in photos]
    rng = np.random.default_rng(seed)
    layout = layout or [(700, 420, 980, "in"), (1350, 610, 760, "right"), (500, 770, 700, "up"),
                        (1200, 300, 720, "down"), (820, 650, 800, "left"), (1460, 380, 740, "right"),
                        (600, 340, 760, "left"), (960, 560, 1080, "up")]
    N = min(len(ims), len(layout))
    step = step or (dur - 1.3) / max(1, N - 1)
    out_e = lambda u: 1 - (1 - min(1.0, max(0.0, u))) ** 3
    tiles = []
    for i in range(N):
        cx, cy, w, frm = layout[i]
        im = ims[i]
        tile = cv2.resize(im, (w, int(round(w * im.shape[0] / im.shape[1]))), interpolation=cv2.INTER_AREA)             if im.shape[1] >= w else upscale(im, w)
        tiles.append(dict(t=0.1 + i * step, cx=cx, cy=cy, img=tile, frm=frm))
    n = int(round(dur * FPS)); enc = encoder(out)
    for k in range(n):
        t = k / FPS
        z = 1.0 + 0.06 * ease(t / dur)
        px = -40 * ease(t / dur)
        canvas = np.full((OH, OW, 3), bg, np.float32)
        for i, L in enumerate(tiles):
            u = (t - L["t"]) / 0.75
            if u <= 0:
                continue
            q = out_e(u)
            dx = dy = 0.0; sc = 1.0
            if L["frm"] == "right": dx = (1 - q) * 700
            elif L["frm"] == "left": dx = -(1 - q) * 700
            elif L["frm"] == "up": dy = (1 - q) * 520
            elif L["frm"] == "down": dy = -(1 - q) * 520
            else: sc = 1.08 - 0.08 * q
            h, w = L["img"].shape[:2]
            zz = z * sc
            x = (L["cx"] + px - OW / 2) * z + OW / 2 + dx
            y = (L["cy"] - OH / 2) * z + OH / 2 + dy
            M = np.float32([[zz, 0, x - w * zz / 2], [0, zz, y - h * zz / 2]])
            ph = cv2.warpAffine(L["img"], M, (OW, OH), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0)).astype(np.float32)
            msk = cv2.warpAffine(np.ones((h, w), np.float32), M, (OW, OH), flags=cv2.INTER_LINEAR)[:, :, None]
            a = msk * min(1.0, q * 1.8)
            # 后面每来一张新照片，旧的就再暗一点，视线跟着新照片走
            newer = sum(1 for j in range(i + 1, N) if t > tiles[j]["t"])
            dim = max(0.5, 1 - 0.13 * newer)
            canvas = canvas * (1 - a) + ph * dim * a
        canvas = canvas + grain(rng, 3.0)
        enc.stdin.write(np.clip(canvas, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait(); print("sequence", out)


def photo_carousel(photos, dur, out, bg=11, w=1440, trans=0.5, dirs=("right", "left", "up", "right", "left"), seed=5):
    """一张一张呈现：每张大图居中慢推；下一张从不同方向滑入盖上来，上一张往反方向退一点并压暗（推拉 + 平移 + 错落）"""
    ims = [rd(p) for p in photos]
    N = len(ims)
    rng = np.random.default_rng(seed)
    seg = dur / N
    tiles = []
    for im in ims:
        wi = min(w, int(round(960 * im.shape[1] / im.shape[0])))     # 高度不超过 960，竖一点的照片窄一点
        h = int(round(wi * im.shape[0] / im.shape[1]))
        tiles.append(cv2.resize(im, (wi, h), interpolation=cv2.INTER_AREA) if im.shape[1] >= wi else upscale(im, wi)[:h])
    out_e = lambda u: 1 - (1 - min(1.0, max(0.0, u))) ** 3
    vec = {"right": (1, 0), "left": (-1, 0), "up": (0, 1), "down": (0, -1)}
    n = int(round(dur * FPS)); enc = encoder(out)
    for k in range(n):
        t = k / FPS
        canvas = np.full((OH, OW, 3), bg, np.float32)
        for i in range(N):
            t0 = i * seg - (trans if i else 0)          # 这一张开始滑入
            if t < t0:
                continue
            nxt = (i + 1) * seg - trans                   # 下一张开始滑入
            if i + 1 < N and t > nxt + trans + 0.05:
                continue                                   # 已经被下一张完全盖住
            q = 1.0 if i == 0 else out_e((t - t0) / trans)
            vx, vy = vec[dirs[i % len(dirs)]]
            dx, dy = (1 - q) * vx * 900, (1 - q) * vy * 640
            life = (t - max(0.0, t0)) / (seg + trans)
            z = 1.0 + 0.06 * life                          # 每张慢推
            dim = 1.0
            if i + 1 < N and t > nxt:                      # 被下一张盖上时往反方向退一点 + 压暗
                r = out_e((t - nxt) / trans)
                nvx, nvy = vec[dirs[(i + 1) % len(dirs)]]
                dx -= nvx * 160 * r; dy -= nvy * 110 * r; dim = 1 - 0.45 * r
            img = tiles[i]; h, ww = img.shape[:2]
            x, y = OW / 2 + dx, OH / 2 + dy
            M = np.float32([[z, 0, x - ww * z / 2], [0, z, y - h * z / 2]])
            ph = cv2.warpAffine(img, M, (OW, OH), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0)).astype(np.float32)
            msk = cv2.warpAffine(np.ones((h, ww), np.float32), M, (OW, OH), flags=cv2.INTER_LINEAR)[:, :, None]
            a = msk * (1.0 if i == 0 else min(1.0, q * 1.5))
            canvas = canvas * (1 - a) + ph * dim * a
        canvas = canvas + grain(rng, 3.0)
        enc.stdin.write(np.clip(canvas, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait(); print("carousel", out)
