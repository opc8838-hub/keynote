# 助手公共说明模板（填好存成项目根 AGENT_BRIEF.md）

> 用法：把 `<…>` 换成本项目的内容。连盈片的原版在 `E:\claude工作区\lianying-launch\AGENT_BRIEF.md`，可对照。

---

# <企业> <产品> 发布会片 · 助手公共说明（每个助手开工前必读）

用户是非技术负责人，最终成片由主线程统一合成、加字幕、混音。
你只负责自己那一幕，交付「干净画面 + 配音」的分段视频和台词时间表。

## 必读文件
- 导演方案（分镜、镜头意图）：`<项目>\导演方案.md`
- 定稿文案（中英对照，以这份为准）：`<项目>\全片文案.md`

## 路径
- 项目根：`<项目>`
- ffmpeg：`E:\claude工作区\back-to-work-video\tools\ffmpeg.exe`（没有 ffprobe，用 `ffmpeg -hide_banner -i 文件` 看时长）
- AI 生成镜头：`clips\`（逐个写：编号、内容、分辨率、要注意的问题如水印/轻飘）
- 真实素材（已转 SDR）：`src_sdr\`
- 照片：`<素材根>`
- 干净的产品白底图（已去别家品牌）：`<…>`
- logo：`<…>`
- 配音（已定稿）：`voice\v<n>\<人>\01–NN.mp3`；逐句文字 `voice\script\*.txt`（第 N 行 = NN.mp3）

## 铁律
1. 画面里我们加的字只用黑/白/灰，不要彩色渐变字。
2. 产品画面里不能出现手。
3. 禁用素材绝不能出现（见文末清单）。
4. 素材保持原色，不乱调色；不要加整体滤镜（主合成统一加）。
5. 苹果式克制：硬模块硬切为主，软模块慢叠化；不要花哨转场、镜头光晕、弹跳字。
6. 不烧字幕；屏幕标签、大屏内容、头衔小字属于画面设计，你来做（黑白灰、细字）。字体：中文 `C:\Windows\Fonts\Deng.ttf`/`Dengl.ttf`，英文 `C:\Windows\Fonts\segoeuil.ttf`。
7. 不要调用 MiniMax（会扣用户的钱）。Codex 生图实在缺画面才用，最多 <3> 张，一次只跑一个。

## 技术约定
- 输出 1920x1080、30fps、H.264、yuv420p，编码必须带 `-vf scale=out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int -color_primaries bt709 -color_trc bt709 -colorspace bt709`。
- cv2 读写中文路径：`cv2.imdecode(np.fromfile(p, np.uint8), 1)` / `cv2.imencode('.png', img)[1].tofile(p)`。
- Git Bash 里调 ffmpeg 加 `</dev/null`。
- 内存 16GB、没有独显、别的助手同时在跑：一次只跑一个重渲染；逐帧处理走 ffmpeg rawvideo 管道流式读写；重渲染前查空闲内存，< 3500MB 就等 30 秒再查；不要用 rembg 等 AI 模型（除非任务书明确要求）。
- 工作目录 `sections\ACT<n>\`，脚本可重复运行；大改前把旧交付复制到 `sections\backup\ACT<n>_v<k>.mp4`。

## 交付
1. `sections\ACT<n>.mp4`：画面 + 配音（-16 LUFS 左右，台词间按画面节奏留气口），不带字幕和音乐。
2. `sections\ACT<n>_lines.json`：`[{"who": "<人>", "n": 1, "start": 0.40, "end": 4.11}, ...]`（秒，相对本幕开头）。
3. `sections\ACT<n>_说明.md`：用了哪些镜头、每段时长、还有什么没解决。
4. 每秒抽 2 帧拼总览图自己检查一遍（`<skill>\scripts\qa\sheet.py`），对照 `<skill>\references\qa-checklist.md`。
5. 预览拷到桌面 `<桌面>\<企业>_成片进度\`。
6. 回复主线程：交付路径、总时长、已知问题（实话实说，别说「完美」）。

## 禁用素材（绝不能出现）
- `<文件完整路径>`（<一句话描述>）及其任何裁切/修复版本。
- 同类：<别家品牌字样 / 别家产品照片 / 第三方部件品牌>。
