"""绿幕 → 白底：绿色差值抠像 + 去溢色 + 抹掉桌子 → 换白色台面 → 裁切放大。

  python gs.py frame in.png out.png <cfg>          # 单帧测试
  python gs.py video in.mp4 out.mp4 <cfg> [--ss 0 --t 5]
cfg 见 CFG：desk = 桌子前沿线（原画面坐标，两点），crop = 放大倍数和人物中心
"""
import subprocess
import sys

import cv2
import numpy as np

FF = r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
# iPhone 素材是 HDR（HLG/杜比视界），不换算直接读会整片发白
TM = ("zscale=tin=arib-std-b67:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=100,format=gbrpf32le,"
      "zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=bgr24")

CFG = {
    # desk: 桌面远边（靠人那条边）两点；zoom: 放大倍数；cx/top: 裁切框的人物中心 x、框顶 y（原图坐标）
    'li': dict(desk=((440, 882), (1920, 957)), zoom=1.4, cx=930, place=0.62, top=240, xmax=1690),
    'zr': dict(desk=((330, 836), (1920, 893)), zoom=1.4, cx=900, place=0.62, top=140, xmax=1740),
}
W, H = 1920, 1080
BG = np.array([255, 255, 255], np.float32)
TABLE = np.array([246, 246, 246], np.float32)


def matte(img):
    f = img.astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    d = g - np.maximum(r, b)                      # 绿得多明显
    a = 1 - np.clip((d - 10) / (32 - 10), 0, 1)   # d<10 前景，d>32 背景
    a = cv2.GaussianBlur(a, (3, 3), 0)
    # 去溢色：前景边缘里的绿压到 r/b 的最大值
    g2 = np.minimum(g, np.maximum(r, b))
    f[..., 1] = np.where(d > 0, g2, g)
    return f, a


def desk_mask(cfg, shape):
    (x0, y0), (x1, y1) = cfg['desk']
    h, w = shape[:2]
    k = (y1 - y0) / (x1 - x0)
    pts = np.array([[0, y0 - k * x0], [w, y0 + k * (w - x0)], [w, h], [0, h]], np.int32)
    m = np.zeros((h, w), np.float32)
    cv2.fillPoly(m, [pts], 1.0)
    return cv2.GaussianBlur(m, (5, 5), 0), k, y0 - k * x0


def process(img, cfg):
    f, a = matte(img)
    dm, k, b0 = desk_mask(cfg, img.shape)
    a = a * (1 - dm)
    a[:, cfg['xmax']:] = 0                          # 右边木柜、灯架
    # 白色台面：桌子区域换成浅灰白，前沿一道细高光，人身上压一点接触阴影
    h, w = img.shape[:2]
    bg = np.empty_like(f)
    bg[:] = BG
    yy = np.arange(h)[:, None].astype(np.float32)
    xx = np.arange(w)[None, :].astype(np.float32)
    edge = b0 + k * xx
    table = np.clip((yy - edge) / 3, 0, 1)[..., None]
    grad = np.clip((yy - edge) / 400, 0, 1)[..., None]
    tcol = TABLE + (BG - TABLE) * grad * 0.6
    bg = bg * (1 - table) + tcol * table
    shadow = np.clip(1 - np.abs(yy - edge - 6) / 18, 0, 1) * 0.10
    bg = bg * (1 - shadow[..., None])
    out = f * a[..., None] + bg * (1 - a[..., None])
    out = np.clip(out, 0, 255).astype(np.uint8)
    # 裁切放大
    z = cfg['zoom']
    cw, ch = int(W / z), int(H / z)
    x0 = int(np.clip(cfg['cx'] - cfg['place'] * cw, 0, w - cw))
    y0 = int(np.clip(cfg['top'], 0, h - ch))
    crop = out[y0:y0 + ch, x0:x0 + cw]
    big = cv2.resize(crop, (W, H), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(big, (0, 0), 1.2)
    return cv2.addWeighted(big, 1.35, blur, -0.35, 0)   # 轻微锐化


def video(src, dst, cfg, ss=0, t=None):
    cmd = [FF, '-v', 'error', '-ss', str(ss)] + (['-t', str(t)] if t else []) + ['-i', src, '-vf', TM, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
    rd = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    wr = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', '30', '-i', '-',
                           '-ss', str(ss)] + (['-t', str(t)] if t else []) + ['-i', src, '-map', '0:v', '-map', '1:a?',
                           '-vf', 'scale=out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int', '-color_primaries', 'bt709',
                           '-color_trc', 'bt709', '-colorspace', 'bt709', '-c:v', 'libx264', '-crf', '14', '-preset', 'slow',
                           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', dst], stdin=subprocess.PIPE)
    n = 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        wr.stdin.write(process(img, cfg).tobytes())
        n += 1
        if n % 60 == 0:
            print(n, flush=True)
    wr.stdin.close()
    wr.wait()
    print('done', n, dst)


def opt(name, default):
    return float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


if __name__ == '__main__':
    mode, src, dst, name = sys.argv[1:5]
    cfg = CFG[name]
    if mode == 'frame':
        img = cv2.imdecode(np.fromfile(src, np.uint8), cv2.IMREAD_COLOR)
        cv2.imencode('.png', process(img, cfg))[1].tofile(dst)
    else:
        video(src, dst, cfg, opt('--ss', 0), opt('--t', None))
