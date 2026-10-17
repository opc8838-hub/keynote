"""设计师抠像多方案对比（单帧）。
  python variants.py in.png outdir [models...]
A 宽松色键 / B 净背景差值（clean plate）/ C、D AI 抠人 / E = B 的发丝 + AI 的实心身体
"""
import os
import sys

import cv2
import numpy as np

from gs import CFG, desk_mask

W_ = np.array([255, 255, 255], np.float32)


def chroma(f, lo, hi):
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    d = g - np.maximum(r, b)
    return 1 - np.clip((d - lo) / (hi - lo), 0, 1)


def clean_plate(f):
    """估一张“没人的绿幕”：确定是背景的像素保留，人所在的洞用小图修补后放大填回。"""
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    d = g - np.maximum(r, b)
    sure = (d > 45).astype(np.uint8)
    sure = cv2.erode(sure, np.ones((15, 15), np.uint8))
    h, w = sure.shape
    s = 8
    small = cv2.resize(f, (w // s, h // s), interpolation=cv2.INTER_AREA)
    ms = cv2.resize(sure, (w // s, h // s), interpolation=cv2.INTER_NEAREST)
    hole = (1 - ms).astype(np.uint8)
    fill = cv2.inpaint(np.clip(small, 0, 255).astype(np.uint8), hole, 12, cv2.INPAINT_TELEA).astype(np.float32)
    fill = cv2.GaussianBlur(fill, (0, 0), 3)
    big = cv2.resize(fill, (w, h), interpolation=cv2.INTER_CUBIC)
    m = cv2.GaussianBlur(sure.astype(np.float32), (0, 0), 4)[..., None]
    return f * m + big * (1 - m)


def plate_key(f, plate, lo=0.08, hi=0.85):
    d = f[..., 1] - np.maximum(f[..., 0], f[..., 2])
    dB = np.maximum(plate[..., 1] - np.maximum(plate[..., 0], plate[..., 2]), 8)
    a = 1 - np.clip(d / dB, 0, 1)                 # 相对这块绿幕本身的绿，阴影里的发丝也算得准
    return np.clip((a - lo) / (hi - lo), 0, 1)


def replace_bg(f, a, plate):
    """把原像素里混进去的那份绿幕换成白：out = p + (1-a)(白 - 绿幕)。发丝的半透明保留下来。"""
    out = f + (1 - a[..., None]) * (W_ - plate)
    b, g, r = out[..., 0], out[..., 1], out[..., 2]
    out[..., 1] = np.minimum(g, np.maximum(r, b))   # 残余溢色
    return neutral_dark(np.clip(out, 0, 255))


def neutral_dark(out):
    """椅背网格、黑衣服这类暗部透出来的青绿色压成中性灰（肤色亮，不受影响）。"""
    lum = out.mean(axis=2, keepdims=True)
    k = np.clip((90 - lum) / 50, 0, 1) * 0.85
    return out * (1 - k) + lum * k


def simple_comp(f, a):
    f = f.copy()
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    f[..., 1] = np.minimum(g, np.maximum(r, b))
    return np.clip(f * a[..., None] + W_ * (1 - a[..., None]), 0, 255)


def ai_alpha(img, model):
    from rembg import new_session, remove
    from PIL import Image
    s = new_session(model)
    rgba = remove(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), session=s, post_process_mask=False)
    return np.asarray(rgba)[..., 3].astype(np.float32) / 255


def finish(out, cfg):
    dm, k, b0 = desk_mask(cfg, out.shape)
    out = out * (1 - dm[..., None]) + W_ * dm[..., None]
    out[:, cfg['xmax']:] = 255
    return out.astype(np.uint8)


if __name__ == '__main__':
    src, od = sys.argv[1], sys.argv[2]
    models = sys.argv[3:]
    os.makedirs(od, exist_ok=True)
    cfg = CFG['designer']
    img = cv2.imdecode(np.fromfile(src, np.uint8), cv2.IMREAD_COLOR)
    f = img.astype(np.float32)
    plate = clean_plate(f)
    cv2.imencode('.jpg', plate.astype(np.uint8))[1].tofile(os.path.join(od, 'plate.jpg'))
    res = {}
    res['A_宽松色键'] = simple_comp(f, chroma(f, 20, 60))
    aB = plate_key(f, plate)
    res['B_净背景差值'] = replace_bg(f, aB, plate)
    res['B2_净背景_收紧'] = replace_bg(f, plate_key(f, plate, 0.15, 0.75), plate)
    res['B3_净背景_放松'] = replace_bg(f, plate_key(f, plate, 0.03, 0.92), plate)
    for m in models:
        aI = ai_alpha(img, m)
        res['C_AI_' + m] = simple_comp(f, aI)
        solid = cv2.erode(aI, np.ones((9, 9), np.uint8))       # AI 的实心身体（往里收一圈）
        aE = np.maximum(aB, solid)
        res['E_发丝B+身体AI_' + m] = replace_bg(f, aE, plate)
    tiles = []
    for name, out in res.items():
        o = finish(out, cfg)
        cv2.imencode('.png', o)[1].tofile(os.path.join(od, name + '.png'))
        crop = cv2.resize(o[360:640, 780:1140], (540, 420), interpolation=cv2.INTER_CUBIC)
        cv2.putText(crop, name.split('_')[0], (10, 40), 0, 1.2, (0, 0, 255), 3)
        tiles.append(crop)
    orig = cv2.resize(img[360:640, 780:1140], (540, 420), interpolation=cv2.INTER_CUBIC)
    tiles.insert(0, orig)
    while len(tiles) % 3:
        tiles.append(np.full_like(tiles[0], 255))
    rows = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]
    cv2.imencode('.jpg', np.vstack(rows))[1].tofile(os.path.join(od, '对比_头发.jpg'))
    print('\n'.join(res))
