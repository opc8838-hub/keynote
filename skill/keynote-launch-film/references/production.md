# 制作：每一步怎么做（命令 + 参数）

脚本都在 `scripts/`。它们原样来自连盈项目，顶部写死了 `ROOT`/`FF`/素材路径，新项目先复制到项目里再改常量，不要直接在 skill 目录里跑。

## 配音

```
python mmvoice.py clone 录音.m4a <voice_id> "试听文本"          # voice_id 如 founderVoice01，字母开头
python emotion_test.py                                           # 改里面的句子和参数组合，出几版给用户挑
python mmvoice.py ttsfile <voice_id> voice\script\founder.txt voice\v1\founder [--speed 0.95] [--emotion happy]
```
- 每行一句 → `01.mp3, 02.mp3 …` + `lines.json`（每句精确毫秒）。剪辑节奏和字幕都按它对齐。
- 连盈定稿参数：创始人 speed 0.95（沉稳）；技术总监 speed 1.05 + happy + `voice_modify{intensity:30,pitch:10}`（「开心加强」）；设计师 speed 1.05 + happy。
- 单句不满意只重配那一句，文件名不变，重跑那一幕即可。
- 国内接口 `api.minimaxi.com`，`trust_env=False` 直连不走代理；报 1008 = 余额不足，请用户充值。

## 素材预处理

- `python hdr_to_sdr.py`：遍历素材库，HDR 用 `zscale…tonemap=hable:desat=0`（npl=100）转 SDR，已转的跳过。**所有 iPhone 视频必须先过这一步。**
- 输出编码一律带：`-vf scale=out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int -color_primaries bt709 -color_trc bt709 -colorspace bt709`，否则白底变成 250/253/251 发绿发黄。
- 低清老照片：Codex 图像「构图不变、只提清晰度」还原，画幅变了要居中裁回原比例。

## 真人换白底

- 绿幕：`python gs.py video in.mp4 out.mp4 <cfg>`，每人一组 CFG（桌子前沿线两点、放大 1.4、人物放在画面 0.62 处）。先 `gs.py frame` 单帧调。
- 任意背景/白布：`python e_key.py 原视频.mp4 输出.mp4 [--desk 0.95]`。HDR 自动换算；连通域只留大块，墙角阴影小块直接变白。约 3 秒/帧，**同时只跑一个**（16GB 内存）。
- 讲话镜头放慢到 0.85x（`setpts=PTS/0.85`），用配音不用原声。

## AI 补画面

1. Codex 每个镜头出 2–3 张 → 拼一页给用户挑（节点 ②）。提示词带「真实、纪实质感、不网红感」；人物镜头带定妆照参考；产品镜头带真实产品图参考。
2. `make_pack.py` 改 `SHOTS`（编号、用在哪、镜头运动、提示词）→ 桌面上传包：每镜头一个文件夹（`编号_首帧.png` + `编号_提示词.txt`）+ `00_提示词总清单.txt` + `返回视频\`。公共尾巴：「画面里不要出现任何文字、字幕、logo；人物长相、服装和图片保持一致；动作缓慢自然，不要变形。」
3. 用户在海螺（MiniMax-H3-Max / Hailuo 2.3，6 秒，最高分辨率）或即梦生成，按编号命名放回 → 拷到 `clips\`。
4. 收回后检查：水印（裁掉）、分辨率（多为 832x480，用户会用剪映调高清）、物体轻飘（落下接触帧加 2–3 帧轻震 + 「咚」声）。
- 同机位转场两张图（车间/卧室）一起生成，提示词写明同机位同角度。
- 首尾帧生成适合「两张图同机位」的过渡；产品转身这类 3D 动作 AI 会把结构转乱，别用。

## 代码动效

| 动效 | 怎么用 |
|---|---|
| 开灯揭幕 `motion/spotlight/` | `index.html` 读产品轮廓图（填充 + 描边两张 PNG），光照出轮廓后射灯随轮廓收光、全屏白；`python export.py` → `spotlight_intro.mp4`（6.4s）。master 自动前插到第二幕 |
| 零件合拢 `motion/assemble/` | 分层爆炸图 → Codex 拆层（L1…）+ `split_layers.py` 手画多边形补层 → `align_asm.py` 校色对齐 → `assemble.py`（LAND 落位、settle 无过冲、ORBIT -7°→6° 2.5D 绕拍、合拢段 3 采样运动模糊、背景视差、接地阴影 + 倒影，`backdrop.py` 影棚）。一张图做不了真 3D 转身，别试 |
| 专利墙 `motion/patent/` | `make_certs.py` 用一张真证书当版式生成 N 张 → `index.html` 弧形三排 + 数字滚到专利数；保持证书原色 |
| 文字地球 `motion/globe/` | 小字拼成球体缓转，总部亮起，出口国家城市卡片（城市名 + 当地时间）依次点亮 + 光弧 + 镜头飞行 |
| 大屏内容 `motion/screen/` | 企业历程横向时间轴、logo 揭幕；`stagecomp.py` 按大屏四角透视贴进舞台视频 |
| 导出 | `python render_html.py <index.html> <out.mp4> [30]`，或 `--stills 0,1.5,3 <目录>` 先看几帧 |

## 分幕制作

- 每幕一个目录 `sections\ACTn\`，脚本一条命令重出全幕。
- 交付三件：`ACTn.mp4`（画面 + 配音，不带字幕和音乐，-16 LUFS）、`ACTn_lines.json`（`[{"who","n","start","end"}]`，秒，相对本幕开头）、`ACTn_说明.md`（用了哪些镜头、时长、未解决问题）。
- 派活：填好 [agent-brief-template.md](agent-brief-template.md) 存成项目根 `AGENT_BRIEF.md`，每幕再写一份任务书。执行者用 Sonnet 子代理（`Agent model=sonnet`）；Claude 额度紧时改用 Codex CLI（`codex exec --skip-git-repo-check -C <项目> -- "<先读 common.md 和 ACTn.md，完整执行…写 ACTn_DONE.txt>"`，两条队列）。
- 重渲染前查空闲内存：`powershell -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)"`，**< 3500MB 就等**。逐帧处理必须走 ffmpeg rawvideo 管道流式读写。
- 主线程自己做第二幕（揭幕最讲究），同时验收各幕。

## 总合成 master.py

```
python master.py --out 成片_v1.mp4                 # 无音乐
python master.py --music 音乐.wav --out 成片.mp4
python master.py --check 12.5 60 131               # 只出这几秒的截图，先看字幕和滤镜
```
- 第二幕 = 开灯揭幕 + 发布片 + 创始人产品句/交棒句 + 交棒镜头（zoompan：大屏特写拉开 0.9s → 停 0.7s → 连续右推放大到大屏 → 渐白）。
- 电影滤镜 `film()`：轻 S 曲线（白点 254）、轻分色、中间调颗粒、暗角只压暗部。**白底不能变灰**。
- 字幕 `draw_sub()`：中文在上（等线 40）、英文在下（Segoe UI Light 25），逐像素按笔画下背景亮度选深灰 (61,59,62) / 白 (246,245,243) + 反色光晕，无描边无底框，0.15s 淡入淡出。
- 各幕 loudnorm 到 -16 LUFS；幕间该淡就淡（第二幕片尾 → 交棒 xfade 0.5s）。
- 出片后：`python scripts/qa/sheet.py 成片.mp4 总览.png` → 过 [qa-checklist.md](qa-checklist.md) → 拷到桌面进度文件夹交用户。
