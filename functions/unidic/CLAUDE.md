# CLAUDE.md — unidic_and_f0 模块（双阶段声调分析）：开发交接文档与协作准则

> 本文件包含两大部分：
> **【第一部分】开发交接文档** —— 供新开窗口的 Agent/开发者无缝接管本模块开发：
> 项目全貌与架构、音调推导规则汇总、踩坑指南、测试与验证规范。
> **【第二部分】模块协作准则** —— 原 `AGENT.md` 契约全文（保留，项目规范唯一权威）。
>
> 最近更新：2026-10-13（新增 No.1–4 参照例句全量对齐、数词读法子系统、の-复合结合律等）。

---

# 第一部分：开发交接文档

## 1. Project Overview & Architecture（项目全貌与文件概要）

### 1.1 一句话职责与数据流

输入日语歌词/例文文本 → **阶段一**用 tdmelodic 组合词典做**确切匹配**（禁止任何调型推测）
→ **阶段二**用确定性规则引擎（资料二 UniDic 手册＋资料三 NHK 辞典规则＋资料四 Wikipedia
东京式理论＋资料一，四合一）推导东京式声调 → 产出 `audio_accent.json` ＋ `rule_report.json`。

```text
文本
 → [预处理链] resegment → numeral → compound_verb → no_compound
 → [引擎·第一遍 推导] 规则按优先级 (−priority, rule_id) 逐 idx 匹配
 → [引擎·第二遍 校验] R-NUCLEUS-SPECIAL 核合法性扫掠（可循环修正）
 → [引擎·第三遍 整句] R-MULTI-UNIT 单位切分与整句渲染
 → [组装] audio_accent.json / rule_report.json；服务层另见 analyze_text/show_accent
```

### 1.2 核心文件清单（全部位于 `functions/unidic/`）

| 文件 | 职责 | 关键接口 |
|---|---|---|
| `init.py` | CLI 入口（`--text/--input/--user/--audio-id/--no-report/--verbose`）；三段打印；写盘 | `main()` |
| `pipeline.py` | 管线编排；**服务层唯一入口**；产物组装；进程内分析锁 | `analyze_text(text)`、`show_accent(data)`、`run_pipeline(text)`、`run_pipeline_full(text)` |
| `stage1_analyzer.py` | 阶段一词典查表（MeCab 26 列 feature 解析、`[]` 括号声调解码、同形語修正表应用） | `analyze(text, tagger, overrides)`、`build_tagger()` |
| `env_util.py` | 项目根/模块目录解析、`test.env` 读取（反斜杠归一化）、`rules_config.json` 读取 | `load_test_env()`、`build_save_dir()`、`load_rules_config()` |
| `mora_util.py` | 拍切分/拍数/特殊拍（ン・ッ・ー）/二重母音副音/无声化近似；括号解码；＼━渲染 | `split_moras()`、`decode_bracket_accent()`、`render_accent()` |
| `ruby_util.py` | `ruby_pairs` 表記-かな 贪心对齐（かな取**読み**转平假名） | `align_ruby_pairs(morph, reading)` |
| `resegment.py` | 预处理①：真未收录整词的确定性词典再切分 | `resegment_unknowns(ctx, tagger, overrides)`；规则 `R-DECOMP-LEX` |
| `numeral_util.py` | 数字→汉数词读法合成（百/千/万促音・連濁）＋助数詞促音规则 | `compose_number_kana(n)`、`apply_sokuon()` |
| `numeral.py` | 预处理②：阿拉伯数字链＋助数詞 → 合成形态素 | `merge_numerals(ctx)`；规则 `R-NUM-READING` |
| `compound_verb.py` | 预处理③：複合動詞首位规则（多调型動詞 token 裁定） | `apply_compound_verb_rule(...)`；规则 `R-CONJ-COMPOUND-VERB` |
| `no_compound.py` | 预处理④：の-复合名词结合律（双平板→整体平板） | `apply_no_compound_rule(...)`；规则 `R-COMPOUND-NO` |
| `selfcheck.py` | 全量回归自检（200+ 项：纯函数/参照例句逐字钉死/配置机制/不变量） | `python3 selfcheck.py`（全绿 = 健康） |
| `rules_config.json` | 修正表与开关（见 §1.4） | — |
| `stage2_rules/` | 规则引擎包（见 §1.3） | `from stage2_rules import registry/load_registry/run_engine` |
| `td_service.py` | **历史遗留**（调用 tdmelodic-s2ya 的 HTTP 服务）——已退出链路，禁止在管线调用 | — |

### 1.3 `stage2_rules/` 包（规则引擎）

| 模块 | 规则 | 说明 |
|---|---|---|
| `base.py` | — | `Rule` 基类（`match(morphs,i)/apply/morphs/priority/phase/source_ref/config_section`）、`MorphState`（工作状态：accent/claimed/join_next/new_unit/unit_id/notes…）、`MorphList`（即规则上下文：`add_report/render_range/render_units`）、`parse_accent_value` |
| `__init__.py` | 注册表 | 六模块自动收集 → `rule_overrides`（改优先级/禁用）→ `custom_rules_dir` 动态加载 → 稳定排序；`run_engine` 三遍执行（推导→**校验→整句**） |
| `compound.py` | `R-COMPOUND-C1…C5`、`R-COMPOUND-NAME-TITLE` | 表10 结合型公式（查 `a_con_type`；无字段按 NHK 拍数规律：1–2拍前部末型/平板例外表，3–4拍→後部一型/保存，**≥5拍不合并**）；数詞/含数字前部不黏合普通名词；人名＋肩書き 2単位 |
| `conjugation.py` | `R-CONJ-MOD` | 表9 アクセント修飾型（词典 `a_mod_type`：M1@M=N0−M；M2/M4 前部置平＋公式）＋命令形（min(base, N0−1)）；**たら/だら 让位 R-PART-TA-TE** |
| `particles.py` | `R-PART-FLAT/KIFUKU/DECIDING/NO-ODAKA/TA-TE` | 表12 F 系列（按前部品詞选 `名詞%/動詞%/形容詞%`，含形状詞→名詞%、助動詞→動詞%）：F1=保持；F2 M≥1→第2単位（です/でし/助動詞前部除外）；F3 尾高→保持否则N1+M；F4=決定型（前部置平）；F5/F6 按表。た/て 家族（一段/カ変/サ変 核前移1拍）；の（尾高或中高+特殊拍末→平板）；**終助詞不参与** |
| `nucleus_legality.py` | `R-NUCLEUS-SPECIAL` | 校验遍：核不可落 ン/ッ/ー/副音（**動詞末尾 ー 豁免**：ユー＼）；可循环前移 |
| `multi_unit.py` | `R-MULTI-UNIT`、`R-NUM-TWO-UNIT`、`R-UNIT-JOIN` | 单位切分（付属語/记号并入、首调型前缀独立、サ変·补助动词并入规则）；15/14/19 数词 2単位；そういう 等定型复合 |
| `fallback.py` | `R-LEX-DICT`、`R-FALLBACK-GOSHU-*`、`R-FALLBACK-SASA`、`R-FALLBACK-HEIBAN` | 词典直取（含括号解码）；語種倾向表分条（漢語/外来語/動詞/形容詞）；〜さ名词化→平板；默认平板＋notes「词典未收录」 |

**优先级链（默认）**：校验1000 > 活用形280 > NUM-TWO-UNIT 260 > NAME-TITLE 255 >
复合词250 > UNIT-JOIN 220 > NO-ODAKA 210 > TA-TE 205 > 付属語(F系)200 > 多単位150 >
LEX-DICT 100 > SASA 65 > GOSHU 60 > HEIBAN 50。

### 1.4 配置体系（`rules_config.json`）

| 键 | 作用 |
|---|---|
| `homograph_overrides` | **同形語修正表**（用户确认制）：按表層形覆写 `reading/pron/accent_raw/pos/a_con_type`。现含：米・盛る・日本・日本人・南東部・ひとつ・きっと・なる・なっ・私・あの・少女・10月・第・描か・（笑）・観光地 |
| `rule_overrides` | 规则优先级/禁用（如 `{"R-FALLBACK-HEIBAN": {"enabled": false}}`） |
| `custom_rules_dir` | 自定义规则目录（默认 `stage2_rules/custom`） |
| `resegment / numeral / compound_verb / no_compound` | 各预处理开关（`{"enabled": true}`） |
| `compound.nhk_flat_exceptions_priority` | NHK 平板例外表（語/化/間/顔/級/金/性/製/的）优先于词典 C 值 |
| `nucleus_legality.avoid_devoiced` | 无声化拍核回避（默认 false，NHK 现代倾向「核不动」） |

### 1.5 对外接口（服务化）

**服务层唯一入口**（详见 `docs/ENGINE_USAGE.md`）：

```python
from pipeline import analyze_text, show_accent
data = analyze_text("米を盛る")      # {"version","text","tokens":[每词 accent/moras/pitch/unit…]}
text = show_accent(data)            # 直观 NHK 音调标注文本（＼核・━平板・・单位）
```

`tokens` 每项含：`idx/morph/lemma/morph_reading/pos/accent/variants/ruby_pairs/moras/pitch/unit`；
`pitch` 为音拍级 H/L（单位内连续、单位间重置：平板 `LHH…`／頭高 `HLL…`／中高 `L…HLL…`）。

---

## 2. Pitch Accent Logic & Rulebook（音调推导核心规则汇总）

### 2.1 基本原则（不可违反）

1. **禁止调型推测**：不调用 `tdmelodic-s2ya/-sy2a`（合规扫描可 grep 验证）；全部推导 = 词典确切匹配＋确定性条件规则。
2. **确定性**：同输入必得同输出；无随机/统计/ML。
3. **规则可追溯**：每条规则带 `source_ref`（`NHK Ⅰ複合名詞 1.2）`、`UniDic 表10 C4`、`NHK Ⅲ-1 1.1` …）。
4. **词典数据优先，冲突最小化**：词典原生字段（aType/aConType/aModType）承载表10/表12/表9 的机制，直接查表；仅当与 NHK 手册/用户参照样例冲突时按「资料三优先」或修正表处理。

### 2.2 核心机制速查

- **结合型 C1–C5（表10，后部要素）**：C1=N1+M2 後部保存／C2=N1+1 後部一型／C3=N1 前部末型／
  C4=0 平板／C5=M1 前部保持（N1=前部モーラ数、M2=後部アクセント型）。
- **F 系列（表12，付属語按前部品詞选规格）**：F1 保持／F2 0型→N1+M、非0→M1（M≥1 拆第2単位；ですが合并保持；助動詞前部合并）／
  F3 0型→M1、非0→N1+M（**尾高前部→核保持于接合部**）／F4 決定型（前部核消失、N1+M）／F5=0／F6 两型。
- **M 系列（表9，活用形）**：M1@M → N0−M（意志推量形）；M2@M/M4@M → 前部置平＋公式（たかっ/たけれ/れ）。
- **た・て 家族（NHK Ⅲ-2 活用形一覧表）**：平板保持／五段保持／一段・カ変・サ変 核前移1拍；
  たら/だり（平板前部→付属語内插入）。
- **核合法性（校验遍）**：核落 ン/ッ/ー/二重母音副音 → 前移1拍；**動詞末尾 ー（いう→ユー）豁免**。
- **数词**：α) 阿拉伯数字链＋助数詞 → NHK Ⅱ 合成读法（10選→ジュッセン；600→ロッピャク；
  イチ/ロク/ハチ/ジュー＋かさたはぱ行促音；月/時 慣用例外不促音；10系頭高）；β) 汉字数词路径
  由词典 token＋R-NUM-TWO-UNIT（15/14/19＋2拍以下助数詞 2単位）处理。
- **複合動詞首位規則（用户完备规则）**：多调型動詞按「最前動詞」定值——首位平板→複合動詞中高[-2]；
  首位非平板→複合動詞平板（思い込む：思い[2]→平板）。
- **名词化「〜さ」兜底**：未收录 → 平板 0（多为0调）。

### 2.3 助词「ノ」前后词汇的结合规则（专节）

**规则（用户确认）**：格助词「の」连接的名词复合（[N1][の][N2]，当作为整体复合词处理时），
必须以「の」前后单词的**原音调**计算结合后的平板化/下落位置：

- **双平板**（N1[0]＋の＋N2[0]）→ **整体平板、单一アクセント単位**：
  `クスリヤ[0]＋ノ＋ヒトリゴト[0] → クスリヤノヒトリゴト[0]━`；
- **非双平板** → 保持既有处理（の 的付属語不干渉；尾高/中高末特殊拍的前接平板化见
  `R-PART-NO-ODAKA`，如 `コメ＼＋ノ → コメノ━`），**禁止**统一合并（保护 `キノーノ━・ヨル` 等正确切分）；
- 「N1 为个人名/多调型」等更复杂组合暂无参照样例，按不干渉处理。

**实现位置**：`no_compound.py` → `apply_no_compound_rule()`（规则 id `R-COMPOUND-NO`），
经 `pipeline._run_context` 预处理链调用（`no_compound.enabled` 开关）。
两条路径：① 已分离的 `[N1][の][N2]` 序列；② 整词含「の」的词典条目（如 薬屋のひとりごと，
借 MeCab 词典按「の」分解为 `[A][の][B]` 后判定）。合并结果：三形态素 `join_next` 链同単位、
アクセント全 0、登记六字段报告；**仅双平板组合合并**。

### 2.4 音拍级 H/L 展开（`pipeline._unit_h_l` / `show_accent`）

以アクセント単位为单位：无核 → `L`＋`H…`；核在第1拍 → `H`＋`L…`；核在第F拍 → 前F拍 `L H…H`、其后 `L`。
単位内全部下降核参与渲染（付属語決定型叠加时可有 2 处，如 `ハレ＼ルデショ＼ー`）。

---

## 3. Common Pitfalls & Best Practices（开发踩坑指南与正确做法）

### 3.1 汉字→假名与同形語（最高频坑）

| 坑 | 实例 | 正确做法 |
|---|---|---|
| 词典推断条目的**误映射** | 少女→オトメ（应为 ショージョ）、米→ベイ（教程样例为 コメ）、私→ワタクシ（项目统一 ワタシ）、日本→ニッポン（项目统一 ニホン） | 一律入 `homograph_overrides`（按**表層形**精确覆写；汉字形「成る」不受假名条目「なる」影响——表症形即天然区分）。**新映射须经用户确认**后再入表 |
| 同一词**上下文相关**命中不同条目 | 語/人/なっ/タ形 在不同句子中 aCon/a/品詞 变化；「うまいが」把 うまい 解析成名词 | 调试必须用**整句上下文**探针（`stage1_analyzer.analyze` 传完整句），不要只测单词 |
| MeCab 整词合并掩盖规则路径 | 桜の花・11階・600円・おすすめ観光地 为单一词典 token | 规则/分解另辟预处理路径（`no_compound` 的整词分解即此类）；不要把规则调到能"改词典整词" |

### 3.2 长音/促音表记（ー vs ウ/イ）

- 输出表记约定：**长音以「ー」书写**——`ショージョ`・`ジューガツ`・`ウツクシー`・`ホーソー`；词典个别条目存 `ウ/イ`（如 10月=ジュウガツ）时按需入修正表。
- `後宮：コーキュー`／`では：デワ` 等表记与用户参照样例的 `コーキュウ`／`デハ` 存在**可接受差异**（用户已确认以引擎输出为准）——此类差异应**记录在用例注释**中，不要为此改动 `は→ワ` 等全局规则。
- 促音规则有**慣用例外**（10月＝ジューガツ、10時＝ジュージ；表 `numeral_util.SOKUON_EXCEPTIONS`）。

### 3.3 复合与単位边界

- **数词不黏合普通名词**：含阿拉伯数字的表記（10月・2日）与后续名词是独立単位；汉字数词＋助数詞（〜本/人/階）可复合。
- **后部≥5拍不合并**（中国｜南東部）；**人名＋肩書き** 2単位；**带调型接頭辞**（第）独立成単位、无调型接頭辞（お）并入。
- 补助动词并入规则：名詞＋し/する；〜て＋いる 类并入；**命令形补助动词（ください）独立**；終助詞永远独立并入前部但**不参与 F 规则**。
- 定型复合 `そういう→ソーユー━`（`R-UNIT-JOIN`）。

### 3.4 人工修正指令（Correction Directives）的解析流程

用户给出「输入 + 预期输出 + 备注」时的标准流程：

1. **逐単位对齐**：预期输出按 `・` 切分，与 `show_accent` 输出逐単位比对，先区分
   「単位切分差异」与「调型/表记差异」（单位数不同时不要被错位吓到，按内容对齐）。
2. **差异归类**（决定修改层级）：
   - 分词/合并问题 → 预处理（resegment/numeral/compound_verb/no_compound）或复合/単位规则；
   - 词典值/表记问题 → `homograph_overrides`（最小、可追）；
   - 规则公式问题 → 对应规则模块（保持 source_ref 注释与 NHK 依据）；
   - 优先级问题 → `rules_config.json`。
3. **最小修正原则**：优先修正表>预处理>规则；**不得为单案例破坏既有 NHK 规则**——修完后全量 selfcheck 必须零回归。
4. **用户确认的例外**：若用户明确某差异"没问题"，**记录在用例注释并保留引擎行为**，不强行对齐字符串。
5. **钉死**：新参照句加入 `test_sentences.txt` 与 `selfcheck.check_reference_sentences`（逐字断言＋注释说明新增规则/例外）。
6. **提交**：Conventional Commits（scope `unidic`），逐字对齐结果与修正项写入 commit message。

### 3.5 其他常见坑

- `TEST_SAVE_PATH` 含反斜杠（`fast-api\audio\`），Linux 下必须归一化。
- MeCab feature 为 **26 列 CSV**，含被引号包裹的逗号字段（aConType）——必须用 `csv.reader` 拆。
- 修饰型 M4（れ/せる 等）与 F3 的**双路径**：M4 前部置平＋公式；F3 尾高保持——修改其一务必回归另一个（許され vs 描かれ）。
- 非自立動詞零化**仅限补助用法**（前接 助動詞 或 て/で）；主用言用法保留（来た・ナ＼ッタリ）。
- 引擎渲染（`rule_report.result`）与 `show_accent` 必须同源同规则；`show_accent` 须渲染**全部**下降核（勿只取首核）。

---

## 4. Testing & Verification Protocols（测试与验证规范）

### 4.1 运行测试

```bash
cd Utaer/functions/unidic
python3 selfcheck.py          # 全量回归（200+ 项）；输出「自检结束：全部通过 ✓」为健康状态
python3 init.py --text "米を盛る"                    # CLI 冒烟
python3 init.py --input test_sentences.txt           # 20 句语料批跑
```

- `test_sentences.txt`：开发期语料（每行一句，UTF-8），含全部历史修正句；
- `selfcheck.check_reference_sentences`：四组用户参照长例句**逐字钉死**（句1 21/21、句2 29/29、
  句3 10/10、句4 25/25），任何逻辑改动若破坏其中任一句即视为回归；
- 产物校验：`python3 -m json.tool fast-api/audio/<user>/<audio-id>/audio_accent.json`。

### 4.2 新增修正指令的验收标准

1. 目标句 `show_accent` 输出与用户预期**逐単位一致**（用户确认的例外除外，须注释在案）；
2. `python3 selfcheck.py` **全绿**（全部历史用例零回归）；
3. 新增/调整的规则带 `source_ref`（用户规则亦注明"用户确认"）；
4. commit message 含：修正项清单、对齐结果（n/n）、回归结论。

### 4.3 参照例句现状（钉死于 selfcheck）

| 句 | 内容摘要 | 结果 |
|---|---|---|
| 句1 | 廈門（アモイ）は、中国南東部の…10選をご紹介します… | 21/21（含 ジュ＼ッセンオ 数词读法） |
| 句2 | 今回の大会に関しては…大変でした（笑）。 | 29/29 |
| 句3 | あの、揺れる世界に…救ってください | 10/10 |
| 句4 | TVアニメ『薬屋のひとりごと』第3期が10月2日より…描かれた。 | 25/25（コーキュー/デワ 为确认可接受差异） |

已知边界：NHK Ⅱ 助数詞一覧表（259项）未在仓库，21–99 的 2単位形与各助数詞调型明细待补；
形状詞等个别词类接续按已确认范围实现。

---

# 第二部分：模块协作准则（原 `AGENT.md` 契约全文，保留）

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

> 注：上表为契约基线；实际模块已扩展出预处理与工具文件（`env_util`、`mora_util`、`ruby_util`、
> `resegment`、`numeral`、`numeral_util`、`compound_verb`、`no_compound`、`selfcheck`），
> 详见第一部分 §1.2。

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
