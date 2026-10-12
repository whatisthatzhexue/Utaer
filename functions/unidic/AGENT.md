# AGENT.md — unidic_and_f0 模块（UniDic + tdmelodic）协作准则

> 本文档是 Utaer 项目 `unidic_and_f0` 模块中「UniDic + tdmelodic 词典声调分析」部分的协作准则，供 AI 编码代理与协作者共同遵守。
> 通用规范（分支、提交、数据格式等）以项目根目录 `AGENTS.md`（总规范）为准，本文档只补充模块特有内容。

## 1. 文档简介

本文档聚焦 `unidic_and_f0` 模块（代码位于 `functions/unidic/`），说明其角色定位、工作流、输入输出接口与文件结构，并给出验证方式与常见排错。

**一句话职责**：输入日语歌词/例文文本，对照东京腔词典调型（UniDic + tdmelodic），产出 `audio_accent.json` 音调数据。

**适用范围**：

- 分支 `unidic_and_f0` 承载 UniDic + WORLD + CREPE 三类功能（总 AGENTS.md §2）；本文档只覆盖其中「UniDic + tdmelodic 词典声调分析」部分，代码位于 `functions/unidic/`。
- WORLD（`functions/world/`）与 CREPE（`functions/crepe/`）的 F0 提取不在本模块职责内。

**与本系列其他文档的关系**：

| 文档 | 关系 |
|---|---|
| `tdmelodic 配置教程.md` | 环境搭建（必读，本文档的前置） |
| `tdmelodic 使用教程.md` | 词典调用/预测方式详解（可选） |
| `本项目配置教程.md` | 宿主 Python/mecab 环境配置（本文档的前置） |
| `本项目 unidic_and_f0 部分启动教程.md` | 启动与自测流程 |

## 2. 前置条件

### 2.1 运行环境

| 环境 | 要求 |
|---|---|
| 宿主系统 | WSL2（Ubuntu-22.04） |
| 容器运行时 | docker，镜像 `tdmelodic:latest`（见配置教程） |
| 宿主 MeCab | mecab、libmecab-dev、mecab-python3（见本项目配置教程） |
| 组合词典 | `$(mecab-config --dicdir)/tdmelodic`（见配置教程 3.16） |

### 2.2 第三方仓库与文件来源

`tdmelodic/`、`mecab-unidic-neologd/`、UniDic 基础辞书（`unidic-mecab_kana-accent-2.1.2_src.zip`）均为第三方内容，不随本模块提供，须按《tdmelodic 配置教程》自行克隆/下载安装。

### 2.3 前置文档依赖

必须先完成《tdmelodic 配置教程》与《本项目配置教程》；《tdmelodic 使用教程》用于了解调用细节（可选）。

## 3. 核心步骤

### 3.1 角色定位与职责边界

**在 MVP 链路中的位置**（总 AGENTS.md §1）：录制结束后，本模块与「Demucs 人声分离 + CREPE 精确 F0 提取」并行执行；产物 `audio_accent.json` 经 FastAPI 统一转发给前端，与 F0 曲线共同支撑声调对比展示。

**做什么 / 不做什么**：

| 职责 | 说明 |
|---|---|
| ✅ 词典声调分析 | 文本 → UniDic/tdmelodic 调型（含未收录词兜底） |
| ✅ 声调预测 | 未收录词走 tdmelodic-s2ya 推断 |
| ✅ 产出 audio_accent.json | 遵循总 AGENTS.md §7.4 简化格式 |
| ❌ F0 提取 | 属 WORLD / CREPE 模块 |
| ❌ 人声分离 | 属 Demucs 模块 |
| ❌ 前端展示/对比匹配 | 由前端完成（§10） |

### 3.2 双通道工作流

```text
输入：日语歌词 / 例文文本
│
├─ 通道 A（HTTP 预测）── tdmelodic_service 容器（8000 端口，td_service.py）
│                         tdmelodic-s2ya：表記 → 読み + 声调预测（未收录词补充）
│
└─ 通道 B（本地词典解析）── 宿主 mecab-python3 MeCab.Tagger
                             + 组合词典 $(mecab-config --dicdir)/tdmelodic
                             （整词调型，如「人工知能」）
│
▼ 汇总
audio_accent.json（§7.4 格式）
```

**兜底规则**（总 AGENTS.md §9）：

- UniDic 未收录词（网络语、拟声词、专有名词）→ tdmelodic / pyopenjtalk 补充；补充失败按 NEologd 词表 + 默认平板型兜底，并在 notes 中标注「词典未收录」。
- 多调型容忍：词典给出 `variants` 变体时，发音命中任一变体即判「通过」；评价采用「接受度」而非「对错」。

**产物约定**（总 AGENTS.md §11）：任务完成后需通知前端。

### 3.3 输入输出接口

#### 接口 1：HTTP 声调预测服务（td_service.py）

| 项 | 说明 |
|---|---|
| 地址 | `POST http://localhost:8000` |
| 请求体 | `{"texts": ["文本1", "文本2", …]}` |
| 响应体 | `{"results": ["结果1", "结果2", …]}`（逐条对应，内容为 tdmelodic-s2ya 输出） |
| 实现 | 容器内逐行调用 `tdmelodic-s2ya`，按行拆分回传 |

#### 接口 2：本地词典解析（mecab-python3）

输入文本字符串，输出 MeCab 标准格式（列含义见《tdmelodic 使用教程》3.2）。

#### 接口 3：产物文件 audio_accent.json

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

**存储路径**（总 AGENTS.md §8）：`audio/<user-id>/<audio-id>/audio_accent.json`；开发期保存路径由 `test.env` 三个值拼出（§6）。

### 3.4 文件结构与命名约定

```text
functions/unidic/
├── Dockerfile              # tdmelodic 镜像构建文件（含 setuptools 修复）
├── init.py                 # 启动脚本（模块启动脚本统一命名 init.py，§11）
├── td_service.py           # HTTP 声调预测服务（启动时挂载进容器为 /app/server.py）
├── tdmelodic/              # 【第三方】tdmelodic 词典本体（自行克隆）
├── mecab-unidic-neologd/   # 【第三方】UniDic 音调词典扩充器（自行克隆）
└── *.csv                   # 大音调词典推断产物（编译产物，不入库）
```

**约定**：

- 保存路径一律引用项目根目录 `test.env`（§6），禁止硬编码路径。
- 产物文件：本模块生成 `audio_accent.json`（§11）。
- 只上传源代码，不上传编译结果（`__pycache__/`、模型权重、推断产生的 CSV 等，§4）。

### 3.5 协作规范

- **Commit**：遵循 Conventional Commits，作用域建议用 `unidic`，示例：`refactor(unidic): 重制了语音语调的结果输出格式`（§3）。
- **分支**：本模块工作在 `unidic_and_f0` 分支，通过 PR 合入 `dev`（§2）。
- **数据格式**：音调数据一律以 §7.4 简化版为准。

## 4. 验证方式

### 4.1 接口自测（通道 A）

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"texts": ["機械学習"]}'
```

预期：返回 `{"results": [...]}`，`results` 条数与 `texts` 一致。

### 4.2 词典自测（通道 B）

对照《tdmelodic 使用教程》3.1 的预期输出：「人工知能」等复合词应作为整词返回。

### 4.3 产物校验

- `audio_accent.json` 必填字段：`idx`、`morph`、`morph_reading`、`accent`、`ruby_pairs`。
- JSON 格式校验（路径为开发期保存路径示例）：

```bash
python3 -m json.tool fast-api/audio/testuser123/20030303123749/audio_accent.json
```

## 5. 常见问题 / 排错

| 症状 | 原因 | 解决方案 |
|---|---|---|
| curl 连接被拒 | tdmelodic_service 容器未启动 | 见《本项目 unidic_and_f0 部分启动教程》步骤 3 |
| 本地解析报「词典不存在」 | 宿主组合词典未安装 | 见《tdmelodic 配置教程》3.16 |
| 输出アクセント列为 `@` | 该词词典未收录，声调由推断补充 | 正常现象；notes 标注「词典未收录」（§9） |
| `results` 条数与 `texts` 不一致 | `td_service.py` 按换行拆分结果，文本内换行会导致错位（已知局限） | 调用方按单行文本逐条传入 |
| init.py 第一段成功、第二段失败 | 宿主组合词典缺失（第一段仅依赖容器） | 见《tdmelodic 配置教程》3.16 |

## 附录：参考链接

- 项目总规范：`AGENTS.md`（项目根目录）
- 模块总文档：`unidic_and_f0总文档.txt`（项目根目录）
- 本系列：`tdmelodic 配置教程.md`、`tdmelodic 使用教程.md`、`本项目配置教程.md`、`本项目 unidic_and_f0 部分启动教程.md`
- tdmelodic 官方教程（日文）：https://tdmelodic.readthedocs.io/ja/latest/pages/introduction.html
- tdmelodic：https://github.com/PKSHATechnology-Research/tdmelodic
- mecab-unidic-neologd：https://github.com/neologd/mecab-unidic-neologd/
- UniDic：https://clrd.ninjal.ac.jp/unidic/back_number.html
