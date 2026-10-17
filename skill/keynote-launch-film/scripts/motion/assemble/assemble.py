"""分层爆炸图 → 零件完整合拢成一张床（代码动画，学三星堆零件吸合，不切走）。
  python assemble.py still out.jpg t1 t2 ...    # 抽几帧检查
  python assemble.py preview out.mp4            # 单独预览
  python assemble.py endframe out.png           # 合拢完成那一帧（给“转身”首尾帧用）
  被 act2_fix.py import：render(t) 返回 1920x1080 BGR 帧（自带光影背景），t 为秒
零件层：layers/L1–L8（Codex 拆，绿底，已按原图校色）；终点：layers/ASM_装配完成.png（已对齐到爆炸图坐标）；
偏移：offsets.json（按两张图的角点量出来的）。
"""
import json
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import backdrop as BD  # noqa: E402

LAY = os.path.join(ROOT, 'layers')
FF = r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
W, H = 1920, 1080

# 画的先后（后面的盖住前面的）
ORDER = ['L3_后护栏', 'L1_床头板', 'L8_轮子', 'L7a_底座后部', 'L6_床板骨架', 'L7b_底座前脸', 'L5_床垫', 'L4_前护栏', 'L2_床尾板']
# 每个零件飞回来的起止时间（秒）：先骨架和轮子，再床垫、床头床尾，最后两块护栏
TIMING = {
    'L7a_底座后部': (0.0, 0.0), 'L7b_底座前脸': (0.0, 0.0), 'L8_轮子': (0.25, 1.35), 'L6_床板骨架': (0.30, 1.55), 'L5_床垫': (0.55, 1.90),
    'L1_床头板': (0.50, 1.85), 'L2_床尾板': (0.50, 1.80), 'L3_后护栏': (0.75, 2.10), 'L4_前护栏': (0.75, 2.10),
}
START = -0.25                   # 开场比爆炸图再多炸开 25%（爆炸图本身已经拉得很开）
LAND = 2.10                     # 最后一个零件落定
ASM_FADE = (99.0, 99.1)       # 不再换成装配图（两张图对不齐会“卡”一下），零件一路合到底         # 落定瞬间淡到完整床，盖掉零件叠放的细小误差
DUR = 3.40                      # 合拢段长度（之后接“转身”）
LS = 1.00                       # 零件图预缩（省内存；成片里床高约 1000px，原图 1402px 用不满）
PAD = int(420 * LS)
SCALE = H * 0.84 / (1402 * LS)        # 原图 → 画面的基础缩放
PUSH = 0.07                     # 全程推近幅度
PARALLAX = 0.35                 # 背景放大幅度 = 产品的 35%，看得出纵深
CENTER = (560 * LS, 900 * LS)            # 原图里合拢后床的大致中心，对准画面中心
OFF = json.load(open(os.path.join(ROOT, 'offsets.json'), encoding='utf-8'))


def green_key(img):
    f = img.astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    d = g - np.maximum(r, b)
    a = 1 - np.clip((d - 25) / 60, 0, 1)
    a = np.where(a < 0.15, 0, a)
    a = cv2.erode(a, np.ones((2, 2), np.uint8))          # 收掉 1px 绿边
    a = cv2.GaussianBlur(a, (0, 0), 0.8)
    f[..., 1] = np.where(d > 0, np.minimum(g, np.maximum(r, b)), g)
    return f, a


_D = None


def load():
    global _D
    if _D is None:
        rd = lambda p: cv2.resize(cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR), None, fx=LS, fy=LS, interpolation=cv2.INTER_AREA)
        layers = {n: green_key(rd(os.path.join(LAY, n + '.png'))) for n in ORDER}
        asm = rd(os.path.join(LAY, 'ASM_装配完成.png')).astype(np.float32)
        a_asm = np.clip((250 - asm.min(axis=2)) / 20, 0, 1)
        a_asm = cv2.GaussianBlur(a_asm, (3, 3), 0)
        _D = (layers, asm, a_asm)
    return _D


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def settle(x):
    """丝滑吸合：起步柔和、中段加速、末端长尾减速贴合（无过冲，不抖）。"""
    x = min(max(x, 0.0), 1.0)
    # 前段 ease-in（三次），后段长尾 ease-out（五次），在 0.4 处速度连续衔接
    s = 0.526
    if x < 0.4:
        return s * (x / 0.4) ** 3
    u = (x - 0.4) / 0.6
    return s + (1 - s) * (1 - (1 - u) ** 5)


def product(t):
    """原图坐标系（带留边）里的产品图和透明度。"""
    layers, asm, a_asm = load()
    h0, w0 = asm.shape[:2]
    H2, W2 = h0 + 2 * PAD, w0 + 2 * PAD
    canvas = np.zeros((H2, W2, 3), np.float32)
    alpha = np.zeros((H2, W2), np.float32)
    for n in ORDER:
        f, a = layers[n]
        t0, t1 = TIMING[n]
        dx, dy = [v * LS for v in OFF.get(n, [0, 0])[:2]]
        p = 1.0 if t1 <= t0 else START + (1 - START) * settle((t - t0) / (t1 - t0))
        M = np.float32([[1, 0, PAD + dx * p], [0, 1, PAD + dy * p]])
        fw = cv2.warpAffine(f, M, (W2, H2), flags=cv2.INTER_LINEAR)
        aw = cv2.warpAffine(a, M, (W2, H2), flags=cv2.INTER_LINEAR)[..., None]
        if n == 'L6_床板骨架':                      # 骨架落位后收进床垫和底座里（真床里看不到）
            aw = aw * (1 - ease_io((t - (t1 - 0.30)) / 0.40))
        if t1 > t0 and p < 0.995:                     # 飞行中的零件投下柔和阴影，落定后消失
            sh = cv2.GaussianBlur(np.roll(aw[..., 0], int(26 * (1 - p) + 6), axis=0), (0, 0), 14)[..., None] * 0.22 * (1 - p)
            canvas = canvas * (1 - sh)
        canvas = canvas * (1 - aw) + fw * aw
        alpha = alpha * (1 - aw[..., 0]) + aw[..., 0]
    # 落定后把零件之间被包围的缝补上（床垫/护栏之间露底的地方），用周围像素修补，不换图
    u = ease_io((t - (LAND - 0.2)) / 0.3)
    if u > 0:
        s = 4
        sa = cv2.resize(alpha, None, fx=1 / s, fy=1 / s, interpolation=cv2.INTER_AREA)
        solid = (sa > 0.5).astype(np.uint8)
        closed = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        ff = closed.copy(); m = np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8)
        cv2.floodFill(ff, m, (0, 0), 1)
        holes = (1 - ff) & (1 - solid)                      # 只补被床体包围的内部缝，外轮廓不动
        holes = cv2.dilate(holes, np.ones((2, 2), np.uint8))
        if holes.any():
            sc_ = cv2.resize(np.clip(canvas, 0, 255).astype(np.uint8), (sa.shape[1], sa.shape[0]), interpolation=cv2.INTER_AREA)
            fill = cv2.inpaint(sc_, holes, 5, cv2.INPAINT_TELEA)
            big = cv2.resize(fill, (canvas.shape[1], canvas.shape[0]), interpolation=cv2.INTER_CUBIC).astype(np.float32)
            hb = cv2.GaussianBlur(cv2.resize(holes.astype(np.float32), (canvas.shape[1], canvas.shape[0])), (0, 0), 2)[..., None] * u
            canvas = canvas * (1 - hb) + big * hb
            alpha = np.maximum(alpha, hb[..., 0])
    k = ease_io((t - ASM_FADE[0]) / (ASM_FADE[1] - ASM_FADE[0]))
    if k > 0:
        ac = np.zeros_like(canvas)
        aa = np.zeros_like(alpha)
        ac[PAD:PAD + h0, PAD:PAD + w0] = asm
        aa[PAD:PAD + h0, PAD:PAD + w0] = a_asm
        canvas = canvas * (1 - k) + ac * k
        alpha = alpha * (1 - k) + aa * k
    return canvas, alpha


ORBIT = (-7.0, 6.0)             # 镜头绕床的角度（度）：从左一点绕到右一点，全程一个连续弧线
BG_SLIDE = 0.10                 # 背景随镜头反向滑动（画面宽度比例 / 每 10°）


def orbit_angle(t):
    """合拢时镜头从左绕到右（-7°→+8°），合好后再缓缓绕回左边（→ -9°），像产品在转台上转了一下。"""
    return -7.0 + 13.0 * ease_io(t / DUR)          # 一个连续的绕拍弧线，产品只出现一次


def orbit_warp(img, a, deg, cx, cy, half_w):
    """2.5D 镜头绕拍：床绕竖轴转 deg 度的透视近似（近侧边变高、远侧边变矮、横向按 cos 压缩）。"""
    th = np.radians(deg)
    k = np.sin(th) * 0.20
    c = np.cos(th)
    src = np.float32([[cx - half_w, cy - half_w], [cx + half_w, cy - half_w], [cx + half_w, cy + half_w], [cx - half_w, cy + half_w]])
    lx, rx = cx - half_w * c, cx + half_w * c
    dst = np.float32([[lx, cy - half_w * (1 + k)], [rx, cy - half_w * (1 - k)], [rx, cy + half_w * (1 - k)], [lx, cy + half_w * (1 + k)]])
    M = cv2.getPerspectiveTransform(src, dst)
    return (cv2.warpPerspective(img, M, (W, H), flags=cv2.INTER_LINEAR),
            cv2.warpPerspective(a, M, (W, H), flags=cv2.INTER_LINEAR))


def compose(canvas, alpha, push, deg=0.0):
    """产品放进有光影的影棚：镜头绕拍、背景视差、接地阴影、地面倒影。"""
    sc = SCALE * push
    bg = BD.make(zoom=1 + (push - 1) * PARALLAX, shift=-deg / 10 * BG_SLIDE)
    nh, nw = int(canvas.shape[0] * sc), int(canvas.shape[1] * sc)
    cf = cv2.resize(canvas, (nw, nh), interpolation=cv2.INTER_AREA)
    ca = cv2.resize(alpha, (nw, nh), interpolation=cv2.INTER_AREA)
    x0 = int(W * 0.50 - (PAD + CENTER[0]) * sc)
    y0 = int(H * 0.60 - (PAD + CENTER[1]) * sc)
    full = np.zeros((H, W, 3), np.float32)
    fa = np.zeros((H, W), np.float32)
    sx0, sy0, dx0, dy0 = max(0, -x0), max(0, -y0), max(0, x0), max(0, y0)
    dx1, dy1 = min(W, x0 + nw), min(H, y0 + nh)
    full[dy0:dy1, dx0:dx1] = cf[sy0:sy0 + dy1 - dy0, sx0:sx0 + dx1 - dx0]
    fa[dy0:dy1, dx0:dx1] = ca[sy0:sy0 + dy1 - dy0, sx0:sx0 + dx1 - dx0]
    if abs(deg) > 0.01:
        full, fa = orbit_warp(full, fa, deg, W * 0.50, H * 0.60, 460 * push)
    # 接地阴影：产品最下沿往下压扁、模糊
    ys = np.where(fa.max(axis=1) > 0.5)[0]
    if len(ys):
        bottom = ys.max()
        band = (fa > 0.5).astype(np.float32)
        band[:max(0, bottom - int(60 * push))] = 0
        sh = cv2.GaussianBlur(cv2.dilate(band, np.ones((11, 71), np.uint8)), (0, 0), 26)
        bg = bg * (1 - np.clip(sh * 0.28, 0, 0.28)[..., None])
        # 淡倒影：只取产品下半部分翻转
        rf = full[::-1]
        ra = fa[::-1]
        shift = 2 * bottom - H + 6
        M = np.float32([[1, 0, 0], [0, 1, shift]])
        rf = cv2.warpAffine(rf, M, (W, H))
        ra = cv2.warpAffine(ra, M, (W, H))
        fade = np.clip(1 - (np.arange(H, dtype=np.float32) - bottom) / 140, 0, 1)[:, None] * (np.arange(H)[:, None] > bottom)
        ra = cv2.GaussianBlur(ra, (0, 0), 2.5) * fade * 0.07
        bg = bg * (1 - ra[..., None]) + rf * ra[..., None]
    return bg * (1 - fa[..., None]) + full * fa[..., None]


def push_at(t):
    # 开场拉远看清整个爆炸结构，随着合拢一路推近，合拢后继续缓慢推
    return 0.80 + 0.20 * ease_io(t / LAND) + PUSH * ease_io(max(0.0, t - LAND) / (DUR - LAND))


def render(t, plate=None, samples=1, shutter=1 / 60):
    """samples>1 时在快门时间内多采样平均（运动模糊，合拢更丝滑）。"""
    if samples <= 1 or t > LAND + 0.05:
        canvas, alpha = product(t)
        return compose(canvas, alpha, push_at(t), orbit_angle(t))
    acc = None
    for i in range(samples):
        ts = t - shutter * i / (samples - 1)
        canvas, alpha = product(max(ts, 0))
        f = compose(canvas, alpha, push_at(ts), orbit_angle(ts))
        acc = f if acc is None else acc + f
    return acc / samples


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'still':
        ts = [float(x) for x in sys.argv[3:]]
        tiles = [cv2.resize(np.clip(render(t), 0, 255).astype(np.uint8), (W // 2, H // 2)) for t in ts]
        while len(tiles) % 2:
            tiles.append(np.full_like(tiles[0], 255))
        cv2.imencode('.jpg', np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)]))[1].tofile(sys.argv[2])
    elif mode == 'endframe':
        cv2.imencode('.png', np.clip(render(DUR), 0, 255).astype(np.uint8))[1].tofile(sys.argv[2])
    elif mode == 'preview':
        fps = 30
        wr = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                               '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', sys.argv[2]], stdin=subprocess.PIPE)
        for i in range(int(DUR * fps)):
            wr.stdin.write(np.clip(render(i / fps), 0, 255).astype(np.uint8).tobytes())
        wr.stdin.close()
        wr.wait()
        print('done', sys.argv[2])
