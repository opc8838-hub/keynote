"""把 assets/patent_sample.jpg 里中间那张证书拉正，生成 p1..p6（+_blank 同图）。
v3：保持原色（红章、红国徽、蓝灰边框都是原色），只去反光、把纸面拉平成原项目那种米白；
    背景直接用原项目 seg5-motion 的蓝色渐变（天空蓝/深蓝 → 白）。"""
import cv2, numpy as np, shutil
from PIL import Image, ImageOps
from pathlib import Path
ROOT = Path(__file__).parent
SRC = ROOT.parents[2] / "assets" / "patent_sample.jpg"
im = ImageOps.exif_transpose(Image.open(SRC)).convert("RGB")
a = np.array(im)[:, :, ::-1]
S = a.shape[1] / 1500.0
# 印刷边框四角（在 1500 宽预览坐标里量的）
src = np.float32([[385, 362], [1207, 372], [1228, 1600], [322, 1590]]) * S
W, H = 1055, 1491
M = 52  # 边框到纸边留白
dst = np.float32([[M, M], [W - M, M], [W - M, H - M], [M, H - M]])
P = cv2.getPerspectiveTransform(src, dst)
out = cv2.warpPerspective(a, P, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
cv2.imencode('.png', out)[1].tofile(str(ROOT / 'assets' / 'rect_raw.png'))

# 去反光、拉平光照：用灰度的“纸面亮度”估计光照，三个通道一起除（颜色比例不变 → 红章还是红的）
f = out.astype(np.float32)
g = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).astype(np.float32)
bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
bg = cv2.GaussianBlur(bg, (0, 0), 25)
n = np.clip(f / np.maximum(bg, 1)[:, :, None], 0, 1.0)          # 纸面≈1
# 纸面原本偏冷灰（玻璃反光），先按纸面中位数做白平衡
paper_mask = (cv2.cvtColor((n * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY) > 225)
wb = np.median(n[paper_mask], axis=0)
n = np.clip(n / wb, 0, 1)
# 墨色加深一点；红色（章）饱和度稍微补回来（反光把它冲淡了），不改色相
hsv = cv2.cvtColor((n * 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
red = ((hsv[:, :, 0] < 12) | (hsv[:, :, 0] > 165)) & (hsv[:, :, 1] > 40)
hsv[:, :, 1] = np.where(red, np.clip(hsv[:, :, 1] * 1.35, 0, 255), hsv[:, :, 1])
n = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32) / 255
n = n ** 1.25
rng = np.random.default_rng(7)
# 原项目证书纸色 ≈ RGB(245,239,229)；6 张轻微变体
papers = [(245, 239, 229), (247, 242, 233), (244, 238, 226), (246, 240, 231), (243, 237, 227), (248, 243, 235)]
ink = np.array([34, 30, 28], np.float32)[::-1]      # BGR，接近黑的暖墨
for i in range(1, 7):
    pb = np.array(papers[i - 1], np.float32)[::-1]
    # 纸=paper，墨=ink；彩色部分按 n 的各通道比例保留
    v = ink + (pb - ink) * n
    ang = [0, 0.25, -0.2, 0.15, -0.3, 0.1][i - 1]
    R = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0 + 0.004 * (i % 3))
    v = cv2.warpAffine(v, R, (W, H), borderMode=cv2.BORDER_CONSTANT, borderValue=tuple(float(x) for x in pb))
    v = np.clip(v + rng.normal(0, 1.0, v.shape[:2])[:, :, None], 0, 255).astype(np.uint8)
    for suf in ("", "_blank"):
        cv2.imencode('.jpg', v, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(ROOT / 'assets' / f'p{i}{suf}.jpg'))
# 背景：原项目蓝色渐变原样
shutil.copyfile(ROOT.parents[3] / "seg5-motion" / "assets" / "wallbg.jpg", ROOT / "assets" / "wallbg.jpg")
print('certs ok (color)')
