"""把分层爆炸图拆成独立零件层（Codex 图像编辑），每层放在纯绿底上、位置不变、被挡部分补全、去掉品牌标志。
  python gen_layers.py            # 全部（已有的跳过）
  python gen_layers.py L4 ASM     # 只跑指定层
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, r"E:\claude工作区\lianying-launch\gen")
import gen_batch1 as G  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'src_exploded5.png')
G.OUT = os.path.join(ROOT, 'layers')
os.makedirs(G.OUT, exist_ok=True)

BASE = ('这是一次【图像编辑】：以附件这张护理床分层爆炸图为底图。画布尺寸、相机角度、透视完全不变，'
        '要保留的零件必须留在原图里完全相同的位置、大小、角度，逐像素对齐，外观、颜色、光影都不变。'
        '只保留：{keep}。'
        '除此之外的所有零件全部删掉，删掉后露出的地方和整个背景填成纯绿色(#00FF00)的平涂色块，不要阴影、不要渐变。'
        '保留的零件如果原来被别的零件挡住了一部分，要按它本来的结构把被挡住的部分自然补全，让它成为一个完整的零件。'
        '枕套和床尾毯垫上的金色图案和文字一律去掉，变成干净的纯黑色布料。不要增加任何文字、logo。')

LAYERS = {
    'L1_床头板': '左后方那块高高的暖灰色布艺床头板（连同它背面的黑色安装支架）',
    'L2_床尾板': '右前方那块暖灰色布艺床尾板（连同它下面的黑色安装支架）',
    'L3_后护栏': '床后方（画面上方偏右）那块小的暖灰色布艺护栏',
    'L4_前护栏': '床前方（画面左侧中间）那块暖灰色布艺护栏，以及挂在它上面的白色手控器和卷曲的电线',
    'L5_床垫': '最上层的白色分段床垫、白色枕头（黑色枕套）和床尾那块黑色毯垫，作为一个整体',
    'L6_床板骨架': '床垫下面那层深灰色金属床板骨架（横向条板、可折叠的背板和腿板框架、以及上面连着的银色电动推杆）',
    'L7_底座': '最下面那个暖灰色布艺包边的长方形底座，以及底座里面的深灰色金属框架、黑色电机和电控盒、底座边上的黑色小支架',
    'L8_轮子': '底座下方的四个万向轮，以及轮子上方那些小的金属连接件和螺丝',
}

ASM = ('这是一次【图像编辑】：以附件这张护理床分层爆炸图为底图。保持完全相同的相机角度、透视、画布尺寸和每个零件的外观、颜色、光影，'
       '把所有零件按真实结构装配合拢成一张完整的护理床：金属床板骨架落进底座里，白色床垫和枕头平铺在骨架上（床垫保持图中背部略微抬起的姿态），'
       '床头板竖立在底座左端、床尾板竖立在底座右端，两块小护栏贴在床的两侧，四个轮子装在底座下面，手控器挂在前护栏上。'
       '装配后床的整体位置以底座在原图中的位置为准，底座不移动。背景纯白，床下一道柔和的接地阴影。'
       '枕套和床尾毯垫上的金色图案和文字一律去掉，变成纯黑色布料。不要增加任何文字、logo。')

if __name__ == '__main__':
    only = set(sys.argv[1:])
    jobs = [(n, [SRC], BASE.format(keep=k)) for n, k in LAYERS.items() if not only or n.split('_')[0] in only]
    if not only or 'ASM' in only:
        jobs.append(('ASM_装配完成', [SRC], ASM))
    with ThreadPoolExecutor(3) as ex:
        for f in [ex.submit(G.run, *j) for j in jobs]:
            f.result()
    print('all done', flush=True)
