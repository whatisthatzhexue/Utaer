# AGENTS.md — Utaer 项目协作与开发规范

> 本文件汇总 `docs/` 下各文档中的规范与约定（不含成员分工），是 AI 编码代理与所有协作者必须共同遵守的准则。
> 详细背景与推导见：
> - `docs/Utaer项目合作规范及分支说明 (2026.09.05版).md`（Git 协作与分支）
> - `docs/技术流程文档与开发细节说明（初期）.md`（技术路线与数据格式）
> - `docs/分工设计.md`（MVP 时序、开发约定；其中 5.2.1 的声调格式已取代技术流程文档 3.3.1 的旧格式）

---

## 1. 项目定位与技术栈

**一句话**：上传歌声/朗读，对照东京腔词典调型，指出偏差点，给出母语者接受度视角的克制简评。

**技术栈**：
- 前端：`React + TypeScript + Vite`
- 后端：`Supabase`（前期由 FastAPI 中转）
- UniDic 声调提取：`Python (MeCab)`

**MVP 链路**：
- 录制时：whisperlivekit 实时字幕 + WORLD 实时 F0 提取
- 录制后：UniDic+tdmelodic 词典声调分析 与 Demucs 人声分离 + CREPE 精确 F0 提取，两任务并行
- 交付：各功能产物经 FastAPI 统一转发给前端

---

## 2. 分支规范

**当前分支设计**（取代旧的 `main/dev/frontend/backend/unidic` 设计）：

```
main
└── dev
    ├── unidic_and_f0    # UniDic + World + Crepe
    ├── demucs           # Demucs
    └── whisperlivekit   # whisperlivekit
```

- 前端与 FastAPI 的工作通过 **PR 提交到 `dev` 分支**。
- `main` 仅用于维护 `docs` 等协作文档，**禁止直接 push 未测试稳定的功能**。
- **主干保护**：`main` 和 `dev` 为 Protected 分支，必须通过 PR 并经 owner 审查才能合入。
- **合并方式**：统一采用 `Merge Commit`。

## 3. Commit 规范

- 遵循 **Conventional Commits（约定式提交）**：`<类型>[可选的作用域]: <描述>`。
- 描述需交代本次 commit 的新内容与对旧内容的修复/更新。
- 示例：`refactor(unidic): 重制了语音语调的结果输出格式`

## 4. Git 与文件管理规范

- **只上传源代码，不要上传编译结果**（`__pycache__/`、构建产物、模型权重等），提前写好 `.gitignore`。
- **严禁上传 `.env` 文件**。根目录必须包含 `.env.example` 模板，列出所有必需的环境变量名（如 `VITE_SUPABASE_URL`、`VITE_SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY`）。
- `test.env` 是**开发期约定文件，允许提交**（见 §6）。
- 拉取单分支可用 `git clone -b <分支> <url>` 或 `git fetch origin <分支> --depth 1` 浅克隆；更新用 `git pull origin <分支>` 或 `git fetch + git merge`。

## 5. 项目目录结构

```
Utaer/
├── docs/                    # 协作文档（API 接口文档、项目计划书等），仅在 main 更新
├── fast-api/                # FastAPI 相关代码
│   └── audio/               # 开发阶段测试用文件夹，音频处理产物都保存在此处
├── functions/               # 各独立功能
│   ├── crepe/               # CREPE
│   ├── demucs/              # Demucs
│   ├── unidic/              # UniDic 和 tdmelodic
│   ├── whisper/             # whisperlivekit
│   └── world/               # WORLD
└── test.env                 # 开发期环境变量文件（见 §6）
```

## 6. 开发期路径约定（test.env）

项目根目录的 `test.env`（后缀即 `env`）内容：

```ini
TEST_USER_ID=testuser123
TEST_AUDIO_ID=20030303123749
TEST_SAVE_PATH=fast-api\audio\
```

- `functions/` 下各独立功能只需读取这三个值，拼接为 `fast-api\audio\testuser123\20030303123749\` 即为开发期处理后文件的保存路径。
- `TEST_AUDIO_ID` 采用「日期 + 6 位随机数」格式（如 `20030303123749`），与 Supabase Storage 布局一致。
- 后续接入 fast-api / supabase 时，只需修改引用这三个值所在区域的代码。

## 7. 通用数据格式规范

### 7.1 时间戳

格式为 `小时:分:秒,毫秒`，均不足位补 0：`01:02:03,438`

### 7.2 F0 文本（`f0.txt` / `f0_slow.txt`）

每行一条记录，格式为 `[时间戳][空格][Hz的数值]`。`f0.txt`（WORLD 实时）与 `f0_slow.txt`（CREPE 后处理）**格式完全一致**，前者供前端即时展示，后者生成好后由前端改用。

### 7.3 字幕文件（`jimaku.srt`）

标准 SRT 格式：序号（从 1 开始）→ `开始时间戳 --> 结束时间戳` → 字幕内容，块间空行分隔。

### 7.4 音调数据（`audio_accent.json`）

以以下**简化版**为准（《技术流程文档》3.3.1 的旧格式已作废）：

```jsonc
{
  "input": "ここに日本語の歌詞または例文を入力",
  "json_data": [
    {
      "idx": 0,                           // 【必填】序号，从0开始
      "morph": "表記形",                  // 【必填】显示用
      "lemma": "辞書形",                  // 【建议保留】查词典用
      "morph_reading": "よみがな",        // 【必填】注音基础
      "pos": "名詞*普通名詞*一般",         // 【可选】词性
      "accent": 0,                       // 【核心】单个数字（0=平板，N=第N拍下降）
      "variants": [0, 3],
      "ruby_pairs": [                    // 【必填】前端构建注音
        ["漢字", "かんじ"]
      ]
    }
  ]
}
```

- `ruby_pairs` 中首元素为 `null` 表示该读音片段没有对应的新表记字符。
- `audio_feature.json`（MVP 阶段暂时不做）建议占位结构：`{ "energy": [...], "f0_stats": {...}, "spectral": {...}, "emotion": {...} }`，时间轴与音频帧对齐，前端按进度条取对应段。

## 8. Supabase 后端规范

- **任务列表**：`accent_analysis`（产出 `audio_accent.json`）、`feature_analysis`（产出 `audio_feature.json`）；状态为 `pending` / `completed` / `failed`，前端轮询/订阅状态更新。
- **Storage 文件布局**（严格遵循）：

  ```
  audio/<user-id>/<audio-id>/audio.mp3            # 原始音频
  audio/<user-id>/<audio-id>/audio_accent.json    # 音调数据
  audio/<user-id>/<audio-id>/audio_feature.json   # 音频特征
  ```

- **权限**：每个用户仅能访问自己的 `user-id` 文件夹，可自行删除任一 audio-id 的内容（即删除查询历史）。用 Supabase RLS + Storage Policy 实现 `auth.uid() = owner_id` 行级策略；服务端写入用 service_role key 的微服务专有调用，普通用户只有读权限。
- **用户类型**：`student`（默认）/ `admin`。

## 9. 音频处理规范

- **预处理**：16kHz / 16bit / 单声道；静音头尾裁剪；F0 帧移 5ms。
- **F0 提取**：首选 CREPE（低信噪比鲁棒），备选 WORLD/pyworld（需重合成时必用）、Praat。
- **歌唱扰动平滑**：对照前先做 20ms 矩形窗移动平均（步长 5ms），无声段用最近有声段 F0 插值（处理 vibrato/overshoot/准备/细波动四种扰动）。
- **归一化**：按说话人音域归一（男 /200Hz、女 /400Hz，或按句中位数），得到句内相对 H/L 走势。
- **对齐与偏差**：以形态素莫拉边界为锚对齐词典 H/L 序列；歌唱拖拍/抢拍导致锚点漂移时用 DTW 兜底。输出每词的核位置偏差、上升点偏差、整体 H/L 相似度。
- **多调型容忍**：词典给出 `variants` 变体时，发音命中任一变体即判「通过」；评价采用「接受度」而非「对错」。
- **未收录词**：UniDic 未收录（网络语、拟声词、专有名词）走 tdmelodic / pyopenjtalk 补充；补充失败按 NEologd 词表 + 默认平板型兜底，并在 notes 中标注「词典未收录」。
- **人声分离**：Demucs 分离后只取人声，保存为 `vocal.mp3`（格式和改名统一由前端完成）。
- **部署注意**：CREPE 可选 `tiny` 模型或转 ONNX 量化（Serverless 冷启动与内存占用较大）；WORLD（pyworld）CPU 即可实时；MDX 类人声分离权重较大，初期放「可选功能」开关、异步执行、结果缓存。
- **MeCab 微服务 docker 布局**：`Dockerfile` + `requirements.txt`（mecab-python3, pyworld, fastapi 等）+ `app/`（main.py、mecab_analyzer.py、f0_extractor.py、models/）+ `local/`（libmecab.so、UniDic 词典）。

## 10. 前端规范

- **设计风格**：面向日语初学者与歌曲爱好者，界面信息不能过多，多留白，多利用单页上下滑动；参考 https://akusento.com/zh-Hans/ 与 https://www.jpitch.org/ 。
- **录音采集**：WebRTC `getUserMedia` → Web Audio API 低通滤波 → 降采样 16kHz → 二进制流传输；若走 HTTP 上传则上传后统一转码。
- **音频限制**：标准格式 mp3（非 mp3 由前端转换）；时长上限 3 分钟（超时自动停止录音）；大小上限 20MB（超出触发压缩）。
- **声调展示**：按播放进度/拖动进度条展示用户声调曲线，并与正确音调曲线对比匹配（声调数据来自后端，匹配由前端完成）。
- **振假名**：音调数据传来后显示歌词文本中的所有振假名（基于 `ruby_pairs`，可先做 mock）。
- **音频特征可视化**：能量、F0 统计、频谱等（可先占位）+ 情感分析输出窗口，多用图表、尽量直观。
- **罗马音转换按钮**：转化逻辑直接写在前端。
- **登录/注册界面**：先做 mock 版本。
- **多端适配**：做好手机端等设备的布局测试与适配。
- **评价严格度分档**：宽松/标准/严格三档反馈级别，默认标准档；避免初学者被过多红线打击积极性。
- **环境变量**：前端页面代码调用 `.env` 中的 `SUPABASE_URL`、`SUPABASE_ANON_KEY` 占位（后端就绪后可尽快连接）。

## 11. 独立功能模块开发规范（functions/）

- **启动脚本命名**：所有独立功能的启动脚本统一命名为 `init.py`：

  ```
  functions\crepe\init.py    # CREPE
  functions\demucs\init.py   # Demucs
  functions\unidic\init.py   # UniDic 和 tdmelodic
  functions\whisper\init.py  # whisperlivekit
  functions\world\init.py    # WORLD
  ```

- **保存路径**：一律引用项目目录下的 `test.env`（见 §6），禁止硬编码路径。
- **产物文件约定**：
  - whisperlivekit：录制期间流式传不带时间信息的纯文本；录制结束生成 `jimaku.srt` 传给前端。
  - WORLD：录制期间流式传 `[时间戳] [Hz]`；录制结束生成 `f0.txt` 传给前端。
  - UniDic + tdmelodic：生成 `audio_accent.json`（格式见 §7.4）。
  - Demucs + CREPE：人声分离得到 `vocal.mp3`，CREPE 非流式生成 `f0_slow.txt`（格式同 WORLD）。
  - 任务完成后均需**通知前端**。

## 12. FastAPI 的角色

接受前端信息，并向前端发消息 / 文件（前期承担中转角色，后期迁移到 Supabase）。

## 13. LLM 简评原则

- **只解释客观声学结果**：只吃「F0 走势描述 + 情感标签 + 词典调型」三类客观信息。
- **禁止主观评价**：不评判唱功好坏，不生成鼓励/贬损话术。

## 14. 风险与合规

- **版权**：仅存储用户自己录制的音频；歌词引用标注来源；不提供伴奏下载。
- **隐私**：用户声音仅存于其私有目录；用户可随时删除历史；提供合规提示文案。
- **F0 噪声**：默认 CREPE；可选人声分离前置。
- **歌唱节拍错位**：DTW 兜底 + 允许手动拖动锚点校正（v1）。
- **模型体积**：模型量化/ONNX；F0 用 pyworld 保底；任务异步化。

## 15. 待解决问题

1. 有流式信息的独立功能，**如何向 FastAPI 传递文本信息**？
2. 无流式信息的独立功能，**如何向 FastAPI 传递完成状态信息**？（曾设计基于 Supabase 的 `pending`/`completed`/`failed` 三态）
3. WORLD/CREPE 的采样间隔 `s0` 取多少 ms 能保证实时？
4. whisperlivekit 是否能实时给出时间信息（SRT 需要句子划分边界）？

## 16. 参考资源

- 声调知识入门（前端必读）：https://akusento.com/zh-Hans/guide/
- 界面参考：https://www.jpitch.org/ 、https://akusento.com/zh-Hans/
- 词典工具：UniDic（https://clrd.ninjal.ac.jp/unidic/back_number.html ）、tdmelodic（https://github.com/PKSHATechnology-Research/tdmelodic ）
- 测试语料：青空文库 https://www.aozora.gr.jp/
- 论文清单见 `docs/技术流程文档与开发细节说明（初期）.md` §5
