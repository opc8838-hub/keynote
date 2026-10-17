"""MiniMax 语音：克隆音色 + 文字转语音（国内 api.minimaxi.com，直连不走代理）。

  python mmvoice.py clone ref.wav <voice_id> ["试听文本"]     # 上传参考音频并克隆
  python mmvoice.py tts <voice_id> out.mp3 "文本" [--speed 1.0] [--emotion calm] [--model speech-2.6-hd]
  python mmvoice.py ttsfile <voice_id> lines.txt outdir        # 每行一句，输出 01.mp3、02.mp3 … + 时长表
"""
import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = 'https://api.minimaxi.com'
S = requests.Session()
S.trust_env = False   # 直连，绕开本机代理
MODELS = ['speech-2.8-hd', 'speech-2.6-hd', 'speech-02-hd']


def key():
    for line in open(os.path.join(ROOT, '.env'), encoding='utf-8'):
        if line.startswith('MINIMAX_API_KEY='):
            return line.split('=', 1)[1].strip()


H = {'Authorization': 'Bearer ' + key()}


def check(r, what):
    j = r.json()
    br = j.get('base_resp', {})
    if br.get('status_code', 0) != 0:
        print(what, 'failed:', json.dumps(br, ensure_ascii=False))
        return None
    return j


def clone(ref, voice_id, text=None):
    with open(ref, 'rb') as f:
        r = S.post(HOST + '/v1/files/upload', headers=H, data={'purpose': 'voice_clone'},
                   files={'file': (os.path.basename(ref), f)}, timeout=120)
    j = check(r, 'upload')
    if not j:
        sys.exit(1)
    fid = j['file']['file_id']
    print('file_id', fid)
    body = {'file_id': fid, 'voice_id': voice_id, 'need_noise_reduction': True, 'need_volume_normalization': True}
    if text:
        body.update(text=text, model=MODELS[1])
    r = S.post(HOST + '/v1/voice_clone', headers=H, json=body, timeout=180)
    j = check(r, 'clone')
    if not j:
        sys.exit(1)
    print(json.dumps({k: v for k, v in j.items() if k != 'base_resp'}, ensure_ascii=False))
    if j.get('demo_audio'):
        out = os.path.join(os.path.dirname(os.path.abspath(ref)), voice_id + '_demo.mp3')
        open(out, 'wb').write(S.get(j['demo_audio'], timeout=120).content)
        print('demo saved', out)


def tts(voice_id, out, text, speed=1.0, emotion=None, model=None):
    for m in ([model] if model else MODELS):
        vs = {'voice_id': voice_id, 'speed': speed, 'vol': 1.0, 'pitch': 0}
        if emotion:
            vs['emotion'] = emotion
        body = {'model': m, 'text': text, 'stream': False, 'language_boost': 'Chinese',
                'voice_setting': vs,
                'audio_setting': {'sample_rate': 44100, 'bitrate': 256000, 'format': 'mp3', 'channel': 1}}
        r = S.post(HOST + '/v1/t2a_v2', headers=H, json=body, timeout=180)
        j = check(r, 'tts ' + m)
        if j and j.get('data', {}).get('audio'):
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            open(out, 'wb').write(bytes.fromhex(j['data']['audio']))
            ms = j.get('extra_info', {}).get('audio_length')
            print('saved', out, m, ms, 'ms')
            return ms
    sys.exit(1)


def opt(name, default):
    if name in sys.argv:
        return type(default)(sys.argv[sys.argv.index(name) + 1]) if default is not None else sys.argv[sys.argv.index(name) + 1]
    return default


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'clone':
        clone(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == 'tts':
        tts(sys.argv[2], sys.argv[3], sys.argv[4], opt('--speed', 1.0), opt('--emotion', None), opt('--model', None))
    elif cmd == 'ttsfile':
        lines = [l.strip() for l in open(sys.argv[3], encoding='utf-8') if l.strip()]
        rows = []
        for i, l in enumerate(lines, 1):
            ms = tts(sys.argv[2], os.path.join(sys.argv[4], '%02d.mp3' % i), l, opt('--speed', 1.0), opt('--emotion', None), opt('--model', None))
            rows.append({'n': i, 'text': l, 'ms': ms})
            time.sleep(1)
        json.dump(rows, open(os.path.join(sys.argv[4], 'lines.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
