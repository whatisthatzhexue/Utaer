# tdmelodic 使用教程

> 本教程讲解 tdmelodic 的两种使用方式：组合词典调用（宿主）与声调预测（容器/HTTP），并说明输出格式与参数含义。

## 1. 文档简介

本教程是可选阅读（不启动项目也够用）。如果你已完成 `tdmelodic 配置教程.md`，且文件位置符合路径约定，可按需了解：

- **组合词典调用**：用宿主安装的 UniDic-tdmelodic 组合词典解析文本，得到整词调型（3.1、3.2）；
- **声调预测**：用容器内的 tdmelodic 工具对未收录词推断读音与声调（3.3）；
- **HTTP / Python 调用**：本项目中 `td_service.py` 与 `init.py` 的实际调用方式（3.4、3.5）。

建议阅读顺序：`tdmelodic 配置教程.md` → 本教程（可选）→ `本项目配置教程.md` → `本项目 unidic_and_f0 部分启动教程.md`。

## 2. 前置条件

### 2.1 环境与软件要求

| 用法 | 前置条件 |
|---|---|
| 组合词典调用（3.1） | 宿主已安装组合词典 `$(mecab-config --dicdir)/tdmelodic`（配置教程 3.16） |
| 声调预测（3.3） | 已构建镜像 `tdmelodic:latest`（配置教程 3.8） |
| HTTP 调用（3.4） | 已启动 tdmelodic_service 容器（见启动教程） |
| Python 绑定调用（3.5） | 宿主已安装 mecab-python3（见本项目配置教程） |

### 2.2 术语约定

- **表記形（surface）**：文本中出现的原始写法，如「一昔」。
- **読み（yomi）**：辞书式读音，如「ヒトムカシ」。
- **発音（hatsuon）**：实际发音，可能含有アクセント核标记 `[ ]`，如「ジ[ンコーチ]ノー」。
- **アクセント（accent）**：声调/音调调型，数字表示（0=平板型，N=第N拍下降）。
- **アクセント核**：音高开始下降位置的前一拍，`[ ]` 括起的部分。

### 2.3 前置文档依赖

- `tdmelodic 配置教程.md`（必读前置）。
- 项目总规范 `AGENTS.md` §7.4（`audio_accent.json` 的 `accent`/`variants` 字段含义）。

## 3. 核心步骤

### 3.1 组合词典调用（宿主）

在 WSL 宿主中执行（无需容器）：

```bash
echo 一昔前は人工知能のプログラミング言語といえばCommon LispやPrologだった。 | \
    mecab -d `mecab-config --dicdir`/tdmelodic/
```

预期输出结果：

```text
一昔	ヒトムカシ	ヒトムカシ	一昔	名詞-普通名詞-一般			2,3
前	マエ	マエ	前	名詞-普通名詞-副詞可能			1
は	ワ	ハ	は	助詞-係助詞
人工知能	ジ[ンコーチ]ノー	ジンコウチノウ	人工知能	名詞-固有名詞-一般			@
の	ノ	ノ	の	助詞-格助詞
プログラミング言語	プ[ログラミングゲ]ンゴ	プログラミングゲンゴ	プログラミング言語	名詞-固有名詞-一般			@
と	ト	ト	と	助詞-格助詞
いえ	イエ	イウ	言う	動詞-一般	五段-ワア行	仮定形-一般	0
ば	バ	バ	ば	助詞-接続助詞
Common Lisp	コ[モンリ]スプ	コモンリスプ	Common Lisp	名詞-固有名詞-一般			@
や	ヤ	ヤ	や	助詞-副助詞
Prolog	プ[ロログ	プロログ	Prolog	名詞-固有名詞-一般			@
だっ	ダッ	ダ	だ	助動詞	助動詞-ダ	連用形-促音便
た	タ	タ	た	助動詞	助動詞-タ	終止形-一般
。			。	補助記号-句点
EOS
```

> **说明**：输出中「人工知能」「プログラミング言語」「Common Lisp」「Prolog」作为**整词**返回，这正是配置教程第二阶段生成的大音调词典的效果。

### 3.2 输出字段解读

每行按 Tab 分隔，列为：

| 列 | 含义 | 示例（「いえ」行） |
|---|---|---|
| 1 表層形 | 文本中的原始写法 | いえ |
| 2 発音 | 实际发音，`[ ]` 标记アクセント核 | イエ |
| 3 読み | 辞书式读音 | イウ |
| 4 原型 | 辞书形 | 言う |
| 5 品詞 | 词性 | 動詞-一般 |
| 6 活用型 | 活用类型（无则空） | 五段-ワア行 |
| 7 活用形 | 活用形（无则空） | 仮定形-一般 |
| 8 アクセント | 调型数字或推断标记 | 0 |

关于第 8 列（アクセント）：

- **数字**：词典收录的调型。`0` = 平板型；`N` = 第 N 拍下降（对应 `audio_accent.json` 的 `accent` 字段）。
- **逗号分隔的数字**（如「一昔」的 `2,3`）：该词有多个候选调型（对应 `audio_accent.json` 的 `variants` 字段）。
- **`@`**：该词条词典未收录，声调由推断补充（如「人工知能」「Common Lisp」行）；此时调型以第 2 列発音中的 `[ ]` 标记表示。

### 3.3 声调预测模式（容器）

无需宿主词典，直接调用镜像内工具：

```bash
# 这个是根据表記形生成読み + 音調
echo 機械学習 | docker run -i --rm tdmelodic:latest tdmelodic-s2ya
# 这个是根据表記形和読み生成音調
echo 御御御付け,おみおつけ | docker run -i --rm tdmelodic:latest tdmelodic-sy2a
```

> **说明**：`tdmelodic-s2ya` 的输入为表記形，输出为该词的読み + 音调；`tdmelodic-sy2a` 的输入为「表記形,読み」（逗号分隔），输出为该词音调。模块总文档未给出这两个命令的预期输出样例，以实际运行结果为准。

### 3.4 HTTP 服务调用（基于 td_service.py）

先按 `本项目 unidic_and_f0 部分启动教程.md` 启动 tdmelodic_service 容器，然后：

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"texts": ["機械学習", "深層学習"]}'
```

返回：

```jsonc
{"results": ["...", "..."]}
// results 逐条对应 texts，内容为 tdmelodic-s2ya 的输出
```

Python 调用示例（对应 `init.py` 中 `predict_batch` 的写法）：

```python
import json
from urllib.request import Request, urlopen

def predict_batch(text_list, url="http://localhost:8000"):
    data = json.dumps({"texts": text_list}).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})

    with urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["results"]

print(predict_batch(["私は歌を歌うのが好きです。", "なんでこんな目で見てるの"]))
```

### 3.5 Python 绑定调用（mecab-python3，基于 init.py）

在宿主上通过 mecab-python3 调用组合词典：

```python
import subprocess
import MeCab

def load_t():
    dic_base = subprocess.check_output(["mecab-config", "--dicdir"], text=True).strip()
    dic_path = f"{dic_base}/tdmelodic"
    return dic_path

# 使用 MeCab
tagger = MeCab.Tagger(f"-d {load_t()}")
text = "一昔前は人工知能のプログラミング言語といえばCommon LispやPrologだった。"
print(tagger.parse(text))
```

输出与 3.1 的命令行结果格式完全一致。

### 3.6 参数说明

| 参数 / 工具 | 说明 |
|---|---|
| `-d <词典路径>` | 指定 MeCab 使用的词典目录 |
| `-m unidic` | `tdmelodic-convert` 的词典模式（按 UniDic 推断） |
| `--input <文件>` / `--output <文件>` | 推断工具（`tdmelodic-neologd-preprocess`、`tdmelodic-convert`）的输入/输出文件 |
| `--no-rmdups` | 预处理时不过滤重复词条 |
| `--no-rm_wrong_yomi` | 预处理时不过滤读音错误的词条 |
| `tdmelodic-s2ya` | 表記形 → 読み + 音调（surface → yomi & akusento） |
| `tdmelodic-sy2a` | 表記形 + 読み → 音调（surface & yomi → akusento） |

## 4. 验证方式

### 4.1 词典调用验证

与 3.1 预期输出逐字对照，重点确认「人工知能」「プログラミング言語」作为整词返回。

### 4.2 预测模式验证

`tdmelodic-s2ya` / `tdmelodic-sy2a` 对输入行逐行返回预测结果，无报错即可。

### 4.3 HTTP 调用验证

返回的 `results` 条数与 `texts` 条数一致，且每条为对应文本的预测结果。

### 4.4 Python 绑定验证

3.5 的 `parse()` 输出与 3.1 的命令行输出一致。

## 5. 常见问题 / 排错

| 症状 | 原因 | 解决方案 |
|---|---|---|
| `-d` 指定的词典路径不存在 | 组合词典未安装 | 完成配置教程 3.16；用 `ls $(mecab-config --dicdir)` 确认包含 `tdmelodic` |
| `tdmelodic-s2ya: command not found` 或镜像不存在 | 镜像未构建 | 完成配置教程 3.8 |
| 词典调用与预测结果不一致 | 前者来自大词典收录词条，后者由模型推断 | 属正常差异；项目侧未收录词需在 notes 标注「词典未收录」（总 AGENTS.md §9） |
| アクセント列为 `@` | 该词词典未收录、声调由推断补充 | 正常现象，见 3.2 |
| HTTP 连接被拒 | tdmelodic_service 容器未启动 | 见启动教程步骤 3 |

## 附录：参考链接

- 模块总文档：`unidic_and_f0总文档.txt`（项目根目录）
- 本系列：`tdmelodic 配置教程.md`、`本项目配置教程.md`、`本项目 unidic_and_f0 部分启动教程.md`、`AGENT.md`
- tdmelodic 官方教程（日文）：https://tdmelodic.readthedocs.io/ja/latest/pages/introduction.html
- tdmelodic：https://github.com/PKSHATechnology-Research/tdmelodic
