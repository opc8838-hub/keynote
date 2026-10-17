# keynote 发布会 skill

用来给传统企业做「苹果发布会式」宣传片的 Claude Code skill。一部 2–3 分钟、中英字幕的片子：创始人第一人称开场 → 产品揭幕 → 两个中段模块 → 回到舞台收尾。

从连盈科技 LY-600 护理床发布会片沉淀出来，整套流程已经完整跑通过一次。制作手记：https://opc8838-hub.github.io/keynote/

> 人定故事和审美，模型把它做出来。

## 安装

把整个 `keynote-launch-film` 文件夹放到 Claude Code 的 skills 目录：

```
Windows:  C:\Users\<你>\.claude\skills\keynote-launch-film\
macOS:    ~/.claude/skills/keynote-launch-film/
```

之后在 Claude Code 里说「做一个发布会片」或「企业宣传片」，Claude 会先读 `SKILL.md`，再按流程推进。

## 目录

```
keynote-launch-film/
  SKILL.md                 入口：流程、三个拍板节点、硬规矩、脚本索引（Claude 先读这个）
  README.md                本文件：给人看的说明和规范
  references/
    story.md               五幕骨架、中段模块库、转场、文案规矩
    assets.md              六类素材清单、录音要求、文件夹结构、禁用清单
    production.md          每一步的命令和参数
    qa-checklist.md        交片前自查清单
    agent-brief-template.md  派给执行助手的公共说明模板
    lessons.md             踩过的坑和用户的审美偏好
    example-lianying.md    范例：连盈片定稿文案（中英）
  scripts/
    voice/    配音：克隆音色、逐句 TTS、情绪试听
    media/    iPhone HDR 视频转 SDR
    keying/   真人视频换白底（绿幕版 / 任意背景版）
    pack/     海螺/即梦图生视频上传包
    motion/   代码动效：开灯揭幕、零件合拢、专利墙、文字地球、舞台大屏、证书展开
    compose/  总合成：拼幕、电影滤镜、自适应字幕、响度、音乐
    qa/       总览图 + 响度检查
```

## 工作流规范

### 结构
- 五幕骨架固定：舞台开场 → 产品发布 → 中段模块 A → 中段模块 B → 舞台回归。
- 中段两个模块可以换（技术、供应链、品质、研发 / 人文、用户故事、服务、匠人），但必须两块都有：一块硬、一块软，一张一弛。
- 先定文案，再按文案倒推画面。文案定稿后不再改结构。

### 分工
- 用户只在三个节点拍板：① 大纲和文案定稿，② 关键镜头样片和配音试听，③ 整片看片。
- 其余由 AI 完成；每次交片前，主线程过一遍 `references/qa-checklist.md`。
- 视频生成（海螺/即梦）由用户自己在平台上操作，AI 负责打包首帧和提示词。

### 画面
- 我们加的字只用黑/白/灰；素材本身保持原色。
- 产品不让 AI 画，用真实素材；产品画面里不出现手。
- 真人露脸用真实视频逐帧换白底，不用图生视频。
- 别家品牌、竞品产品绝不出现：每个项目都建禁用清单，交付前逐格扫一遍。

### 文件与命名
- 镜头编号前缀：S 舞台、P 产品、K 硬模块补镜、T 转场、H 软模块故事（H0 = 角色定妆照）。
- 配音：`voice\script\<人>.txt` 一行一句 → `voice\v<n>\<人>\01.mp3 …`，带 `lines.json` 时长表。
- 每幕交付三件：`ACTn.mp4`（画面 + 配音，不带字幕和音乐）、`ACTn_lines.json`（台词起止秒）、`ACTn_说明.md`。
- 成片按版本号命名；大改前把旧版复制到 `backup\`。
- 视频输出：1920x1080、30fps、H.264、yuv420p、bt709 标签，配音 -16 LUFS。

### 执行
- 多幕并行时，每幕派一个执行助手（Sonnet 子代理或 Codex CLI），公共说明用 `agent-brief-template.md` 填好。
- 本机内存 16GB：空闲内存不到 3500MB 不重渲染；逐帧处理一律走 ffmpeg 管道流式读写。

## 换项目时要改的

脚本原样来自连盈项目，文件顶部写死了路径常量（`ROOT`、`FF`、素材目录）。新项目先把脚本复制到项目里，再改这些常量，不要直接在 skill 目录里跑。

依赖：
- ffmpeg（可用环境变量 `KEYNOTE_FFMPEG` 指定）
- Python：opencv-python、numpy、pillow、requests、playwright；`e_key.py` 另需 rembg
- MiniMax API key：写在项目根目录 `.env` 里，格式 `MINIMAX_API_KEY=…`（不要提交到 git）
- 生图：Codex CLI（内置图像生成）
