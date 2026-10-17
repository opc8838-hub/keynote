"""有光影的影棚背景：后墙渐变 + 产品身后光晕 + 暗角 + 地面光斑，推镜时背景视差（放大得比产品慢）。
  python backdrop.py out.jpg          # 预览
色调取自即梦第二幕前后镜头的浅灰影棚，接得上。
"""
import sys

import cv2
import numpy as np

W, H = 1920, 1080
WALL_TOP = np.array([243, 243, 243], np.float32)      # BGR，略带一点即梦影棚的冷紫灰
WALL_MID = np.array([252, 252, 252], np.float32)
FLOOR = np.array([247, 247, 247], np.float32)
HORIZON = 0.66                                         # 墙地交界（无缝过渡，没有硬线）


def make(zoom=1.0, cx=0.5, cy=0.56, shift=0.0):
    """zoom：背景自身的放大（推镜视差用，产品放大 1.06 时背景只放大约 1.02）。"""
    ys = (np.arange(H, dtype=np.float32) - H * cy) / zoom + H * cy
    xs = (np.arange(W, dtype=np.float32) - W * cx) / zoom + W * cx + shift * W
    X, Y = np.meshgrid(xs / W, ys / H)
    # 墙：上暗下亮；地面：远处亮、近处略暗；中间柔和过渡
    t_wall = np.clip(Y / HORIZON, 0, 1)[..., None]
    wall = WALL_TOP * (1 - t_wall ** 0.8) + WALL_MID * t_wall ** 0.8
    t_floor = np.clip((Y - HORIZON) / (1 - HORIZON), 0, 1)[..., None]
    floor = WALL_MID * (1 - t_floor) + FLOOR * t_floor
    blend = np.clip((Y - HORIZON + 0.06) / 0.12, 0, 1)[..., None]
    img = wall * (1 - blend) + floor * blend
    # 产品身后墙上的光晕
    glow = np.exp(-(((X - cx) / 0.32) ** 2 + ((Y - 0.42) / 0.30) ** 2))[..., None]
    img = img + glow * 6
    # 地面光斑（椭圆，产品脚下）
    pool = np.exp(-(((X - cx) / 0.36) ** 2 + ((Y - 0.80) / 0.10) ** 2))[..., None]
    img = img + pool * 4
    # 暗角
    vig = 1 - 0.08 * np.clip(((X - 0.5) / 0.75) ** 2 + ((Y - 0.5) / 0.85) ** 2, 0, 1)[..., None]
    img = img * vig
    # 极细的颗粒，避免大面积渐变出现色带
    rng = np.random.default_rng(7)
    img = img + rng.normal(0, 0.8, (H, W, 1)).astype(np.float32)
    return np.clip(img, 0, 255)


def reflection(prod_bgr, prod_a, floor_y, strength=0.10):
    """产品在地面的淡倒影：翻转、压扁、越往下越淡。返回 (倒影图, 倒影透明度)，坐标同画面。"""
    ys, xs = np.where(prod_a > 0.5)
    if len(ys) == 0:
        return None, None
    flip = prod_bgr[::-1]
    fa = prod_a[::-1]
    shift = 2 * floor_y - H
    M = np.float32([[1, 0, 0], [0, 0.55, floor_y - 0.55 * (H - floor_y) + (H - floor_y) * 0.0 - shift * 0.0]])
    rf = cv2.warpAffine(flip, M, (W, H))
    ra = cv2.warpAffine(fa, M, (W, H))
    fade = np.clip(1 - (np.arange(H, dtype=np.float32) - floor_y) / 160, 0, 1)[:, None]
    ra = cv2.GaussianBlur(ra, (0, 0), 3) * fade * strength
    return rf, ra


if __name__ == '__main__':
    cv2.imencode('.jpg', make().astype(np.uint8))[1].tofile(sys.argv[1])
