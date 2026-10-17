"""情绪测试：同一句用不同参数各念一遍。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mmvoice import H, HOST, S, check  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'emotion_test')
os.makedirs(OUT, exist_ok=True)

LINES = {
    '技术总监': ('一张好的护理床，首先要经得起时间。所以每一张连盈，都从一块钢板开始。', ['lythe Technical DirectorCTO02', 'lythe Technical DirectorCTO01']),
    '设计师': ('参数会被记住。但真正被记住的，是那一刻——他不用再说一句：“麻烦你了。”', ['designerVoice02', 'designerVoice01']),
}
VARIANTS = {
    'A_现在': dict(speed=0.95),
    'B_正常语速': dict(speed=1.05),
    'C_开心': dict(speed=1.05, emotion='happy'),
    'D_语气加强': dict(speed=1.05, modify={'intensity': 40, 'pitch': 10}),
    'E_开心加强': dict(speed=1.05, emotion='happy', modify={'intensity': 30, 'pitch': 10}),
    'F_惊喜': dict(speed=1.05, emotion='surprised'),
}


def tts(voice, text, out, speed=1.0, emotion=None, modify=None):
    vs = {'voice_id': voice, 'speed': speed, 'vol': 1.0, 'pitch': 0}
    if emotion:
        vs['emotion'] = emotion
    body = {'model': 'speech-2.8-hd', 'text': text, 'stream': False, 'language_boost': 'Chinese', 'voice_setting': vs,
            'audio_setting': {'sample_rate': 44100, 'bitrate': 256000, 'format': 'mp3', 'channel': 1}}
    if modify:
        body['voice_modify'] = modify
    j = check(S.post(HOST + '/v1/t2a_v2', headers=H, json=body, timeout=180), os.path.basename(out))
    if j and j.get('data', {}).get('audio'):
        open(out, 'wb').write(bytes.fromhex(j['data']['audio']))
        print('ok', os.path.basename(out))


for who, (text, voices) in LINES.items():
    for k, v in VARIANTS.items():
        tts(voices[0], text, os.path.join(OUT, f'{who}_{k}.mp3'), **v)
    # 旧音色（从绿幕视频原声克隆的，说话更自然）
    tts(voices[1], text, os.path.join(OUT, f'{who}_G_旧音色_视频原声克隆.mp3'), speed=1.05)
