"""1. Codex 新出的 L4–L8 替换手切层（手切的备份到 layers/_manual），全部按原图校色
2. 装配完成图对齐到爆炸图坐标：只比底座前脸（两张图都看得见），搜缩放+平移
3. 每个零件在对齐后的装配图里搜终点位置 → offsets.json
"""
import json
import os
import shutil

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
LAY = os.path.join(ROOT, 'layers')
CX = os.path.join(ROOT, 'layers_codex')
SRC = cv2.imdecode(np.fromfile(os.path.join(ROOT, 'src_exploded5.png'), np.uint8), cv2.IMREAD_COLOR)
H0, W0 = SRC.shape[:2]


def part_mask(img):
    d = img[..., 1].astype(int) - np.maximum(img[..., 0], img[..., 2]).astype(int)
    return d < 60


def color_fix(img):
    m = part_mask(img)
    same = m & (np.abs(img.astype(int) - SRC.astype(int)).mean(axis=2) < 30) & (SRC.min(axis=2) < 246)
    if same.sum() < 500:
        return img, None
    gain = SRC[same].reshape(-1, 3).mean(0) / np.maximum(img[same].reshape(-1, 3).mean(0), 1)
    return np.where(m[..., None], np.clip(img * gain, 0, 255), img).astype(np.uint8), gain


def ncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))


def main():
    os.makedirs(os.path.join(LAY, '_manual'), exist_ok=True)
    for n in ('L4_前护栏', 'L5_床垫', 'L6_床板骨架', 'L7_底座', 'L8_轮子'):
        mp = os.path.join(LAY, '_manual', n + '.png')
        if not os.path.exists(mp) and os.path.exists(os.path.join(LAY, n + '.png')):
            shutil.copy(os.path.join(LAY, n + '.png'), mp)
        img = cv2.imdecode(np.fromfile(os.path.join(CX, n + '.png'), np.uint8), cv2.IMREAD_COLOR)
        img, g = color_fix(img)
        print(n, 'gain', None if g is None else np.round(g, 3))
        cv2.imencode('.png', img)[1].tofile(os.path.join(LAY, n + '.png'))

    asm = cv2.imdecode(np.fromfile(os.path.join(CX, 'ASM_装配完成.png'), np.uint8), cv2.IMREAD_COLOR)
    asm = cv2.resize(asm, (W0, H0), interpolation=cv2.INTER_AREA)
    asm, g = color_fix(np.where((asm.min(axis=2) > 246)[..., None], np.array([0, 255, 0], np.uint8), asm))
    asm = np.where(part_mask(asm)[..., None], asm, 255).astype(np.uint8)
    print('ASM gain', None if g is None else np.round(g, 3))

    # 底座前脸：底座层里偏下的那部分（顶面会被床垫盖住，不能拿来比）
    base = cv2.imdecode(np.fromfile(os.path.join(LAY, 'L7_底座.png'), np.uint8), cv2.IMREAD_COLOR)
    bm = part_mask(base)
    ys, xs = np.where(bm)
    front = bm & (np.arange(H0)[:, None] > ys.min() + (ys.max() - ys.min()) * 0.45)
    s = 3
    bg = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY).astype(np.float32)[::s, ::s]
    fm = front[::s, ::s]
    ag_full = cv2.cvtColor(asm, cv2.COLOR_BGR2GRAY).astype(np.float32)
    best = (-9, None)
    for sc in np.arange(0.70, 1.10, 0.02):
        for tx in range(-120, 121, 6):
            for ty in range(-120, 121, 6):
                M = np.float32([[sc, 0, tx + (1 - sc) * W0 / 2], [0, sc, ty + (1 - sc) * H0 / 2]])
                # 把装配图按 M 的逆变换取到爆炸图坐标
                aw = cv2.warpAffine(ag_full, M, (W0, H0), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=255)[::s, ::s]
                v = ncc(bg[fm], aw[fm])
                if v > best[0]:
                    best = (v, (float(sc), tx, ty))
    sc, tx, ty = best[1]
    print('ASM align scale %.2f tx %d ty %d  score %.3f' % (sc, tx, ty, best[0]))
    M = np.float32([[sc, 0, tx + (1 - sc) * W0 / 2], [0, sc, ty + (1 - sc) * H0 / 2]])
    asm_al = cv2.warpAffine(asm, M, (W0, H0), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=(255, 255, 255))
    cv2.imencode('.png', asm_al)[1].tofile(os.path.join(LAY, 'ASM_装配完成.png'))

    # 每个零件搜终点（只比零件本身像素；零件在装配图里会被别的零件挡住一部分，所以只要大致对上）
    ag = cv2.cvtColor(asm_al, cv2.COLOR_BGR2GRAY).astype(np.float32)
    off = {'L7_底座': [0, 0, 1.0]}
    rng = {'L8_轮子': (-80, 40, -30, 30), 'L6_床板骨架': (-20, 260, -60, 60), 'L5_床垫': (0, 380, -80, 80),
           'L1_床头板': (-40, 420, -60, 160), 'L2_床尾板': (-80, 160, -120, 60), 'L3_后护栏': (0, 380, -160, 80),
           'L4_前护栏': (0, 420, -60, 220)}
    s = 4
    for n, (y0, y1, x0, x1) in rng.items():
        img = cv2.imdecode(np.fromfile(os.path.join(LAY, n + '.png'), np.uint8), cv2.IMREAD_COLOR)
        m = part_mask(img)
        g_ = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gs, ms, as_ = g_[::s, ::s], m[::s, ::s], ag[::s, ::s]
        hh, ww = gs.shape
        best = (-9, [0, 0])
        for dy in range(y0 // s, y1 // s + 1):
            for dx in range(x0 // s, x1 // s + 1):
                ys0, ys1 = max(0, -dy), min(hh, hh - dy)
                xs0, xs1 = max(0, -dx), min(ww, ww - dx)
                mm = ms[ys0:ys1, xs0:xs1]
                if mm.sum() < 40:
                    continue
                v = ncc(gs[ys0:ys1, xs0:xs1][mm], as_[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx][mm])
                if v > best[0]:
                    best = (v, [dx * s, dy * s])
        off[n] = best[1] + [round(best[0], 3)]
        print(n, 'offset', best[1], 'score %.3f' % best[0])
    json.dump(off, open(os.path.join(ROOT, 'offsets.json'), 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
