"""Codex 额度用完后，剩下的零件层用代码从白底渲染图里切：产品轮廓（白底阈值）× 手画多边形。
Codex 已出的 L1/L2/L3 不动；本脚本输出 L4–L8 绿底 PNG（和 Codex 层同格式），被挡住的白床垫用修补补齐。
  python split_layers.py          # 输出层 + overlay 检查图
"""
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'src_exploded5.png')
LAY = os.path.join(ROOT, 'layers')
GREEN = np.array([0, 255, 0], np.uint8)

# 多边形（原图 1122x1402 坐标）
POLY = {
    'L5_床垫': [(165, 300), (272, 185), (330, 158), (470, 150), (560, 225), (590, 300), (600, 392), (760, 398), (800, 432),
               (1050, 445), (1055, 600), (752, 618), (560, 590), (410, 512), (330, 455), (170, 330)],
    'L4_前护栏': [(120, 395), (150, 385), (330, 425), (360, 440), (360, 560), (300, 575), (250, 720), (195, 715),
                 (190, 600), (125, 545)],
    'L6_床板骨架': [(95, 560), (380, 488), (450, 545), (690, 615), (905, 670), (905, 765), (860, 800), (860, 845),
                  (735, 845), (700, 850), (560, 850), (520, 770), (300, 775), (100, 780)],
    'L8_轮子': None,   # 下面按矩形
    'L7_底座': [(46, 793), (265, 715), (908, 788), (908, 1082), (766, 1168), (46, 888)],
}
BRACKETS = [(58, 705, 102, 782), (845, 822, 895, 895)]   # 悬空的小安装支架，跟底座走
WHEELS = [(25, 870, 110, 1005), (985, 1005, 1070, 1140), (760, 1140, 850, 1305)]


def poly_mask(shape, pts):
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [np.array(pts, np.int32)], 1)
    return m


def main():
    img = cv2.imdecode(np.fromfile(SRC, np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    # 产品轮廓：比白底暗一点就算；白床垫靠多边形补
    fg = (img.min(axis=2) < 246).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    # Codex 已经出的三层：先按原图校色（Codex 出来偏红），再从剩余里扣掉
    bak = os.path.join(LAY, '_codex_原始')
    os.makedirs(bak, exist_ok=True)
    taken = np.zeros((h, w), np.uint8)
    for n in ('L1_床头板', 'L2_床尾板', 'L3_后护栏'):
        bp = os.path.join(bak, n + '.png')
        if not os.path.exists(bp):
            cv2.imencode('.png', cv2.imdecode(np.fromfile(os.path.join(LAY, n + '.png'), np.uint8), 1))[1].tofile(bp)
        c = cv2.imdecode(np.fromfile(bp, np.uint8), cv2.IMREAD_COLOR)
        dd = c[..., 1].astype(int) - np.maximum(c[..., 0], c[..., 2]).astype(int)
        part = dd < 60
        same = part & (np.abs(c.astype(int) - img.astype(int)).mean(axis=2) < 30) & (img.min(axis=2) < 246)
        if same.sum() > 500:
            gain = img[same].reshape(-1, 3).mean(0) / np.maximum(c[same].reshape(-1, 3).mean(0), 1)
            c = np.where(part[..., None], np.clip(c * gain, 0, 255), c).astype(np.uint8)
            print(n, 'gain', np.round(gain, 3))
        cv2.imencode('.png', c)[1].tofile(os.path.join(LAY, n + '.png'))
        d = c[..., 1].astype(int) - np.maximum(c[..., 0], c[..., 2]).astype(int)
        taken |= (d < 60).astype(np.uint8)
    masks = {}
    mat = poly_mask(img.shape, POLY['L5_床垫'])
    # 床垫是白色的，用更严的阈值认出来，再把内部填实
    fi = img.astype(int)
    fabric_s = ((fi[..., 2] - fi[..., 0] > 6) & (img.max(axis=2) > 140) & (img.max(axis=2) < 222)).astype(np.uint8)
    fgm = (img.min(axis=2) < 250).astype(np.uint8) & mat & (1 - fabric_s)
    fgm = cv2.morphologyEx(fgm, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    ff = fgm.copy(); fmask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, fmask, (0, 0), 1)
    mat = fgm | (1 - ff)
    masks['L5_床垫'] = mat
    masks['L4_前护栏'] = poly_mask(img.shape, POLY['L4_前护栏']) & fg
    wheels = np.zeros((h, w), np.uint8)
    for x0, y0, x1, y1 in WHEELS:
        wheels[y0:y1, x0:x1] = 1
    wm = wheels & (img.min(axis=2) < 205).astype(np.uint8)                          # 只要轮子本体，阴影不要
    wm = cv2.morphologyEx(wm, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n_, lab_, st_, _ = cv2.connectedComponentsWithStats(wm, 8)
    masks['L8_轮子'] = np.isin(lab_, [k for k in range(1, n_) if st_[k, cv2.CC_STAT_AREA] > 40]).astype(np.uint8)
    base_poly = poly_mask(img.shape, POLY['L7_底座'])
    for x0, y0, x1, y1 in BRACKETS:
        base_poly[y0:y1, x0:x1] = 1
    f = img.astype(int)
    fabric = ((f[..., 2] - f[..., 0] > 4) & (img.max(axis=2) > 140)).astype(np.uint8)  # 暖灰布料（金属是中性偏冷）
    slat = poly_mask(img.shape, POLY['L6_床板骨架']) & fg & (1 - mat) & (1 - masks['L4_前护栏'])
    # 和底座重叠的地方，骨架只保留这几块：推杆、右侧横杆、左侧横杆（深色金属）
    keep = np.zeros((h, w), np.uint8)
    keep[740:850, 520:735] = 1
    keep[755:845, 735:860] = 1
    keep |= poly_mask(img.shape, [(96, 728), (300, 688), (320, 702), (320, 724), (112, 770), (96, 762)])
    metal = ((np.abs(fi[..., 2] - fi[..., 0]) <= 6) | (img.max(axis=2) < 120)).astype(np.uint8)   # 中性金属色或深色
    keep = keep & (metal | (img.max(axis=2) > 200).astype(np.uint8) * 0) & (1 - fabric)
    masks['L6_床板骨架'] = slat & (1 - (base_poly & (1 - keep)))
    used = taken | mat | masks['L4_前护栏'] | masks['L8_轮子'] | masks['L6_床板骨架']
    masks['L7_底座'] = fg & base_poly & (1 - used)
    # 底座被骨架、前护栏挡住的地方：补出来（零件飞走后不露白洞）
    bhole = base_poly & (masks['L6_床板骨架'] | masks['L4_前护栏']) & (1 - taken)
    base_img = cv2.inpaint(img, cv2.dilate(bhole, np.ones((3, 3), np.uint8)), 9, cv2.INPAINT_TELEA)
    masks['L7_底座'] = masks['L7_底座'] | bhole
    # 前护栏在床垫前面：床垫被挡住的部分用周围白色修补
    hole = (masks['L4_前护栏'] & mat).astype(np.uint8)
    mat_img = cv2.inpaint(img, cv2.dilate(hole, np.ones((5, 5), np.uint8)), 7, cv2.INPAINT_TELEA)
    # 别家品牌金字 → 压成枕套/毯垫的黑色
    hsv = cv2.cvtColor(mat_img, cv2.COLOR_BGR2HSV).astype(int)
    gold = ((hsv[..., 0] >= 8) & (hsv[..., 0] <= 35) & (hsv[..., 1] > 50) & (hsv[..., 2] > 60)).astype(np.uint8)
    dark = cv2.dilate((mat_img.max(axis=2) < 70).astype(np.uint8), np.ones((25, 25), np.uint8))
    gold = cv2.dilate(gold & dark, np.ones((3, 3), np.uint8))
    a = cv2.GaussianBlur(gold.astype(np.float32), (0, 0), 1.0)[..., None]
    mat_img = (mat_img * (1 - a) + np.array([24, 24, 26]) * a).astype(np.uint8)
    srcs = {'L5_床垫': mat_img, 'L7_底座': base_img}
    light = (img.min(axis=2) > 215).astype(np.uint8)          # 骨架、底座、轮子本身没有这么亮的颜色，是阴影/碎屑
    for n in ('L6_床板骨架', 'L8_轮子'):
        masks[n] = masks[n] & (1 - light)
    base_light = (base_img.min(axis=2) > 215).astype(np.uint8)
    masks['L7_底座'] = masks['L7_底座'] & (1 - base_light)
    for n in ('L6_床板骨架', 'L7_底座', 'L8_轮子'):
        k_, lab_, st_, _ = cv2.connectedComponentsWithStats(masks[n].astype(np.uint8), 8)
        masks[n] = np.isin(lab_, [k for k in range(1, k_) if st_[k, cv2.CC_STAT_AREA] > 60]).astype(np.uint8)
    for n, m in masks.items():
        m = m.astype(np.uint8)
        out = np.where(m[..., None] > 0, srcs.get(n, img), GREEN).astype(np.uint8)
        cv2.imencode('.png', out)[1].tofile(os.path.join(LAY, n + '.png'))
    # 检查图：每层一种颜色
    cols = {'L4_前护栏': (255, 0, 255), 'L5_床垫': (0, 200, 255), 'L6_床板骨架': (255, 120, 0), 'L7_底座': (0, 180, 0), 'L8_轮子': (0, 0, 255)}
    ov = img.copy().astype(np.float32)
    for n, c in cols.items():
        m = masks[n].astype(bool)
        ov[m] = ov[m] * 0.45 + np.array(c) * 0.55
    ov[taken.astype(bool)] = ov[taken.astype(bool)] * 0.45 + np.array((128, 128, 128)) * 0.55
    cv2.imencode('.jpg', ov.astype(np.uint8))[1].tofile(os.path.join(ROOT, 'split_overlay.jpg'))
    print('ok')


if __name__ == '__main__':
    main()
