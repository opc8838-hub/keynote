"""assets/logo.png → logo_k.png（深灰 + 透明底，去掉 JPEG 底色噪点）"""
import cv2, numpy as np
from pathlib import Path
a = cv2.imdecode(np.fromfile(str(Path(__file__).parents[3] / "assets" / "logo.png"), np.uint8), 1)
g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
ys, xs = np.nonzero(g < 128)
pad = 6
g = g[ys.min()-pad:ys.max()+pad, xs.min()-pad:xs.max()+pad].astype(np.float32)
alpha = np.clip((215 - g) / 150 * 255, 0, 255).astype(np.uint8)
rgba = np.dstack([np.full_like(alpha, 31), np.full_like(alpha, 29), np.full_like(alpha, 29), alpha])
cv2.imencode('.png', rgba)[1].tofile(str(Path(__file__).parent / "logo_k.png"))
print(g.shape)

# v3：结尾揭幕用的白色 logo（logo_w.png）和描边（logo_line.png）
al = rgba[:, :, 3]
cv2.imencode('.png', np.dstack([np.full_like(al, 255)] * 3 + [al]))[1].tofile(str(Path(__file__).parent / "logo_w.png"))
b = (al > 110).astype(np.uint8) * 255
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
edge = cv2.GaussianBlur(cv2.subtract(cv2.dilate(b, k), cv2.erode(b, k)), (0, 0), 0.8)
cv2.imencode('.png', np.dstack([np.full_like(al, 255)] * 3 + [edge]))[1].tofile(str(Path(__file__).parent / "logo_line.png"))
