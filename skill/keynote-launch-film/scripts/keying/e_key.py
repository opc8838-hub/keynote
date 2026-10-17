"""方案 E 通用版：真实视频逐帧换白底（人物像素不重画，不会变形/闪烁）。
  python e_key.py 原视频.mp4 输出.mp4 [--desk 0.95]
--desk：画面高度这个比例以下当桌子抹成白色（没有桌子就不写）。
HDR 自动换算；输出 1920x1080 白底，带原声。
"""
import subprocess
import sys

import cv2
import numpy as np
from rembg import new_session, remove
from PIL import Image

sys.path.insert(0, __file__.rsplit('\\', 1)[0] if '\\' in __file__ else '.')
import variants as V  # noqa: E402
from gs import FF, TM  # noqa: E402

W, H = 1920, 1080
src, dst = sys.argv[1], sys.argv[2]
desk = float(sys.argv[sys.argv.index('--desk') + 1]) if '--desk' in sys.argv else None

info = subprocess.run([FF, '-hide_banner', '-i', src], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
hdr = 'arib-std-b67' in info or 'smpte2084' in info
# 等比缩放铺满 1920x1080 再居中裁切
fit = 'scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,crop=1920:1080'
vf = (TM.replace('format=bgr24', 'format=gbrpf32le') + ',' if hdr else '') + fit + ',format=bgr24'

sess = new_session('isnet-general-use')
W_ = np.array([255, 255, 255], np.float32)


def frame(img):
    f = img.astype(np.float32)
    plate = V.clean_plate(f)
    a = V.plate_key(f, plate)
    aI = np.asarray(remove(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), session=sess, post_process_mask=False))[..., 3]
    aI = aI.astype(np.float32) / 255
    a = np.maximum(a, cv2.erode(aI, np.ones((9, 9), np.uint8)))
    out = V.replace_bg(f, a, plate)
    # 清孤立污渍：只保留和人/椅子连成一大块的区域，墙角阴影这类小块直接变白
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > 0.4).astype(np.uint8), 8)
    big = np.zeros(n, np.uint8)
    big[1:] = st[1:, cv2.CC_STAT_AREA] > 0.01 * H * W
    keep = cv2.dilate(big[lab], np.ones((31, 31), np.uint8)).astype(np.float32)
    keep = cv2.GaussianBlur(keep, (0, 0), 6)[..., None]
    out = out * keep + W_ * (1 - keep)
    if desk:
        y = int(H * desk)
        ramp = np.clip((np.arange(H) - (y - 6)) / 12, 0, 1)[:, None, None]
        out = out * (1 - ramp) + W_ * ramp
    return np.clip(out, 0, 255).astype(np.uint8)


rd = subprocess.Popen([FF, '-v', 'error', '-i', src, '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                      stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
fps = '30'
wr = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', fps, '-i', '-',
                       '-i', src, '-map', '0:v', '-map', '1:a?', '-vf', 'scale=out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int',
                       '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                       '-colorspace', 'bt709', '-c:a', 'aac', '-shortest', dst], stdin=subprocess.PIPE)
n = 0
while True:
    buf = rd.stdout.read(W * H * 3)
    if len(buf) < W * H * 3:
        break
    wr.stdin.write(frame(np.frombuffer(buf, np.uint8).reshape(H, W, 3)).tobytes())
    n += 1
wr.stdin.close()
wr.wait()
print('done', n, dst, flush=True)
