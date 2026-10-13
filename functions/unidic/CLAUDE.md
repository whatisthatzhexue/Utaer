# AGENT.md — unidic_and_f0 模块（双阶段声调分析）协作准则

> 本文档是 Utaer 项目 `unidic_and_f0` 模块的协作准则，供 AI 编码代理与协作者共同遵守。
> 模块采用**双阶段声调分析**：阶段一「tdmelodic 词典基础分析」（离线查表，禁止调型推测）+ 阶段二「规则引擎」（复合词与句级声调匹配工程）。
> 通用规范（分支、提交、数据格式等）以项目根目录 `AGENTS.md`（总规范）为准，本文档只补充模块特有内容。

## 1. 文档简介

本文档聚焦 `unidic_and_f0` 模块（代码位于 `functions/unidic/`），说明其双阶段角色定位、架构与数据流、输入输出接口、文件结构，并给出验证方式与常见排错。

**一句话职责**：输入日语歌词/例文文本，阶段一用 tdmelodic 组合词典做**确切匹配**的词法/声调基础分析；阶段二用**确定性规则引擎**（UniDic 手册 + NHK 规则 + Wikipedia 理论，四合一）完成复合词与句级声调匹配；输出严格遵循**现代标准日语（东京式声调 / Tokyo-style pitch accent）**的 `audio_accent.json`，并附带**规则概要报告**。

**适用范围**：

- 分支 `unidic_and_f0` 承载 UniDic + WORLD + CREPE 三类功能（总 AGENTS.md §2）；本文档只覆盖其中「UniDic + tdmelodic 词典声调分析」部分，代码位于 `functions/unidic/`。
- WORLD（`functions/world/`）与 CREPE（`functions/crepe/`）的 F0 提取不在本模块职责内。

**与本系列其他文档的关系**：

| 文档 | 关系 |
|---|---|
| `tdmelodic 配置教程.md` | 组合词典与镜像构建（必读，本文档的前置） |
| `tdmelodic 使用教程.md` | 词典调用细节（可选；其中 HTTP 预测服务已退出分析链路，见 3.1） |
| `本项目配置教程.md` | 宿主环境 + 阶段二规则匹配库配置与扩展（本文档的前置） |
| `本项目 unidic_and_f0 部分启动教程.md` | 双阶段管线启动与输出验证 |

## 2. 前置条件

### 2.1 运行环境

| 环境 | 要求 |
|---|---|
| 宿主系统 | WSL2（Ubuntu-22.04） |
| 宿主 MeCab | mecab、libmecab-dev、mecab-python3（见本项目配置教程） |
| 组合词典 | `$(mecab-config --dicdir)/tdmelodic`（见配置教程 3.16） |
| 容器运行时 | 分析链路**不依赖容器**；docker 镜像仅用于配置阶段的大词典推断（配置教程 3.8–3.14） |

### 2.2 参考资料库（规则引擎的权威依据）

项目根目录 `NHK/` 下：

| 资料 | 文件 | 用途 |
|---|---|---|
| 资料一 | 阶段一输出（运行时生成） | 结构化 MeCab 形态素结果，阶段二的输入 |
| 资料二 | `NHK/UNIDIC_manual.pdf` | UniDic 手册：重点为 6.3–6.7 的アクセント結合型（C1–C5）、アクセント修飾型（M1@M–M4@M）、助词助动词結合型（F1–F6）、語種、連濁 |
| 资料三 | `NHK/` 下 NHK 辞典摘录（`Ⅰ複合名詞…`、`Ⅱ数詞＋助数詞…`、`Ⅲ-1/2/3 …付属語…`、`Ⅲ発音・アクセント全般…` 等 13 篇） | 附属语、变形与句式接续的声调变调规则 |
| 资料四 | `NHK/Japanese_pitch_accent.htm` | Wikipedia 日本语音调条目：东京式（起伏型/平板型）分类、声调核判定、拍（Mora）与音高转换、核前/核后变调的理论补充 |

### 2.3 第三方仓库与前置文档

- `tdmelodic/`、`mecab-unidic-neologd/`、UniDic 基础辞书均为第三方内容，须按《tdmelodic 配置教程》自行克隆/下载安装。
- 前置文档：`tdmelodic 配置教程.md` 与 `本项目配置教程.md`（必读）；`tdmelodic 使用教程.md`（可选）。

## 3. 核心步骤

### 3.1 角色定位与职责边界

#### 阶段一：tdmelodic 词典基础分析（离线查表）

- 调用 `tdmelodic` 组合词典对输入文本进行基础词法与声调分析。
- **核心约束（严格执行）：禁止使用调型推测（Pitch Pattern Estimation）功能**。该功能不稳定且句子级别出错率极高，分析过程必须完全依赖词典确切匹配。
  - 禁止在分析链路中调用 `tdmelodic-s2ya` / `tdmelodic-sy2a`；
  - `td_service.py`（HTTP 预测服务，内部调用 `tdmelodic-s2ya`）**退出分析链路**，仅作历史遗留保留，不得在管线中调用。
- 提取并输出 MeCab 的分析结果（词性、原词、基础调型等元数据），作为阶段二的输入数据（**资料一**）。

#### 阶段二：基于规则引擎的复合词与句级声调匹配工程

- 以「资料一」为输入，严格结合「资料二」（UniDic 手册）、「资料三」（NHK 规则）与「资料四」（Wikipedia 理论）中的逻辑编写代码。
- 规则引擎为**模块化/可扩展**架构，支持新增、修改或调整自定义声调规则的优先级（见本项目配置教程 3.8）。
- 所有声调推导与输出结果**严格遵循现代标准日语（东京式声调）**规则；运行过程严格遵循逻辑条件判断，**不得引入非确定性的推测**。

#### 做什么 / 不做什么

| 职责 | 说明 |
|---|---|
| ✅ 阶段一：词典查表 | MeCab + 组合词典确切匹配，产出资料一 |
| ✅ 阶段二：规则推导 | 复合词/活用形/付属語/核合法性/多单位/兜底规则 |
| ✅ 产出 audio_accent.json | 东京式调型，遵循总 AGENTS.md §7.4 简化格式 |
| ✅ 产出 rule_report.json | 规则概要报告（命中规则清单与匹配逻辑） |
| ❌ 调型推测 | 禁止 `tdmelodic-s2ya` / `-sy2a` 进入分析链路 |
| ❌ 非确定性行为 | 规则匹配只做条件判断，无随机/统计推断 |
| ❌ F0 提取 / 人声分离 | 属 WORLD / CREPE / Demucs 模块 |
| ❌ 前端展示/对比匹配 | 由前端完成（§10） |

### 3.2 双阶段架构与数据流

```text
输入：日语歌词 / 例文文本
│
▼
┌────────────────── 阶段一：tdmelodic 词典基础分析（离线查表）──────────────────┐
│ mecab-python3 MeCab.Tagger + 组合词典 $(mecab-config --dicdir)/tdmelodic    │
│ 【硬约束】禁止调型推测：不调用 tdmelodic-s2ya / -sy2a；只采用词典确切匹配      │
│ 产物：资料一（结构化形态素：表層形/発音/読み/原型/品詞/活用型/活用形/          │
│        調型（数字或未收录标记）/拍数/变体）                                    │
└───────────────────────────────────────────────────────────────────────────┘
│
▼ 资料一
┌────────────────── 阶段二：规则引擎（确定性条件匹配，禁止推测）────────────────┐
│ 复合词规则      —— 资料二 C1–C5（結合型）＋ 资料三 Ⅰ複合名詞（四型・拍数规律）  │
│ 活用形规则      —— 资料二 表9（修飾型 M1@M–M4@M）＋ 资料三 活用形表            │
│ 付属語接続规则  —— 资料三 Ⅲ-1/2/3（不干渉原则・平板式/起伏式・例外）＋ 资料二 F 系列│
│ 核合法性规则    —— 特殊拍（ン・ッ・ー・二重母音副音・無声化拍）核移位          │
│                  （资料三 Ⅰ複合名詞/Ⅲ全般 ＋ 资料四 非自立拍理论）             │
│ 多单位/句级规则 —— 资料三 Ⅲ全般 4.（複数単位）＋ 资料四（アクセント単位・downstep）│
│ 兜底规则        —— 語種倾向表（资料三 Ⅲ全般 1.）→ 默认平板型，notes 标注        │
│                  「词典未收录」（总 AGENTS.md §9）                              │
└───────────────────────────────────────────────────────────────────────────┘
│
▼
输出（严格遵循现代标准日语・东京式声调）：
  audio_accent.json   —— 分析结果（§7.4 格式；accent=声调核位置：0=平板型，N=第N拍下降）
  rule_report.json    —— 规则概要报告（本次成功匹配并触发的规则清单与匹配逻辑概要）
```

**确定性要求**：规则引擎为纯函数式条件判断（match → apply），同一输入必得同一输出；任何规则不得引入随机、统计或机器学习推断。每条规则必须携带 `source_ref`（资料编号 + 节号，如 `NHK Ⅲ-1 2.1`、`UniDic 表10 C2`），保证可追溯。

### 3.3 输入输出接口

#### 接口 1：资料一（阶段一输出 / 阶段二输入）

```jsonc
{
  "input": "米を盛る",
  "morphs": [
    {
      "idx": 0,                          // 序号，从 0 开始
      "morph": "米",                     // 表層形
      "lemma": "米",                     // 原型
      "reading": "コメ",                 // 読み（注音基础）
      "pron": "コメ",                    // 発音
      "pos": "名詞-普通名詞-一般",        // 品詞
      "conj_type": "",                   // 活用型（无则空）
      "conj_form": "",                   // 活用形（无则空）
      "accent_raw": "2",                 // 词典调型：数字（0=平板，N=第N拍下降）、
                                         // 逗号分隔多调型、或 @（词典未收录）
      "mora_count": 2,                   // 拍数（モーラ数）
      "is_unknown": false                // @ 标记的归一化布尔值
    }
  ]
}
```

#### 接口 2：产物文件 audio_accent.json（分析结果）

遵循总 AGENTS.md §7.4 简化格式（旧格式已作废）：

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

- `accent` 即**东京式声调核位置**：0 = 平板型（无核），N = 第 N 拍后下降（对应资料四的 nucleus / 下げ核定义）。

#### 接口 3：产物文件 rule_report.json（规则概要报告）

在分析结果下方附带输出，记录本次处理过程中**成功匹配并触发的规则清单与匹配逻辑概要**：

```jsonc
{
  "input": "米を盛る",
  "matched_rules": [
    {
      "rule_id": "R-PART-FLAT",          // 规则唯一标识
      "name": "平板式付属語・基本接続",    // 规则名
      "source_ref": "NHK Ⅲ-1 1.1",       // 依据（资料编号+节号）
      "target": [0, 1],                  // 作用的形态素 idx 区间
      "logic": "「を」为平板式付属語（无自身下がり目），『付属語不干渉』原则下不改变前部调型",
      "result": "コメ＼オ"                // 匹配结果（＼=下がり目位置）
    }
  ]
}
```

**存储路径**（总 AGENTS.md §8）：`audio/<user-id>/<audio-id>/audio_accent.json` 与 `audio/<user-id>/<audio-id>/rule_report.json`；开发期保存路径由 `test.env` 三个值拼出（§6）。

### 3.4 文件结构与命名约定

```text
functions/unidic/
├── Dockerfile              # tdmelodic 镜像构建文件（含 setuptools 修复）
├── init.py                 # 启动脚本（模块启动脚本统一命名 init.py，§11；双阶段管线 CLI 入口）
├── pipeline.py             # 双阶段管线编排：stage1 → stage2 → 组装双产物
├── stage1_analyzer.py      # 阶段一：词典查表（MeCab+tdmelodic；禁止调型推测）
├── stage2_rules/           # 阶段二：规则引擎（模块化/可扩展）
│   ├── __init__.py         # 规则注册表：按优先级加载全部规则
│   ├── base.py             # Rule 基类（match / apply / priority / source_ref）
│   ├── compound.py         # 复合词规则（资料二 C1–C5 ＋ 资料三 Ⅰ複合名詞）
│   ├── conjugation.py      # 活用形规则（资料二 表9 ＋ 资料三 活用形表）
│   ├── particles.py        # 付属語接続规则（资料三 Ⅲ-1/2/3 ＋ 资料二 F 系列）
│   ├── nucleus_legality.py # 核合法性规则（特殊拍核移位，资料三 Ⅰ/Ⅲ全般 ＋ 资料四）
│   ├── multi_unit.py       # 多单位/句级规则（资料三 Ⅲ全般 4. ＋ 资料四）
│   └── fallback.py         # 兜底规则（語種倾向表 → 默认平板，notes 标注）
├── rules_config.json       # 规则优先级/开关配置（用户可自定义，见本项目配置教程 3.8）
├── td_service.py           # 【历史遗留】HTTP 预测服务（tdmelodic-s2ya）——已退出分析链路，禁止在管线中调用
├── tdmelodic/              # 【第三方】tdmelodic 词典本体（自行克隆）
├── mecab-unidic-neologd/   # 【第三方】UniDic 音调词典扩充器（自行克隆）
└── *.csv                   # 大音调词典推断产物（编译产物，不入库）
```

**约定**：

- 保存路径一律引用项目根目录 `test.env`（§6），禁止硬编码路径。
- 产物文件：本模块生成 `audio_accent.json` 与 `rule_report.json`。
- 只上传源代码，不上传编译结果（`__pycache__/`、模型权重、推断产生的 CSV 等，§4）。

### 3.5 协作规范

- **Commit**：遵循 Conventional Commits，作用域建议用 `unidic`，示例：`refactor(unidic): 重制了语音语调的结果输出格式`（§3）。
- **分支**：本模块工作在 `unidic_and_f0` 分支，通过 PR 合入 `dev`（§2）。
- **数据格式**：音调数据一律以 §7.4 简化版为准；`accent` 一律为东京式核位置。
- **规则可追溯**：每条规则必须注明 `source_ref`（资料二/三/四的文件与节号），新增规则亦然。
- **确定性**：禁止在阶段一与阶段二引入任何推测性（统计/ML）功能；`tdmelodic-s2ya`/`-sy2a` 的调用一经发现即视为违规。

## 4. 验证方式

### 4.1 阶段一验证

组合词典解析输出与 `tdmelodic 使用教程.md` 3.1 的预期输出对照（Tab 分隔的 表層形/発音/読み… 列），确认词典确切匹配生效。

### 4.2 阶段二验证（东京式样例对照）

以 `本项目 unidic_and_f0 部分启动教程.md` 4.2/4.3 的完整样例为准：

- `米を盛る` → 米を［コメ＼オ］＋盛る［モル━］（2 个アクセント単位）；
- `住民税` → ［ジューミ＼ンゼー］（前部末型 + 特殊拍核移位）。

### 4.3 产物校验

- `audio_accent.json` 必填字段：`idx`、`morph`、`morph_reading`、`accent`、`ruby_pairs`；`accent` 为东京式核位置。
- `rule_report.json`：每条命中规则须含 `rule_id`、`name`、`source_ref`、`target`、`logic`、`result` 六字段。
- JSON 格式校验：

```bash
python3 -m json.tool fast-api/audio/testuser123/20030303123749/audio_accent.json
python3 -m json.tool fast-api/audio/testuser123/20030303123749/rule_report.json
```

## 5. 常见问题 / 排错

| 症状 | 原因 | 解决方案 |
|---|---|---|
| 输出アクセント列为 `@` | 该词词典未收录 | 正常现象：由阶段二兜底规则（語種倾向 → 默认平板）处理，notes 标注「词典未收录」（§9）；**禁止**用 s2ya 推测补齐 |
| 两条规则命中同一形态素 | 规则优先级未配置 | 检查 `rules_config.json` 的 `rule_overrides`，按优先级裁定（见本项目配置教程 3.8） |
| 核落在 ン/ッ/ー/副音 之后 | 核合法性规则未生效 | 检查 `nucleus_legality.py` 是否在注册表且优先级最高（后处理校验型规则） |
| 复合词被 MeCab 拆散 | 组合词典未收录该复合词 | 阶段二复合词规则负责合并推导（C1–C5）；若仍未合并，确认形态素序列满足复合条件 |
| 本地解析报「词典不存在」 | 宿主组合词典未安装 | 见 `tdmelodic 配置教程.md` 3.16 |
| 分析链路报容器连接错误 | 旧代码仍在调用 td_service.py | 分析链路不依赖容器；移除对 HTTP 预测服务的调用（3.1） |

## 附录：参考链接

- 项目总规范：`AGENTS.md`（项目根目录）
- 模块总文档：`unidic_and_f0总文档.txt`（项目根目录）
- 参考资料库：`NHK/`（`UNIDIC_manual.pdf`、NHK 辞典摘录 13 篇、`Japanese_pitch_accent.htm`）
- 本系列：`tdmelodic 配置教程.md`、`tdmelodic 使用教程.md`、`本项目配置教程.md`、`本项目 unidic_and_f0 部分启动教程.md`
- tdmelodic 官方教程（日文）：https://tdmelodic.readthedocs.io/ja/latest/pages/introduction.html
- tdmelodic：https://github.com/PKSHATechnology-Research/tdmelodic
- mecab-unidic-neologd：https://github.com/neologd/mecab-unidic-neologd/
- UniDic：https://clrd.ninjal.ac.jp/unidic/back_number.html
