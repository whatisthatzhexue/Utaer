# ENGINE_USAGE.md — 音调引擎服务接口（唯一入口 `analyze_text`）

> **受众**：基于本引擎搭建 HTTP 服务的工程师。本文件**自包含**——不需要阅读引擎源码。
>
> **冻结声明**：本文件是音调引擎对服务层的**唯一接口契约**。服务层只允许通过
> `analyze_text` 一个函数调用引擎。契约版本 **1.0**（与输出 `version` 字段对应）；
> 字段增删或语义变更时将升版并更新本文件。
>
> 说明：《前端声调信息传输规范》为项目待发布文档；在其发布前，**本文件 §2/§3
> 即当前生效的输出契约**（字段与既有 `audio_accent.json` 格式对齐并扩展音拍级 H/L）。
> 规范发布后如有字段差异，引擎按规范更新本文件并升版，服务层以 `version` 字段为准。

---

## 1. 唯一入口函数（服务层只允许调用这一个函数）

```python
def analyze_text(text: str) -> dict:
    """
    输入：原始日语文本（可含标点、换行）
    输出：符合《前端声调信息传输规范》的 dict（含 text + tokens）
    内部完成：MeCab 分词 → UniDic 调型 → 规则引擎推导 → 音拍级 H/L 展开
    """
```

### 导入与调用

```python
import sys
sys.path.insert(0, "/home/rainybread/Utaer/functions/unidic")   # 引擎模块目录（按实际部署路径替换）
from pipeline import analyze_text

result = analyze_text("米を盛る")
```

### 硬性约束

1. **服务层只允许调用 `analyze_text`**（不得调用引擎内其他函数/模块——其余函数均为内部实现，随时可能变动）；
2. **确定性**：同一输入必得同一输出。引擎为纯确定性管线（词典确切匹配＋条件规则），
   **不做任何调型推测**（不使用机器学习/统计推断）；
3. **线程安全**：引擎内部对共享 MeCab 解析器加进程内锁，多线程/协程并发调用安全
   （并发请求被串行化执行，单请求耗时毫秒级）；追求更高吞吐时可多进程部署（每进程独立引擎）；
4. **预热**：首次调用会初始化词典解析器（约百毫秒级）。建议服务启动时以
   `analyze_text("テスト")` 预热一次，失败则拒绝启动。

---

## 2. 输出结构（完整字段规范）

### 2.1 顶层

| 字段 | 类型 | 说明 |
|---|---|---|
| `version` | string | 契约版本（当前 `"1.0"`） |
| `text` | string | 原始输入文本（**原样保留**，含换行） |
| `tokens` | array | 形态素列表（按出现顺序；多行输入为全句连续序号） |

### 2.2 token 字段

| 字段 | 类型 | 必有 | 说明 |
|---|---|---|---|
| `idx` | int | ✓ | 序号，从 0 起（多行输入全句连续） |
| `morph` | string | ✓ | 表記形（显示用原文写法） |
| `lemma` | string | ✓ | 辞書形 |
| `morph_reading` | string | ✓ | 发音（片假名）；标点等无读音时为 `""` |
| `pos` | string | ✓ | 词性，层级以 `*` 分隔（如 `名詞*普通名詞*一般`） |
| `accent` | int | ✓ | **声调核位置**：`0`=平板型；`N`=第 N 拍后下降（东京式；单位内位置） |
| `variants` | int[] | ✓ | 词典多调型的其余值（首个为主值；无变体时 `[]`） |
| `ruby_pairs` | array | ✓ | 振假名对齐 `[[表記, かな], …]`；首元素 `null` 表示该读音片段无对应表记 |
| `moras` | string[] | ✓ | 音拍切分（拗音并入前拍；`ー`/`ン`/`ッ` 各计 1 拍；标点为 `[]`） |
| `pitch` | string[] | ✓ | **音拍级 H/L**（与 `moras` 一一对应；标点为 `[]`；展开规则见 §3） |
| `unit` | int | ✓ | 所属**アクセント単位**编号（0 起；多行输入全句连续） |
| `notes` | string[] | 可选 | 仅特殊情形出现（如 `["词典未收录"]`） |

### 2.3 完整输出示例

`analyze_text("米を盛る")` 的真实返回（逐字）：

```json
{
  "version": "1.0",
  "text": "米を盛る",
  "tokens": [
    {
      "idx": 0, "morph": "米", "lemma": "米", "morph_reading": "コメ",
      "pos": "名詞*普通名詞*一般", "accent": 2, "variants": [],
      "ruby_pairs": [["米", "こめ"]],
      "moras": ["コ", "メ"], "pitch": ["L", "H"], "unit": 0
    },
    {
      "idx": 1, "morph": "を", "lemma": "を", "morph_reading": "オ",
      "pos": "助詞*格助詞", "accent": 0, "variants": [],
      "ruby_pairs": [[null, "を"]],
      "moras": ["オ"], "pitch": ["L"], "unit": 0
    },
    {
      "idx": 2, "morph": "盛る", "lemma": "盛る", "morph_reading": "モル",
      "pos": "動詞*一般", "accent": 0, "variants": [],
      "ruby_pairs": [["盛", "も"], ["る", "る"]],
      "moras": ["モ", "ル"], "pitch": ["L", "H"], "unit": 1
    }
  ]
}
```

读法：`米を`（unit 0）＝核在第 2 拍后下降（`コメ＼オ`，H/L 展开 `L H L`）；
`盛る`（unit 1）＝平板型（`モル━`，`L H`）。多单位句按 `unit` 分组即可还原全句曲线。

---

## 3. 音拍级 H/L 展开规则（冻结）

1. **以アクセント単位（`unit`）为单位**计算：同一 `unit` 内所有 token 的 `moras`
   拼接后共享一条**连续**曲线，再按 token 切回各自的 `pitch` 数组；
2. 每个単位**独立重置**（単位与単位之间不连续）；
3. 単位内下降核位置记为 F（1 起，即 `accent` 所落形态素的核拍在单位内的全局拍序）：

| 单位内情况 | 展开 |
|---|---|
| 无核（平板型） | 第 1 拍 `L`，其余全部 `H` |
| F = 1（頭高型） | 第 1 拍 `H`，其余全部 `L` |
| 2 ≤ F ≤ 拍数 | 前 F 拍为 `L H … H`，其后全部 `L` |
| F = 拍数（尾高型） | 单位内呈现 `L H … H`（下降由后续付属語的 `L` 显现——引擎已把付属語并入同一 unit） |

4. **标点等无读音形态素**：`moras` 与 `pitch` 均为 `[]`，`unit` 跟随其所属単位。

### 展开示例（记号 ↔ token 的 H/L）

| NHK 记号（下がり目式） | unit 内 H/L | token 切回 |
|---|---|---|
| `コメ＼オ`（米を，尾高＋助詞） | `L H L` | 米 `[L,H]` / を `[L]` |
| `モル━`（盛る，平板） | `L H` | 盛る `[L,H]` |
| `ア＼メガ`（雨が，頭高） | `H L L` | 雨 `[H,L]` / が `[L]` |
| `ガクセイデ＼ス`（学生です） | `L H H H H L` | 学生 `[L,H,H,H]` / です `[H,L]` |
| `トーキョ＼ーエキ`（東京駅） | `L H H L L L` | 東京駅 `[L,H,H,L,L,L]` |

---

## 4. `accent` 数值 ↔ 型名（供服务侧/前端换算）

| `accent` | 型 | 含义 |
|---|---|---|
| `0` | 平板型 | 无下降核 |
| `1` | 頭高型 | 第 1 拍后下降 |
| `N`（0 < N < 拍数） | 中高型 | 第 N 拍后下降 |
| `N` = 拍数 | 尾高型 | 末拍后下降（接付属語时核显现） |

（拍数 = 该 token 的 `moras` 长度；单位整体渲染可使用 §3 的 `pitch`。）

---

## 5. 输入语义与边界

| 输入 | 行为 |
|---|---|
| 单行文本 | 直接分析 |
| **含换行** | **行 = 句**：逐行独立分析后合并 `tokens`（行间不复合、不跨行连接単位）；`idx` 与 `unit` 全句连续；`text` 原样返回 |
| 含标点 | 正常参与分析：标点并入前一アクセント単位（`pitch`/`moras` 为空数组） |
| 空串 / 全空白 | **抛 `ValueError`** |
| 长度 | 无硬性上限，耗时随文本线性增长（建议单请求 ≤ 数百字） |

---

## 6. 错误处理

| 异常 | 触发条件 | 服务侧建议 |
|---|---|---|
| `ValueError` | 空文本 / 全空白 | 返回 400 |
| `Stage1Error`（`stage1_analyzer.Stage1Error`） | 组合词典缺失、MeCab 未安装 | 属部署错误：启动自检时暴露（返回 500 并告警） |

**部署前置**（一次性）：宿主 `mecab-python3` ＋ 组合词典
（安装步骤见同目录《本项目配置教程.md》《tdmelodic 配置教程.md》）。

---

## 7. 最小服务集成示例（FastAPI）

```python
import sys
sys.path.insert(0, "/home/rainybread/Utaer/functions/unidic")   # 按实际部署路径替换

from fastapi import FastAPI, HTTPException
from pipeline import analyze_text
from stage1_analyzer import Stage1Error

app = FastAPI()

# 启动预热（失败快速暴露部署问题）
try:
    analyze_text("テスト")
except Exception as exc:      # Stage1Error 等
    raise RuntimeError(f"音调引擎初始化失败：{exc}")

@app.get("/accent")
def accent(text: str):
    try:
        return analyze_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Stage1Error as exc:          # 理论上预热后不再出现
        raise HTTPException(status_code=500, detail=str(exc))
```

---

## 8. 行为保证（可依赖的冻结承诺）

1. **确定性**：同输入必得同输出（无随机、无统计/机器学习推断、不调用任何调型推测功能）；
2. **词典确切匹配优先**：调型来源为组合词典（UniDic＋大音调词典，含推断条目的
   发音标记解码），规则引擎仅做确定性推导与校验；
3. **可追溯**：每条推导都有内置依据（规则的 source_ref 指向 NHK 辞典规则/UniDic 手册
   章节），异常排查由引擎侧负责，服务侧无需理解细节；
4. **契约版本**：`version` 字段标识输出结构版本；**同版本内只做向后兼容的字段追加**，
   破坏性变更升版并更新本文件；服务侧可在响应中透传 `version` 以便前端适配。

---

## 附录 A：人工自测（不写代码）

```bash
cd /home/rainybread/Utaer/functions/unidic

# 单句快速验证（打印完整 JSON）
python3 -c "from pipeline import analyze_text; import json; print(json.dumps(analyze_text('米を盛る'), ensure_ascii=False, indent=2))"

# 引擎全量自检（含服务契约断言；应打印「全部通过」）
python3 selfcheck.py
```

引擎另有命令行工具与离线产物（`audio_accent.json` / `rule_report.json`，含逐条规则依据），
供人工核对使用；**服务化场景一律以 `analyze_text` 的输出契约为准**。

## 附录 B：常见问题

| 问题 | 处理 |
|---|---|
| 某词读音/调型与预期不符 | 属引擎侧词典条目问题（引擎维护者通过内置修正表维护），**服务侧无需处理**，请反馈给引擎维护者 |
| 高并发下耗时上升 | 引擎内部串行化（MeCab 非线程安全）；建议多进程部署（每进程独立引擎实例） |
| 需要整句的 NHK 记号（`＼`/`━`/`・`） | 由 `pitch`/`unit` 可还原（§3）；如需字符串记号可向引擎维护者提出接口扩展 |
| 前端要画音高曲线 | 直接用 `moras` + `pitch`（按 `unit` 分组拼接），无需再做任何换算 |
