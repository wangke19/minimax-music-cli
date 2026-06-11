# MiniMax Music Generator

AI 音乐生成 CLI 工具，通过 MiniMax API 从文本提示词生成歌曲（含歌词演唱）或纯音乐。支持批量生成、自动命名、证据链跟踪、断点续传。

## 快速开始

```bash
# 设置 API Key
export MINIMAX_API_KEY="your-api-key"

# 单曲生成（AI 自动生成歌词）
python3 main.py -p "华语流行, 深情, 夜晚, 男声" --use-lyrics-gen

# 纯音乐
python3 main.py -p "纯音乐, 钢琴, 雨夜, 忧伤" --instrumental

# 从提示词库批量生成（自动断点续传）
python3 batch_generate.py

# 批量生成（并发 3 条，每条 2 个采样）
python3 batch_generate.py -c 3 -s 2
```

---

## 项目结构

```
minimax-music-cli/
├── minimax_music/           # Python 包
│   ├── api/                 # API 封装层
│   │   ├── client.py        # BaseClient（HTTP、认证、错误处理）
│   │   ├── music.py         # MusicClient + MusicResult
│   │   └── lyrics.py        # LyricsClient + LyricsResult
│   ├── generators/          # 业务逻辑层
│   │   ├── base.py          # BaseGenerator ABC + GenerationResult
│   │   ├── vocal.py         # 有声乐生成器
│   │   └── instrumental.py  # 纯音乐生成器
│   ├── batch/               # 批处理模块
│   │   ├── manager.py       # 进度管理（断点续传）
│   │   └── runner.py        # 批处理执行器
│   ├── evidence/            # 证据链模块
│   │   ├── chain.py         # SHA256 哈希链
│   │   ├── recorder.py      # 动作记录器
│   │   └── types.py         # Actor/Action 枚举 + ChainEntry
│   ├── report/              # 报告模块
│   │   └── markdown.py      # 版权证据链报告生成
│   ├── config.py            # 常量、异常、get_api_key()
│   ├── exceptions.py        # 统一异常导出
│   ├── naming.py            # 文件名生成
│   ├── prompts.py           # 提示词格式化
│   └── cli.py               # CLI 入口
├── tests/                   # 测试（147 tests）
├── main.py                  # 单曲生成入口
├── batch_generate.py        # 批处理入口
├── generate_all_reports.py  # 批量重新生成版权报告
├── prompts_simple.txt       # 提示词库
├── requirements.txt
└── mp3/                     # 输出目录（音频 + 歌词 + 证据链 + 版权报告）
```

---

## 生成模式

| 模式 | 命令 | 说明 |
|------|------|------|
| 有声乐 + AI 歌词 | `--use-lyrics-gen` | 先调用 lyrics API 生成歌词，再生成音乐 |
| 有声乐 + 用户歌词 | `-l "歌词"` | 使用用户提供的歌词 |
| 纯音乐 | `--instrumental` | 无人声纯音乐 |

---

## CLI 参数

### 单曲生成（main.py）

```bash
python3 main.py -p "风格描述" [选项]

必选:
  -p, --prompt           风格描述（max 2000 字符）

生成模式:
  --use-lyrics-gen       先生成歌词再生成音乐
  --instrumental, -i     纯音乐模式
  --no-format-prompt     跳过提示词格式化

参数:
  -l, --lyrics           歌词文本（max 3500 字符）
  -n, --name             输出文件名（不含扩展名）
  -o, --output           输出目录（默认 ./mp3）
  -d, --duration         时长秒数（max 300，默认 300）
  -s, --samples          每条 prompt 生成的采样数（>1 时自动 A/B 命名）

模型与音频:
  --model                模型（music-2.6/music-cover/music-2.6-free/music-cover-free）
  --sample-rate          采样率（16000/24000/32000/44100，默认 44100）
  --bitrate              比特率（32000/64000/128000/256000，默认 256000）
  --format               格式（mp3/wav/pcm，默认 mp3）
  --stream               流式模式
  --aigc-watermark       添加 AIGC 水印
  --audio-url            参考音频 URL（cover 模型）
  --audio-base64         参考音频 base64（cover 模型）

配置文件:
  -f, --param-file       从 JSON/TXT/模板文件加载参数
  -v, --vars             模板变量（key=value,key=value）
```

### 批量生成（batch_generate.py）

```bash
python3 batch_generate.py [选项]

选项:
  -c, --concurrency      并发数（默认 1，免费用户上限 3，付费用户上限 20）
  -s, --samples          每条 prompt 的采样数（默认 1，>1 时 A/B/C 命名）
  --prompts              自定义提示词文件路径（默认 prompts_simple.txt）
  --skip-lyrics          跳过纯音乐的歌词 API 调用
```

---

## 证据链 & 版权报告

每次生成自动记录完整的证据链，输出到 `mp3/evidence/chain.jsonl`（SHA256 哈希链），并为每首作品生成独立的版权报告。

### 证据链

- 使用 SHA256 哈希链接，每个条目包含前驱哈希，形成不可篡改的链
- 记录完整的创作过程：人类 prompt → AI 歌词生成 → AI 音乐生成 → 报告生成
- 每条记录包含时间戳、操作类型、执行者（Human/AI/Human+AI）
- 报告生成时自动从全局链中过滤出该歌曲相关的条目

### 版权报告

为每首作品生成 `{歌名}-版权报告.md`，用于平台（如微信视频号）原创证明，包含：
- 创作意图（原始 prompt）
- 人类贡献评估（加权多因子算法，保底 30%）
- 该歌曲独立的创作过程时间线
- 证据链哈希完整性校验结果
- 文件 SHA256 指纹（含文件大小）
- 原创声明（人类+AI 协作创作说明）

### 人类贡献评估算法

基于 [北京互联网法院（2023）京0491民初11279号判例](https://www.anlilaw.com/100031/2639) 和 [美国版权局 2025 年报告](https://ipr.mofcom.gov.cn/article/rgzhn/202502/1990307.html) 评估因素，采用加权评分：

| 评估维度 | 权重 | 说明 |
|----------|------|------|
| 提示词设计 | 30% | prompt 长度与创意复杂度（≥100字符=85分，≥200=满分） |
| 创作意图表达 | 25% | 风格/情绪/场景/人声四维覆盖度 |
| 参数选择 | 15% | model、duration 等参数是否有人工选择 |
| 作品筛选 | 15% | 多采样（A/B/C）表示人工筛选最佳版本 |
| 证据链完整性 | 15% | 记录条目数越多，创作过程记录越完整 |

**提高分数技巧：** 提示词包含风格、情绪、场景、人声四个维度，长度超过 100 字符，即可获得 60%+ 的人类贡献评估。

### 批量报告管理

```bash
# 重新生成全部版权报告（自动打包为 mp3/版权报告.zip）
python3 generate_all_reports.py
```

生成完成后自动将所有 `*-版权报告.md` 打包为 `mp3/版权报告.zip`，可直接上传至微信视频号等平台的原创证明材料。

---

## API 参考

### 音乐生成 API

| 项目 | 值 |
|------|---|
| 端点 | `POST https://api.minimaxi.com/v1/music_generation` |
| 模型 | `music-2.6`（默认）、`music-cover`、`music-2.6-free`、`music-cover-free` |
| prompt 上限 | 2000 字符 |
| lyrics 上限 | 3500 字符 |
| 时长上限 | 300 秒（5 分钟） |

### 歌词生成 API

| 项目 | 值 |
|------|---|
| 端点 | `POST https://api.minimaxi.com/v1/lyrics_generation` |
| 模式 | `write_full_song`（完整歌曲）、`edit`（续写/改写） |

### 音频设置

| 参数 | 可选值 |
|------|--------|
| sample_rate | 16000, 24000, 32000, 44100 Hz |
| bitrate | 32000, 64000, 128000, 256000 bps |
| format | mp3, wav, pcm |

### 错误码

| 状态码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1002 | 限流 |
| 1004 | API-Key 错误 |
| 1008 | 余额不足 |
| 1026 | 敏感内容 |
| 2013 | 参数异常 |
| 2049 | 无效 API Key |

---

## 歌词结构标签

支持的 14 种标签：

```
[Intro] [Verse] [Pre-Chorus] [Chorus] [Hook] [Drop]
[Bridge] [Solo] [Build-up] [Instrumental] [Breakdown]
[Break] [Interlude] [Outro]
```

推荐使用：`[Intro]` `[Verse]` `[Pre-Chorus]` `[Chorus]` `[Bridge]` `[Outro]`

---

## 配置文件格式

### JSON
```json
{"prompt": "Pop, happy", "lyrics": "[Verse]\nHello", "name": "my_song"}
```

### key=value
```ini
prompt=Pop, happy
lyrics=[Verse]\nHello
name=my_song
```

### 模板格式
```ini
[风格]
Pop, happy, summer

[歌词]
[Intro]
La la la

[歌名]
my_song
```

支持模板变量 `{var}` 和 `$var`：
```bash
python3 main.py --param-file template.txt --vars "style=Pop,mood=Happy"
```

---

## 文件命名规则

| 类型 | 命名来源 | 示例 |
|------|----------|------|
| 有声乐 | AI 生成的歌名 | `星河入梦.mp3` |
| 纯音乐（标准） | `场景_氛围_风格` | `深海底_静谧_氛围电子.mp3` |
| 纯音乐（复杂） | `情绪_乐器` | `heroic_guzheng.mp3` |
| 未识别 | 时间戳 | `music_20260528_123456.mp3` |
| A/B 采样 | 歌名 + A/B 后缀 | `星河入梦A.mp3`, `星河入梦B.mp3` |

每个生成任务输出：
- `*.mp3` — 音频文件
- `*.txt` — 歌词文件（有声乐 / 纯音乐均有）
- `{歌名}-版权报告.md` — 版权证据链报告
- `evidence/chain.jsonl` — 证据链数据（持续累积）

纯音乐文件名自动追加 `-音乐` 后缀：`深海底_静谧_氛围电子-音乐.mp3`

---

## 批量生成

```bash
python3 batch_generate.py
```

### 特性

- 自动跳过空行和 `#` 注释
- 纯音乐行以 `纯音乐,` 开头自动识别
- 检测到 `usage limit exceeded` 自动保存进度退出
- 重启后从断点继续
- 随机 1-5 秒间隔避免限流（单线程模式）
- 并发模式（`-c`）使用 ThreadPoolExecutor
- 可设置每条 prompt 生成多个采样（`-s` > 1 时自动 A/B/C 命名）
- 每次生成记录证据链，完成时生成版权报告

### 账号层级检测

自动检测 API 账号层级并提示并发限制：
- **免费用户**（Starter）：并发不超过 3
- **付费用户**：并发不超过 20

### 断点续传

进度文件：`.batch_progress_{prompts文件哈希}`，每个提示词文件独立跟踪。

---

## 提示词库格式（prompts_simple.txt）

```txt
# 有声乐歌曲：风格, 情绪, 场景, 人声
华语流行, 深情, 夜晚, 男声
爵士, 慵懒, 咖啡馆, 女声

# 纯音乐：纯音乐, 风格, 场景, 氛围
纯音乐, 氛围电子, 深海底, 静谧
纯音乐, 钢琴, 雨夜, 忧伤
```

---

## 已知限制

| 问题 | 说明 |
|------|------|
| 前奏时长不精确 | API 不遵守 prompt 中的具体秒数 |
| 风格控制有限 | "禁止说唱"等约束可能不完全生效 |
| 歌词被重组 | API 会重新诠释用户歌词 |
| 时长偏短 | 不用 `--use-lyrics-gen` 时约 110-170 秒 |

建议：使用 `--use-lyrics-gen` 可提升至 190-230 秒。

---

## 提示词技巧

1. **简短明确** — 控制在 200-400 字符
2. **风格优先** — 流派/情绪放前面
3. **避免堆砌** — 不要堆叠太多细节
4. **禁止明确** — 需要排除的风格单独标出

已测试可用的风格：华语流行、民谣、摇滚、电子、爵士、嘻哈、古典、拉丁、乡村、蓝调、R&B

---

## 额度

- **套餐**: Starter（¥29/月 或 ¥290/年）
- **免费额度**: 每天 100 首
- **歌词生成**: 免费
- **超出额度**: ¥0.1/首

---

## 测试

```bash
pip install pytest
python3 -m pytest tests/ -v
```

147 个测试覆盖所有模块（API 客户端、生成器、批处理、命名、证据链、报告、CLI、配置）。

---

## 官方文档

- API 文档: https://platform.minimaxi.com/docs/guides/music-generation
- 歌词生成: https://platform.minimaxi.com/docs/api-reference/lyrics-generation

