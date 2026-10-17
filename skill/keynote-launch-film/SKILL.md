---
name: keynote-launch-film
description: keynote 发布会 skill —— 给传统企业做「苹果发布会式」2–3 分钟宣传片：创始人第一人称开场 → 产品揭幕 → 两个可替换的中段模块（技术/人文/供应链/品质…）→ 回到舞台收尾，中英字幕。人定故事和审美，AI 写文案、克隆配音、补画面、用代码做动效、分幕剪辑合成。用户说「做一个发布会片 / 企业宣传片 / keynote 风格的片子」时先读这里。
---

# keynote 发布会 skill

从连盈科技 LY-600 护理床发布会片（2026-10，2 分 46 秒）沉淀出来。成片 `桌面\连盈_成片进度\连盈LY600_完整v7.mp4`，工程 `E:\claude工作区\lianying-launch`，制作手记网站 https://opc8838-hub.github.io/keynote/ 。

**分工原则：人定故事和审美，模型把它做出来。** 用户（导演）只在三个节点拍板，其余都由 AI 做完、自查完再交。

**迭代预算**：连盈片实际认真改了约 4 轮：1–2 次大改，其余是微改；前几轮返工主要是视频细节没做好。下一部的目标是**1 次大改 + 1–2 次微改**。办法是每次交片前，把 [references/qa-checklist.md](references/qa-checklist.md) 逐条过完。

## 三个拍板节点（只有这三处等用户）

| 节点 | 交给用户什么 | 用户做什么 |
|---|---|---|
| ① 大纲 + 文案定稿 | 一页表（每幕时长/谁讲/气质/画面来源）+ 中英逐句文案 + 中段两个模块的选择理由 | 改文案、换模块。**文案定了，画面全按文案倒推，之后不再改结构** |
| ② 关键镜头样片 | 角色定妆照、产品揭幕那一镜、每幕 1 张代表画面（Codex 出 2–3 选 1）+ 配音试听 | 挑图、定声音情绪 |
| ③ 整片看片 | 完整片 + 总览图（`scripts/qa/sheet.py`） | 截图 + 时间点给意见 |

## 总流程

1. **导演大纲与文稿** → [references/story.md](references/story.md)：五幕骨架、中段模块库、文案规矩、转场设计。先出大纲表，再出逐句文案（中英对照，数字写成汉字给配音用）。
2. **素材收集与入库** → [references/assets.md](references/assets.md)：六类素材清单、录音要求、禁用清单、文件夹结构。素材一到，先做 HDR→SDR（`scripts/media/hdr_to_sdr.py`）。
3. **声音克隆与配音** → [references/production.md](references/production.md#配音)。**配音是连盈片最弱的一环（录音质量的问题，不是流程的问题）**：开工前就把录音要求发给用户，录音不合格宁可重录；配音不满意可以随时单句重配，流程不用变。
4. **AI 补画面**：Codex 生图 → 打包每镜头一个文件夹（首帧 + 提示词，`scripts/pack/make_pack.py`）→ 用户自己在海螺/即梦生成视频 → 放回「返回视频」按编号对上。
5. **代码动效**：开灯揭幕、零件合拢、专利墙、文字地球、大屏历程、证书展开，都是 `scripts/motion/` 里可改参数的模板。
6. **分幕并行制作**：每幕一个执行者（Sonnet 子代理 / Codex CLI），公共说明用 [references/agent-brief-template.md](references/agent-brief-template.md) 填好再派。主线程做产品揭幕那幕 + 总合成。
7. **总合成**（`scripts/compose/master.py`）：拼五幕、统一电影滤镜、逐像素自适应中英字幕、各幕 loudnorm -16 LUFS、加音乐。→ 跑 [qa-checklist](references/qa-checklist.md) → 交节点 ③。

## 硬规矩（用户多次强调，每部片都适用）

- 画面里我们加的字**只用黑/白/灰**，不要彩色渐变字；素材本身（专利墙、照片）保持原色，不乱调色。
- **产品画面里不能出现手**；人文故事里人的手可以。
- **产品不让 AI 画**，用真实图/真实视频；**真人露脸用真实视频逐帧换白底**，不用图生视频（会变形）。
- **别家品牌、竞品的产品绝不能出现**：建禁用清单，交付前逐帧扫。
- 苹果式克制：技术类模块硬切快剪，人文类模块慢叠化；人物淡入淡出约 0.5s；不要镜头光晕、弹跳字、花哨转场。
- 讲话镜头放慢到约 0.85 倍更有苹果味。
- 不擅自调用 MiniMax 视频生成（花用户的钱）；语音 TTS 可以用。视频由用户自己在平台生成。
- 大改前先备份旧版（`backup\…_v<n>.mp4`），用户常会要求「保留保底以便对比」。

## 脚本索引（全部来自连盈项目，已验证；换项目时改各文件顶部的路径常量）

| 位置 | 用途 |
|---|---|
| `scripts/voice/mmvoice.py` | MiniMax 克隆音色 / 单句 TTS / 按行批量出 01.mp3… + 时长表 |
| `scripts/voice/emotion_test.py` | 同一句用不同情绪、语速各念一遍给用户挑 |
| `scripts/media/hdr_to_sdr.py` | iPhone HDR（HLG/杜比视界）整库转 SDR bt709，否则整片发白 |
| `scripts/keying/gs.py` | 绿幕→白底（色差抠像 + 去溢色 + 抹桌子 + 放大放右） |
| `scripts/keying/e_key.py` + `variants.py` | 「方案 E」：任意背景真人视频逐帧换白底（净背景差值保发丝 + isnet 实心身体），约 3 秒/帧 |
| `scripts/pack/make_pack.py` | 海螺/即梦上传包：每镜头一个文件夹（首帧 + 提示词 + 命名规则）+ 总清单 + 返回视频文件夹 |
| `scripts/motion/spotlight/` | 开灯揭幕：光球→光锥→光束照出产品轮廓→全屏白（canvas + `export.py` 出 mp4） |
| `scripts/motion/assemble/` | 分层爆炸图零件合拢（`split_layers.py` 切层、`align_asm.py` 对齐、`assemble.py` 合拢 + 2.5D 绕拍、`backdrop.py` 影棚背景） |
| `scripts/motion/patent/` | 弧形三排专利墙 + 数字滚动（`make_certs.py` 生成证书卡） |
| `scripts/motion/globe/` | 文字地球 + 城市卡片 + 光弧（出口国家） |
| `scripts/motion/screen/` | 舞台大屏内容（企业历程时间轴、logo 揭幕） |
| `scripts/motion/render_html.py` | 任一 canvas 预览页（`window.__render(t)`）逐帧导出 mp4 / PNG 序列 |
| `scripts/motion/cards.py` + `photoseg.py` | 证书叠放→左右展开、老照片推镜/视差段 |
| `scripts/compose/stagecomp.py` + `screenquad.py` | 把大屏内容透视贴进舞台视频的大屏四角 |
| `scripts/compose/master.py` | 总合成：拼幕、交棒镜头 zoompan 推进、电影滤镜 `film()`、自适应字幕 `draw_sub()`、响度、`--music` |
| `scripts/qa/sheet.py` | 每 N 秒一格总览图 + 整体响度，交片前自查用 |

依赖：ffmpeg（`E:\claude工作区\back-to-work-video\tools\ffmpeg.exe`，可用环境变量 `KEYNOTE_FFMPEG` 覆盖；没有 ffprobe）；Python 装 opencv、numpy、pillow、requests、playwright、rembg（只有 e_key 用）；MiniMax key 在项目根 `.env` 的 `MINIMAX_API_KEY=`（见 [[minimax-api]] 记忆）；Codex 生图 `C:\Users\Administrator\AppData\Local\OpenAI\Codex\bin\9691020b546a15b2\codex.exe exec --skip-git-repo-check -C <目录> "用内置图像生成工具…保存为 x.png"`（约 1 分钟/张）。

坑与经验 → [references/lessons.md](references/lessons.md)。连盈片完整文案（可当范例） → [references/example-lianying.md](references/example-lianying.md)。
