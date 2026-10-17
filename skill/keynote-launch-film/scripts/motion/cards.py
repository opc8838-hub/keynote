"""三张证书卡片：叠在一起 → 依次向左右展开（苹果式）。python cards.py [dur]  → work/O.mp4"""
import sys, numpy as np, cv2
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from stagecomp import encoder, OW, OH, FPS, ease
from photoseg import rd, grain

BOX = [(10, 18, 857, 632), (1134, 18, 1582, 632), (1688, 18, 2140, 632)]  # 医疗器械许可证, 专利1, 专利2
def ease_out(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 4

def make_cards():
    im = rd(HERE / "restore" / "hd" / "honor.png")
    cs = []
    for x0, y0, x1, y1 in BOX:
        c = im[y0:y1, x0:x1]
        cs.append(c)
    return cs

def render(dur, out, bg=11):
    cards = make_cards()
    H = 540; gap = 56
    sc = [H / c.shape[0] for c in cards]
    cards = [cv2.resize(c, (int(c.shape[1] * s), H), interpolation=cv2.INTER_AREA) for c, s in zip(cards, sc)]
    ws = [c.shape[1] for c in cards]
    tot = sum(ws) + 2 * gap
    while tot > 1740:
        H -= 10
        cards = make_cards(); cards = [cv2.resize(c, (int(c.shape[1] * H / c.shape[0]), H), interpolation=cv2.INTER_AREA) for c in cards]
        ws = [c.shape[1] for c in cards]; tot = sum(ws) + 2 * gap
    cx = OW / 2; cy = OH / 2 + 6
    left0 = cx - tot / 2
    final = [left0 + ws[0] / 2, left0 + ws[0] + gap + ws[1] / 2, left0 + ws[0] + ws[1] + 2 * gap + ws[2] / 2]
    # RGBA cards with soft shadow prebaked
    n = int(round(dur * FPS)); enc = encoder(out); rng = np.random.default_rng(1)
    start = [0.15, 0.1, 0.3]   # 左先、右后；中间不动
    T = 0.9                    # 单张展开时间
    for i in range(n):
        t = i / FPS
        canvas = np.full((OH, OW, 3), bg, np.float32)
        # 整体入场：叠在一起时轻微缩放 + 淡入
        fade = ease(t / 0.35)
        gscale = 0.96 + 0.04 * ease(t / 1.6)
        order = [0, 2, 1]  # 绘制顺序：中间在最上
        for k in order:
            p = ease_out((t - start[k]) / T)
            x = cx + (final[k] - cx) * p
            yaw = (1 - p) * (0.5 if k == 0 else -0.5) if k != 1 else 0
            s = gscale * (0.93 + 0.07 * p) if k != 1 else gscale
            w = ws[k]; h = H
            # 透视：靠外一侧略小（绕 y 轴转）
            sq = 1 - 0.0 * abs(yaw)
            hw = w / 2 * s * (1 - 0.35 * abs(yaw)); hh = h / 2 * s
            near = 1 + 0.10 * yaw; far = 1 - 0.10 * yaw
            dst = np.float32([[x - hw, cy - hh * near], [x + hw, cy - hh * far], [x + hw, cy + hh * far], [x - hw, cy + hh * near]])
            src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
            M = cv2.getPerspectiveTransform(src, dst)
            card = cv2.warpPerspective(cards[k], M, (OW, OH), flags=cv2.INTER_LINEAR, borderValue=0)
            mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), M, (OW, OH), flags=cv2.INTER_LINEAR)
            # 阴影
            sh = cv2.GaussianBlur(np.roll(mask, 22, axis=0), (0, 0), 26).astype(np.float32) / 255 * 0.65
            canvas *= (1 - sh[:, :, None])
            a = (mask.astype(np.float32) / 255)[:, :, None]
            canvas = canvas * (1 - a) + card.astype(np.float32) * a
        f = canvas * fade + bg * (1 - fade)
        f = f + grain(rng, 3.0)
        enc.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait(); print("cards", out)

if __name__ == "__main__":
    render(float(sys.argv[1]) if len(sys.argv) > 1 else 1.6, HERE / "work" / (sys.argv[2] if len(sys.argv) > 2 else "O.mp4"))
