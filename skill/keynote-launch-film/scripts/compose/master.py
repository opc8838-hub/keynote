r"""最终合成：五幕拼接 + 中英字幕 + 混音 → 成片。
  python master.py [--music 音乐.wav] [--out 输出.mp4] [--check t1 t2 ...]
依赖：sections\ACT1/3/4/5.mp4 + ACTn_lines.json（助手交付）、act2\第二幕_正式版_1080p.mp4（主线程）。
第二幕自身不带张总配音：这里把 zhang 06（产品介绍）、07（交棒）放进去，07 之后接 S2 张总指大屏 → 大屏白光 → 第三幕。
字幕：苹果式，中文在上、英文在下，按背景亮度自动选深灰/白，无描边无底框，0.15s 淡入淡出。
"""
import json
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = r"E:\claude工作区\lianying-launch"
FF = r"E:\claude工作区\back-to-work-video\tools\ffmpeg.exe"
W, H, FPS = 1920, 1080, 30
WORK = os.path.join(ROOT, 'final', 'work')
os.makedirs(WORK, exist_ok=True)
SUBS = json.load(open(os.path.join(ROOT, 'final', 'subs.json'), encoding='utf-8'))
F_CN = ImageFont.truetype(r"C:\Windows\Fonts\Deng.ttf", 40)
F_EN = ImageFont.truetype(r"C:\Windows\Fonts\segoeuil.ttf", 25)
DARK, LIGHT = (61, 59, 62), (246, 245, 243)

ACT2_SRC = os.path.join(ROOT, 'act2', '第二幕_正式版_1080p.mp4')
ACT2_VOICE = [(6, 5.30), (7, None)]          # (句号, 在第二幕里的开始秒)；7 号接在片尾标题上，自动算
S2_CLIP = os.path.join(ROOT, 'clips', 'S2_new_1080.mp4')     # 用户新做的清晰版（已裁掉 MiniMax 水印）
S2_QUAD = [[116, 107], [1893, 107], [1947, 902], [60, 904]]
XF = 0.5                                                      # 第二幕片尾 → 张总交棒的淡入淡出


def dur(p):
    info = subprocess.run([FF, '-hide_banner', '-i', p], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    import re
    h, m, s = re.search(r'Duration: (\d+):(\d+):([\d.]+)', info).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def run(cmd):
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if r.returncode:
        print(r.stderr[-2000:])
        sys.exit(1)


ENC = ['-vf', 'scale=out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int', '-c:v', 'libx264', '-crf', '16', '-preset', 'medium',
       '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']


def build_act2():
    """第二幕 + 张总 06/07 配音 + S2 交棒镜头（大屏渐白），统一成 30fps，音轨只有配音。"""
    out = os.path.join(WORK, 'ACT2_full.mp4')
    sp = os.path.join(ROOT, 'spotlight', 'spotlight_intro.mp4')       # 开灯揭幕（灯照出床的轮廓 → 全屏亮 → 接发布片第一帧）
    shift = dur(sp) if os.path.exists(sp) else 0.0
    d2 = dur(ACT2_SRC) + shift
    v6, v7 = [os.path.join(ROOT, 'voice', 'v3', 'zhang', '%02d.mp3' % n) for n in (6, 7)]
    ACT2_VOICE[0] = (6, 5.30 + shift)
    t7 = d2 - 0.9                                    # 07 在片尾标题最后不到 1 秒开口，然后淡到张总
    s2_len = max(2.5, t7 + dur(v7) + 0.5 - d2 + XF)
    # S2：张总指向大屏，最后 0.6 秒大屏白光漫开到全白（接第三幕）
    s2 = os.path.join(WORK, 'S2_handoff.mp4')
    s2raw = os.path.join(WORK, 'S2_screen.mp4')
    scr = os.path.join(WORK, 'scr_ly600')
    os.makedirs(scr, exist_ok=True)
    make_screen(os.path.join(scr, '0000.png'))
    sys.path.insert(0, os.path.join(ROOT, 'sections'))
    import stagecomp as SC
    SC.stage_segment(dict(src=S2_CLIP, ss=0.0, dur=s2_len, out=s2raw, content=scr,
                          quad=S2_QUAD))
    # 张总侧身出现约 1 秒，然后镜头往右推、放大到大屏（人物移出画面），最后渐白
    n = int(round(s2_len * FPS))
    # 0–0.9s：从大屏特写（和上一镜头的 LY-600 标题对位）拉开露出张总；停 0.7s；再往右推回大屏
    a1, a2 = 27, 48
    ez = f"(1-cos(PI*min(1,max(0,on-{a2})/{n - a2})))/2"               # 从停顿结束一路右推到渐白，连续不停
    eo = f"(1-cos(PI*min(1,on/{a1})))/2"
    zexp = f"if(lt(on,{a2}),1.30-0.30*{eo},1+0.38*{ez})"
    xexp = f"if(lt(on,{a2}),(iw-iw/zoom)*0.55,(iw-iw/zoom)*(0.55*0+{ez}))"
    zp = (f"scale=3840:2160,zoompan=z='{zexp}':x='{xexp}':y='(ih-ih/zoom)*0.30':d=1:s={W}x{H}:fps={FPS},"
          f"fade=t=out:st={s2_len - 0.6}:d=0.6:color=white")
    run([FF, '-y', '-v', 'error', '-i', s2raw, '-vf', zp, '-an'] + ENC[2:] + [s2])
    v2 = os.path.join(WORK, 'ACT2_30.mp4')
    if shift:
        run([FF, '-y', '-v', 'error', '-i', sp, '-i', ACT2_SRC, '-filter_complex',
             f'[0:v]fps={FPS},scale={W}:{H},fade=t=in:st=0:d=0.5:color=white,format=yuv420p[a];'
             f'[1:v]fps={FPS},format=yuv420p[b];[a][b]concat=n=2:v=1:a=0[v]', '-map', '[v]'] + ENC[2:] + [v2])
    else:
        run([FF, '-y', '-v', 'error', '-i', ACT2_SRC, '-vf', f'fps={FPS}', '-an'] + ENC[2:] + [v2])
    lst = os.path.join(WORK, 'act2_list.txt')
    open(lst, 'w', encoding='utf-8').write(f"file '{v2}'\nfile '{s2}'\n")
    vid = os.path.join(WORK, 'ACT2_vid.mp4')
    run([FF, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', vid])
    total = dur(vid)
    run([FF, '-y', '-v', 'error', '-i', vid, '-i', v6, '-i', v7, '-filter_complex',
         f'[1:a]adelay={int(ACT2_VOICE[0][1] * 1000)}|{int(ACT2_VOICE[0][1] * 1000)}[a1];'
         f'[2:a]adelay={int(t7 * 1000)}|{int(t7 * 1000)}[a2];'
         f'[a1][a2]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad,atrim=0:{total}[a]',
         '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-ac', '2', out])
    lines = [{'who': 'zhang', 'n': 6, 'start': ACT2_VOICE[0][1], 'end': ACT2_VOICE[0][1] + dur(v6)},
             {'who': 'zhang', 'n': 7, 'start': t7, 'end': t7 + dur(v7)}]
    return out, lines


def make_screen(path):
    """大屏内容：按大屏真实宽高比（约 2.25:1）排版，白底深灰字，不拉伸。"""
    cw, ch = 2250, 1000
    img = Image.new('RGB', (cw, ch), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f1 = ImageFont.truetype(r"C:\Windows\Fonts\segoeuil.ttf", 230)
    f2 = ImageFont.truetype(r"C:\Windows\Fonts\Dengl.ttf", 64)
    for txt, font, y in (('LY-600', f1, 300), ('电动旋转升降护理床', f2, 600)):
        b = d.textbbox((0, 0), txt, font=font)
        d.text(((cw - (b[2] - b[0])) // 2 - b[0], y), txt, font=font, fill=(52, 50, 54))
    img.save(path)


def norm(src, name):
    """统一成 1920x1080 30fps + 48k 立体声。"""
    out = os.path.join(WORK, name + '_n.mp4')
    run([FF, '-y', '-v', 'error', '-i', src, '-vf', f'fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}',
         '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000', '-ac', '2'] + ENC[2:] + ['-c:a', 'aac', out])
    return out


def sub_image(cn, en, color):
    img = Image.new('RGBA', (W, 140), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for txt, font, y in ((cn, F_CN, 18), (en, F_EN, 82)):
        if not txt:
            continue
        w = d.textbbox((0, 0), txt, font=font)[2]
        d.text(((W - w) // 2, y), txt, font=font, fill=color + (255,))
    a = np.asarray(img).astype(np.float32)
    rgb, al = a[..., :3][..., ::-1], a[..., 3:] / 255
    halo = cv2.GaussianBlur(al[..., 0], (0, 0), 10)[..., None]
    halo = np.clip(halo * 2.2, 0, 1) * (0.30 if color == LIGHT else 0.38)
    hc = np.array((0, 0, 0) if color == LIGHT else (255, 255, 255), np.float32)
    # 合成成一张图：先光晕后文字
    out_a = al + halo * (1 - al)
    out_rgb = (rgb * al + hc * halo * (1 - al)) / np.maximum(out_a, 1e-4)
    return out_rgb, out_a


_x = np.arange(256, dtype=np.float32) / 255
_curve = 0.024 + 0.972 * (_x - 0.045 * np.sin(2 * np.pi * _x))                    # 轻 S 曲线：黑点微提到 6，白点保持 254，中间调略加对比
FILM_LUT = [np.clip(255 * (_curve * g + o), 0, 255).astype(np.uint8)
            for g, o in ((0.985, 0.006), (0.995, 0.0), (1.0, -0.004))]           # B G R：亮部微暖、暗部微冷
_rng = np.random.default_rng(3)
GRAIN = [(_rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32)) for _ in range(6)]
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = (0.06 * np.clip(((_xx - W / 2) / (W * 0.62)) ** 2 + ((_yy - H / 2) / (H * 0.70)) ** 2, 0, 1.6))[..., None]


def film(f, i):
    """全片统一电影感：曲线 + 轻分色 + 细颗粒 + 很淡暗角（实拍和生成画面统一质感）。"""
    u = f.astype(np.uint8)
    for c in range(3):
        u[..., c] = cv2.LUT(u[..., c], FILM_LUT[c])
    g = cv2.resize(GRAIN[i % 6], (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    lum = u.mean(axis=2, keepdims=True) / 255
    amp = 3.2 * (1 - np.abs(lum - 0.5) * 1.4)                                     # 中间调颗粒最多，纯白纯黑几乎没有
    vig = 1 - VIGNETTE * (1 - lum ** 3)                                           # 暗角只压暗部，白底保持干净
    return np.clip(u.astype(np.float32) * vig + g * amp, 0, 255)


def sub_mask(cn, en):
    """字幕笔画透明度 + 光晕形状（颜色每帧按背景逐像素决定）。"""
    img = Image.new('L', (W, 140), 0)
    d = ImageDraw.Draw(img)
    for txt, font, y in ((cn, F_CN, 18), (en, F_EN, 82)):
        if txt:
            w = d.textbbox((0, 0), txt, font=font)[2]
            d.text(((W - w) // 2, y), txt, font=font, fill=255)
    al = np.asarray(img).astype(np.float32)[..., None] / 255
    halo = np.clip(cv2.GaussianBlur(al[..., 0], (0, 0), 10) * 2.2, 0, 1)[..., None]
    return al, halo


def draw_sub(band, al, halo, fade):
    """逐像素自适应：笔画下面背景亮→深灰字+白光晕；背景暗（比如黑衣服）→白字+黑光晕，同一行字可以分段变色。"""
    lum = cv2.GaussianBlur(band.mean(axis=2), (0, 0), 14)[..., None]
    w = np.clip((lum - 120) / 70, 0, 1)                       # 1=亮背景
    txt = np.array(LIGHT[::-1], np.float32) * (1 - w) + np.array(DARK[::-1], np.float32) * w
    hc = 255 * w
    hs = (0.30 * (1 - w) + 0.38 * w) * halo * (1 - al)
    band = band * (1 - hs * fade) + hc * hs * fade
    return band * (1 - al * fade) + txt * al * fade


def main():
    music = sys.argv[sys.argv.index('--music') + 1] if '--music' in sys.argv else None
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.join(ROOT, 'final', '连盈LY600_发布会.mp4')
    check = [float(x) for x in sys.argv[sys.argv.index('--check') + 1:]] if '--check' in sys.argv else None
    secs, lines, t0 = [], [], 0.0
    for n in (1, 2, 3, 4, 5):
        if n == 2:
            p, ln = build_act2()
        else:
            p = norm(os.path.join(ROOT, 'sections', f'ACT{n}.mp4'), f'ACT{n}')
            ln = json.load(open(os.path.join(ROOT, 'sections', f'ACT{n}_lines.json'), encoding='utf-8'))
        for l in ln:
            lines.append({**l, 'start': l['start'] + t0, 'end': l['end'] + t0})
        secs.append(p)
        t0 += dur(p)
        print(f'ACT{n}', round(dur(p), 2), 's  →', round(t0, 2))
    lst = os.path.join(WORK, 'all_list.txt')
    open(lst, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n" for p in secs))
    joined = os.path.join(WORK, 'joined.mp4')
    run([FF, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', joined])
    total = dur(joined)
    json.dump(lines, open(os.path.join(ROOT, 'final', 'lines_all.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 逐帧叠字幕
    rd = subprocess.Popen([FF, '-v', 'error', '-i', joined, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    vtmp = os.path.join(WORK, 'subbed.mp4')
    wr = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-'] + ENC + [vtmp],
                          stdin=subprocess.PIPE)
    cache = {}
    i = 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        f = film(np.frombuffer(buf, np.uint8).reshape(H, W, 3), i)
        t = i / FPS
        for k, l in enumerate(lines):
            if l['start'] - 0.05 <= t <= l['end'] + 0.25:
                if k not in cache:
                    cn, en = SUBS[l['who']][str(l['n'])]
                    cache[k] = sub_mask(cn, en)
                al, halo = cache[k]
                fade = min(1.0, (t - l['start'] + 0.05) / 0.15, (l['end'] + 0.25 - t) / 0.15)
                y0 = H - 150
                f[y0:y0 + 140] = draw_sub(f[y0:y0 + 140], al, halo, fade)
                break
        if check is None or any(abs(t - c) < 0.5 / FPS for c in check):
            pass
        wr.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
        i += 1
    wr.stdin.close()
    wr.wait()

    # 混音：配音（各幕自带）+ 音乐（可选，压在配音下面 -18dB 左右，有人声时再闪避）
    if music:
        run([FF, '-y', '-v', 'error', '-i', vtmp, '-i', joined, '-i', music, '-filter_complex',
             '[1:a]volume=1.0,asplit=2[v][sc];[2:a]volume=0.35,atrim=0:%f[m];[m][sc]sidechaincompress=threshold=0.05:ratio=6:attack=20:release=400[md];'
             '[v][md]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]' % total,
             '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', out])
    else:
        run([FF, '-y', '-v', 'error', '-i', vtmp, '-i', joined, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', out])
    print('done', out, round(total, 2), 's')


if __name__ == '__main__':
    main()
