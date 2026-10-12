# 本项目 unidic_and_f0 部分启动教程

> 本教程给出 Utaer 项目 unidic_and_f0 部分从文本输入到**双阶段声调分析**的完整线性启动步骤：阶段一（tdmelodic 词典基础分析，禁止调型推测）→ 阶段二（规则引擎），并通过完整样例验证东京式音调结果与规则概要报告。

## 1. 文档简介

本教程是配置流程的收尾篇。完成本教程后，你将在本地跑通模块的**双阶段管线**：

- **阶段一**：`stage1_analyzer.py` 用宿主 mecab-python3 + 组合词典对文本做**确切匹配**的词法/声调基础分析（**禁止调型推测**，不调用 `tdmelodic-s2ya`/`-sy2a`）；
- **阶段二**：`stage2_rules/` 规则引擎基于资料一完成复合词与句级声调匹配，产出严格遵循**现代标准日语（东京式声调）**的 `audio_accent.json`，并附带 `rule_report.json` 规则概要报告。

> **说明**：与旧版流程不同，分析链路**不依赖 Docker 容器**（组合词典已安装在宿主）；`td_service.py`（HTTP 预测服务）已退出分析链路，不再需要启动。

建议阅读顺序：`tdmelodic 配置教程.md` → `tdmelodic 使用教程.md`（可选）→ `本项目配置教程.md` → 本教程。

## 2. 前置条件

### 2.1 环境与软件要求

- 已完成 `tdmelodic 配置教程.md`：宿主组合词典已安装（3.16）。
- 已完成 `本项目配置教程.md`：宿主 mecab-python3、词典路径与规则库可用（3.7/3.8）。

### 2.2 文件与路径约定

- 项目根目录为 `Utaer/`，模块目录为 `Utaer/functions/unidic/`。
- `init.py`、`pipeline.py`、`stage1_analyzer.py`、`stage2_rules/`、`rules_config.json`、`Dockerfile` 由项目提供；`tdmelodic/`、`mecab-unidic-neologd/` 须已按 `tdmelodic 配置教程.md` 自行克隆安装。
- 保存路径由 `test.env` 拼出：`fast-api\audio\testuser123\20030303123749\`。

### 2.3 前置文档依赖

- `tdmelodic 配置教程.md`、`本项目配置教程.md`（必读前置）。
- `AGENT.md` 3.2/3.3（了解双阶段架构与产物格式，可选）。

## 3. 核心步骤

### 3.1 进入模块目录

```bash
cd Utaer/functions/unidic/
```

> **注意**：管线读取 `test.env` 与 `rules_config.json` 均相对项目根目录，请在 `Utaer/` 下按上述路径进入。

### 3.2 清理旧版遗留容器（可选）

旧版流程曾启动 `tdmelodic_service` 容器；新流程不再需要，若存在可清理：

```bash
docker rm -f tdmelodic_service
```

> **说明**：若容器不存在会报错，忽略即可。本步可跳过——分析链路与容器无关。

### 3.3 运行双阶段管线（CLI）

```bash
# 方式一：直接输入文本（快速验证）
python3 init.py --text "米を盛る"

# 方式二：从文件读取歌词/例文（UTF-8）
python3 init.py --input 歌詞.txt
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--text <文本>` | 直接传入待分析文本 |
| `--input <文件>` | 从 UTF-8 文本文件读取待分析文本 |
| `--user <值>` | 覆盖 `test.env` 的 `TEST_USER_ID`（可选） |
| `--audio-id <值>` | 覆盖 `test.env` 的 `TEST_AUDIO_ID`（可选） |
| `--no-report` | 不附带输出规则概要报告（默认附带） |

运行后：控制台依次打印阶段一原始解析、`audio_accent.json`（分析结果）、`rule_report.json`（规则概要报告，附于分析结果下方）；同时按 `test.env` 保存路径写出两个产物文件。

### 3.4 Python API 调用（可选）

```python
# functions/unidic/ 目录下
from pipeline import run_pipeline

accent_json, rule_report = run_pipeline("米を盛る")
# accent_json  -> {"input": …, "json_data": […]}   分析结果（东京式调型）
# rule_report  -> {"input": …, "matched_rules": […]} 规则概要报告
```

### 3.5 输出解读

`init.py` 依次打印三段：

1. **阶段一原始解析**：组合词典的 MeCab 确切匹配输出（Tab 分隔的 表層形/発音/読み/原型/品詞/活用型/活用形/調型 列）——本段**不含任何推测**，调型为词典数字或 `@`（未收录）。
2. **`audio_accent.json`**：阶段二完成后的分析结果，`accent` 为**东京式声调核位置**（0=平板型，N=第N拍下降）。
3. **`rule_report.json`**：附于分析结果下方的**规则概要报告**——本次成功匹配并触发的规则清单（`rule_id`/`name`/`source_ref`/`target`/`logic`/`result`）。

## 4. 验证方式

### 4.1 完整样例（句级 + 付属語规则）

```bash
python3 init.py --text "米を盛る"
```

预期输出（示例）：

```text
===== 阶段一：词典基础分析（确切匹配，禁止推测）=====
米	コメ	コメ	米	名詞-普通名詞-一般			2
を	オ	オ	を	助詞-格助詞
盛る	モル	モル	盛る	動詞-一般	五段-ラ行	終止形-一般	0
EOS

===== 分析结果 audio_accent.json（东京式声调）=====
```

```jsonc
{
  "input": "米を盛る",
  "json_data": [
    {
      "idx": 0,
      "morph": "米",
      "lemma": "米",
      "morph_reading": "コメ",
      "pos": "名詞*普通名詞*一般",
      "accent": 2,
      "variants": [],
      "ruby_pairs": [["米", "こめ"]]
    },
    {
      "idx": 1,
      "morph": "を",
      "lemma": "を",
      "morph_reading": "オ",
      "pos": "助詞*格助詞",
      "accent": 0,
      "variants": [],
      "ruby_pairs": [[null, "を"]]
    },
    {
      "idx": 2,
      "morph": "盛る",
      "lemma": "盛る",
      "morph_reading": "モル",
      "pos": "動詞*一般",
      "accent": 0,
      "variants": [],
      "ruby_pairs": [["盛", "も"], ["る", "る"]]
    }
  ]
}
```

```text
===== 规则概要报告 rule_report.json（成功匹配并触发的规则清单）=====
```

```jsonc
{
  "input": "米を盛る",
  "matched_rules": [
    {
      "rule_id": "R-LEX-DICT",
      "name": "词典直取（阶段一・确切匹配）",
      "source_ref": "tdmelodic 组合词典（UniDic 2.1.2 + 大音调词典）",
      "target": [0, 0],
      "logic": "「米」词典收录，调型=2（尾高型，核在第2拍）→ 直接采用",
      "result": "コメ＼"
    },
    {
      "rule_id": "R-PART-FLAT",
      "name": "平板式付属語・基本接続",
      "source_ref": "NHK Ⅲ-1 1.1（『付属語不干渉』）",
      "target": [0, 1],
      "logic": "「を」为平板式付属語（无自身下がり目）→ 名詞部分调型保持，直接连读",
      "result": "コメ＼オ"
    },
    {
      "rule_id": "R-LEX-DICT",
      "name": "词典直取（阶段一・确切匹配）",
      "source_ref": "tdmelodic 组合词典（UniDic 2.1.2 + 大音调词典）",
      "target": [2, 2],
      "logic": "「盛る」词典收录，调型=0（平板型）→ 直接采用",
      "result": "モル━"
    },
    {
      "rule_id": "R-MULTI-UNIT",
      "name": "複数単位（句级）",
      "source_ref": "NHK Ⅲ全般 4.（複数の単位からなる語）",
      "target": [0, 2],
      "logic": "「米を」与「盛る」各为独立アクセント単位；每单位至多一个核",
      "result": "コメ＼オ・モル━"
    }
  ]
}
```

验证要点：

- `audio_accent.json` 中「米」的 `accent=2`（尾高型）与「盛る」的 `accent=0`（平板型）符合东京式；
- 付属語「を」`accent=0` 表示附着、不产生新核（整单位核由「米」承担，即 コメ＼オ）；
- `rule_report.json` 列出全部 4 条命中规则，每条含依据（`source_ref`）与匹配逻辑（`logic`）。

### 4.2 复合词样例（前部末型 + 特殊拍核移位）

```bash
python3 init.py --text "住民税"
```

阶段二规则概要（示例，词典将「住民税」拆分为「住民」+「税」时）：

```jsonc
{
  "input": "住民税",
  "matched_rules": [
    {
      "rule_id": "R-COMPOUND-C3",
      "name": "复合词・前部末型",
      "source_ref": "NHK Ⅰ複合名詞 1.2）＋ UniDic 表10 C3",
      "target": [0, 1],
      "logic": "后部要素「税」为2拍，属前部末型 → 核置于前部要素末拍之后",
      "result": "ジューミン＼ゼー"
    },
    {
      "rule_id": "R-NUCLEUS-SPECIAL",
      "name": "核合法性・特殊拍核移位",
      "source_ref": "NHK Ⅰ複合名詞 1.2）但书＋ Ⅲ全般 A（＋ Wikipedia 非自立拍）",
      "target": [0, 1],
      "logic": "前部末拍「ン」为特殊拍，核不可置于其后 → 前移1拍",
      "result": "ジューミ＼ンゼー"
    }
  ]
}
```

预期最终调型：**ジューミ＼ンゼー**（与 NHK 辞典原文用例一致）。

> **说明**：若组合词典已收录「住民税」整词，阶段一直接返回词典调型，规则报告仅出现 `R-LEX-DICT`——两种路径都合法，且都**不使用调型推测**。

### 4.3 产物文件校验

```bash
python3 -m json.tool fast-api/audio/testuser123/20030303123749/audio_accent.json
python3 -m json.tool fast-api/audio/testuser123/20030303123749/rule_report.json
```

预期：两个 JSON 均格式合法；`rule_report.json` 的 `matched_rules` 非空，且每条含六字段。

### 4.4 结束与清理（可选）

```bash
docker rm -f tdmelodic_service
```

## 5. 常见问题 / 排错

| 症状 | 原因 | 解决方案 |
|---|---|---|
| 阶段一报「词典不存在」 | 宿主组合词典未安装 | 完成 `tdmelodic 配置教程.md` 3.16 与 `本项目配置教程.md` 3.7 |
| 阶段一调型列为 `@` | 该词词典未收录 | 正常现象：阶段二走兜底规则（語種倾向 → 默认平板）并在 notes 标注「词典未收录」；**禁止**用 s2ya 推测补齐 |
| `rule_report.json` 的 `matched_rules` 为空 | 全部命中 `R-LEX-DICT`（词典直取）或规则未注册 | 词典直取是合法路径；若怀疑注册问题，运行 `本项目配置教程.md` 4.3 检查注册表 |
| 两条规则命中同一形态素且结果冲突 | 规则优先级配置错误 | 检查 `rules_config.json` 的 `rule_overrides`（`本项目配置教程.md` 3.8.1） |
| 核落在 ン/ッ/ー 之后 | 核合法性规则被关闭或优先级被调低 | 恢复 `nucleus_legality` 的最高优先级并启用 |
| 报「连接 localhost:8000 被拒」 | 旧版代码仍调用 HTTP 预测服务 | 分析链路不依赖容器；移除对 `td_service.py` 的调用（见 `AGENT.md` 3.1） |
| 输出乱码 | 终端编码问题 | 使用 UTF-8 终端；输入文件保存为 UTF-8（无 BOM） |

## 附录：参考链接

- 项目总规范：`AGENTS.md`（项目根目录）
- 模块总文档：`unidic_and_f0总文档.txt`（项目根目录）
- 参考资料库：`NHK/`（`UNIDIC_manual.pdf`、NHK 辞典摘录、`Japanese_pitch_accent.htm`）
- 本系列：`tdmelodic 配置教程.md`、`tdmelodic 使用教程.md`、`本项目配置教程.md`、`AGENT.md`
