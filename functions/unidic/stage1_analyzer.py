"""阶段一：tdmelodic 组合词典基础分析（离线查表，确切匹配）。

契约（``AGENT.md`` 3.1 / 3.3 接口 1）：

- 使用宿主 ``mecab-python3`` + 组合词典 ``$(mecab-config --dicdir)/tdmelodic``
  做**确切匹配**的词法/声调基础分析；词典路径经 ``mecab-config --dicdir`` 动态拼接，
  禁止硬编码；
- **硬约束：禁止调型推测**——不调用 ``tdmelodic-s2ya`` / ``tdmelodic-sy2a``，
  不使用 ``td_service.py``（已退出分析链路）；
- 产出「资料一」：结构化形态素（表層形/発音/読み/原型/品詞/活用型/活用形/
  調型（数字或未收录标记）/拍数），供阶段二规则引擎（``stage2_rules``）使用；
  另附 UniDic 原生字段 ``goshu``（語種）、``a_con_type``（アクセント結合型 C1–C5/F 系列）、
  ``a_mod_type``（アクセント修飾型 M 系列）——即「资料二」UniDic 手册规则的词典原生依据。

运行期 feature 列序（实测核对，共 26 个逗号分隔字段）::

    f[0..3]  品詞・品詞細分類1-3      → pos（以 ``-`` 连接、忽略 ``*``）
    f[4]     活用型                   → conj_type
    f[5]     活用形                   → conj_form
    f[6]     読み                     → reading
    f[7]     語彙素（原形）            → lemma
    f[8]     語彙素表記
    f[9]     発音                     → pron / pron_raw
    f[10]    語彙素表記（基底）
    f[11]    発音（基底）
    f[12]    語種（漢/和/固/外…）      → goshu
    f[23]    アクセント型              → accent_raw（数字 / 逗号多调型 / @）
    f[24]    アクセント結合型（C1–C5 等）→ a_con_type
    f[25]    アクセント修飾型（M1@M 等）→ a_mod_type

控制台展示行按契约投影为 8 列：表層形/発音/読み/原型/品詞/活用型/活用形/調型。

「調型」列取值：数字（``0``=平板、``N``=第 N 拍后下降）、逗号分隔多调型（如 ``0,1``）、
``@``（大音调词典未收录）、空串（付属語等无固有调型）。

``@`` 的处理（关键，依据见 :func:`mora_util.decode_bracket_accent`）：
大音调词典推断词条会把声调编码进「発音」字段的 ``[]`` 标记（``]`` 所在拍即声调核）。
「``@`` + ``[]``」的词**不是**无音调——解码后按词典确切匹配直取
（``accent_source="bracket"``，``is_unknown=False``）；
只有「``@`` 且无括号」才是真正未收录（``accent_source="unknown"``），
交由阶段二兜底规则处理（禁止用 s2ya 推测补齐）。

同形語修正表（``homograph_overrides``，位于 ``rules_config.json``）：
对组合词典与项目验收样例不一致的词做**确定性显式覆盖**
（如 米→コメ/2、盛る→0），不引入任何推测；覆盖后 ``accent_source="homograph"``。
"""

from __future__ import annotations

import argparse
import csv
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mora_util

logger = logging.getLogger(__name__)

#: MeCab 节点类型（mecab-python3 常量）
_MECAB_NOR_NODE = 0
_MECAB_UNK_NODE = 1
_MECAB_BOS_NODE = 2
_MECAB_EOS_NODE = 3

#: 运行期 feature（26 个逗号分隔字段）中的关键列索引——已用 --dump 实测核对
FEATURE_POS_INDICES = (0, 1, 2, 3)   # 品詞・品詞細分類1-3
FEATURE_CONJ_TYPE = 4                # 活用型
FEATURE_CONJ_FORM = 5                # 活用形
FEATURE_READING = 6                  # 読み
FEATURE_LEMMA = 7                    # 語彙素（原形）
FEATURE_PRON = 9                     # 発音
FEATURE_GOSHU = 12                   # 語種
FEATURE_ACCENT_TYPE = 23             # アクセント型（aType）
FEATURE_ACCENT_CON_TYPE = 24         # アクセント結合型（aConType，如 C3/C4）
FEATURE_ACCENT_MOD_TYPE = 25         # アクセント修飾型（aModType，如 M1@M）
FEATURE_FIELD_COUNT = 26

#: 声调来源标记（写入 :class:`Morph.accent_source`，供规则报告生成 logic 文案）
ACCENT_SOURCE_ATYPE = "atype"        # 词典 aType 列直接给出数字
ACCENT_SOURCE_BRACKET = "bracket"    # @ 词经「発音」字段 [] 标记解码
ACCENT_SOURCE_HOMOGRAPH = "homograph"  # 同形語修正表覆盖
ACCENT_SOURCE_EMPTY = "empty"        # 词典收录但无固有调型（付属語等）
ACCENT_SOURCE_UNKNOWN = "unknown"    # 真未收录（@ 且无括号）


class Stage1Error(RuntimeError):
    """阶段一错误（词典缺失、MeCab 初始化失败等）。"""


@dataclass(frozen=True)
class Morph:
    """「资料一」形态素（不可变；阶段二拷贝为可变工作状态）。

    ``pron`` 为去括号的干净发音（拍数计算与渲染依据）；
    ``pron_raw`` 为词典原始発音（可能含 ``[]`` 标记，用于阶段一原始解析展示）。
    """

    idx: int
    morph: str          # 表層形
    lemma: str          # 原型
    reading: str        # 読み（注音基础）
    pron: str           # 発音（已去除 [] 标记）
    pron_raw: str       # 词典原始発音（可能含 [] 标记）
    pos: str            # 品詞（``-`` 分隔，如 名詞-普通名詞-一般）
    conj_type: str      # 活用型（无则空串）
    conj_form: str      # 活用形（无则空串）
    accent_raw: str     # 調型：数字 / 逗号分隔多调型 / ""（无固有调型）/ "@"（未收录）
    mora_count: int     # 拍数（モーラ数）
    is_unknown: bool    # 真未收录（@ 且无括号标记）的归一化布尔值
    accent_source: str  # 声调来源（ACCENT_SOURCE_* 之一）
    goshu: str = ""         # 語種（漢/和/固/外…；用于兜底规则的語種倾向表）
    a_con_type: str = ""    # アクセント結合型（资料二 C1–C5 / F 系列；复合词规则依据）
    a_mod_type: str = ""    # アクセント修飾型（资料二 M 系列；活用形规则依据）


@dataclass(frozen=True)
class Stage1Result:
    """阶段一结果：资料一形态素序列 + 原始解析展示行。"""

    input: str
    morphs: tuple[Morph, ...]
    raw_lines: tuple[str, ...]


def _import_mecab() -> Any:
    """延迟导入 MeCab（mecab-python3），失败时给出安装指引。"""
    try:
        import MeCab  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - 环境缺失时的兜底
        raise Stage1Error(
            "未安装 mecab-python3：请执行 `pip install mecab-python3`"
            "（并确保已安装 libmecab-dev，见《本项目配置教程.md》3.2/3.3）"
        ) from exc
    return MeCab


def get_tdmelodic_dic_path() -> Path:
    """返回组合词典路径 ``$(mecab-config --dicdir)/tdmelodic``。

    :raises Stage1Error: ``mecab-config`` 不可执行或组合词典目录不存在。
    """
    try:
        dic_base = subprocess.check_output(
            ["mecab-config", "--dicdir"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Stage1Error(
            "无法执行 `mecab-config --dicdir`：请确认宿主已安装 mecab / libmecab-dev"
            "（见《本项目配置教程.md》3.3）"
        ) from exc
    dic_path = Path(dic_base) / "tdmelodic"
    if not dic_path.is_dir():
        raise Stage1Error(
            f"组合词典目录不存在：{dic_path}——"
            "请按《tdmelodic 配置教程.md》3.16 安装组合词典"
        )
    return dic_path


_TAGGER_CACHE: dict[str, Any] = {}


def build_tagger(dic_path: Path | str | None = None) -> Any:
    """构建（并缓存）指向组合词典的 MeCab Tagger。

    同一进程内按词典路径缓存，避免重复初始化。
    """
    path = str(dic_path) if dic_path is not None else str(get_tdmelodic_dic_path())
    if path not in _TAGGER_CACHE:
        mecab = _import_mecab()
        try:
            _TAGGER_CACHE[path] = mecab.Tagger(f"-d {path}")
        except Exception as exc:  # MeCab 抛出的是通用 Exception
            raise Stage1Error(f"MeCab 初始化失败（词典：{path}）：{exc}") from exc
    return _TAGGER_CACHE[path]


@dataclass(frozen=True)
class _FeatureFields:
    """从 26 列 feature 中提取的关键字段（``*`` 已归一化为空串）。"""

    pron: str
    reading: str
    lemma: str
    pos: str
    conj_type: str
    conj_form: str
    a_type: str
    goshu: str
    a_con_type: str
    a_mod_type: str


def _split_feature(feature: str) -> _FeatureFields:
    """按实测 26 列布局拆分 MeCab feature；``*`` 归一化为空串。

    品詞取 f[0..3]，忽略空值与 ``*``，以 ``-`` 连接（资料一约定，
    如 ``名詞-普通名詞-一般`` / ``助詞-格助詞``）。

    注意：部分字段（如 aConType ``"動詞%F2@0,名詞%F1"``）含逗号并被 MeCab
    以双引号包裹，故用 :mod:`csv` 做引号感知拆分，而非朴素 ``str.split``。
    """
    parts = next(csv.reader([feature]))

    def field(index: int) -> str:
        value = parts[index] if index < len(parts) else ""
        return "" if value == "*" else value

    pos = "-".join(value for value in (field(i) for i in FEATURE_POS_INDICES) if value)
    return _FeatureFields(
        pron=field(FEATURE_PRON),
        reading=field(FEATURE_READING),
        lemma=field(FEATURE_LEMMA),
        pos=pos,
        conj_type=field(FEATURE_CONJ_TYPE),
        conj_form=field(FEATURE_CONJ_FORM),
        a_type=field(FEATURE_ACCENT_TYPE),
        goshu=field(FEATURE_GOSHU),
        a_con_type=field(FEATURE_ACCENT_CON_TYPE),
        a_mod_type=field(FEATURE_ACCENT_MOD_TYPE),
    )


def _resolve_accent(pron_raw: str, a_type: str) -> tuple[str, str, bool, str]:
    """解析调型，返回 ``(干净发音, accent_raw, is_unknown, accent_source)``。

    规则（与模块 docstring 一致）：

    - ``a_type`` 为数字/逗号多调型 → 直取（``atype``）；
    - ``a_type == "@"`` 且発音含 ``[]`` 标记 → 解码为核位置（``bracket``，非未收录）；
    - ``a_type == "@"`` 且无标记 → 真未收录（``unknown``）；
    - ``a_type`` 为空 → 无固有调型（``empty``，如付属語）。
    """
    if a_type == "@":
        clean, decoded, had_brackets = mora_util.decode_bracket_accent(pron_raw)
        if had_brackets and decoded is not None:
            return clean, str(decoded), False, ACCENT_SOURCE_BRACKET
        return mora_util.strip_brackets(pron_raw), "@", True, ACCENT_SOURCE_UNKNOWN
    if a_type:
        return mora_util.strip_brackets(pron_raw), a_type, False, ACCENT_SOURCE_ATYPE
    return mora_util.strip_brackets(pron_raw), "", False, ACCENT_SOURCE_EMPTY


def _build_morph(
    surface: str,
    fields: _FeatureFields | None,
    idx: int,
    is_mecab_unknown: bool,
    overrides: dict[str, dict[str, Any]],
) -> Morph:
    """由 MeCab 字段组装单个 :class:`Morph`（含调型解析与同形語覆盖）。"""
    if is_mecab_unknown or fields is None:
        # MeCab 分词失败（词典亦未收录）：仅保留表層形；读音仅在可假名化时保留
        kana_surface = surface if all(
            mora_util.is_katakana(ch) or 0x3041 <= ord(ch) <= 0x3096 for ch in surface
        ) else ""
        morph = Morph(
            idx=idx, morph=surface, lemma=surface,
            reading=surface if kana_surface else "",
            pron=kana_surface, pron_raw=kana_surface, pos="未知語",
            conj_type="", conj_form="",
            accent_raw="@", mora_count=mora_util.mora_count(kana_surface),
            is_unknown=True, accent_source=ACCENT_SOURCE_UNKNOWN,
        )
    else:
        pron, accent_raw, is_unknown, accent_source = _resolve_accent(fields.pron, fields.a_type)
        morph = Morph(
            idx=idx, morph=surface, lemma=fields.lemma or surface,
            reading=fields.reading,
            pron=pron, pron_raw=fields.pron, pos=fields.pos,
            conj_type=fields.conj_type, conj_form=fields.conj_form,
            accent_raw=accent_raw, mora_count=mora_util.mora_count(pron),
            is_unknown=is_unknown, accent_source=accent_source,
            goshu=fields.goshu, a_con_type=fields.a_con_type, a_mod_type=fields.a_mod_type,
        )

    # 同形語修正表（确定性显式覆盖，优先级最高）
    override = overrides.get(surface)
    if isinstance(override, dict):
        reading = str(override.get("reading", morph.reading))
        pron_override = override.get("pron")
        pron = str(pron_override) if pron_override else morph.pron
        accent_raw = str(override["accent_raw"]) if "accent_raw" in override else morph.accent_raw
        pos = str(override["pos"]) if "pos" in override else morph.pos
        a_con_type = str(override["a_con_type"]) if "a_con_type" in override else morph.a_con_type
        morph = Morph(
            idx=morph.idx, morph=morph.morph, lemma=morph.lemma, reading=reading,
            pron=pron, pron_raw=str(pron_override) if pron_override else morph.pron_raw,
            pos=pos, conj_type=morph.conj_type, conj_form=morph.conj_form,
            accent_raw=accent_raw, mora_count=mora_util.mora_count(pron),
            is_unknown=False, accent_source=ACCENT_SOURCE_HOMOGRAPH,
            goshu=morph.goshu, a_con_type=a_con_type, a_mod_type=morph.a_mod_type,
        )
    elif override is not None:
        logger.warning("homograph_overrides[%s] 应为对象，已忽略", surface)
    return morph


def render_raw_line(morph: Morph) -> str:
    """渲染阶段一原始解析行（Tab 分隔 8 列，按契约投影，供控制台展示）。

    発音列：括号解码词显示词典原始発音（保留 ``[]``，便于核对来源），
    其余显示干净发音。
    """
    display_pron = morph.pron_raw if morph.accent_source == ACCENT_SOURCE_BRACKET else morph.pron
    return "\t".join([
        morph.morph, display_pron, morph.reading, morph.lemma, morph.pos,
        morph.conj_type, morph.conj_form, morph.accent_raw,
    ])


def parse_nodes(
    text: str,
    tagger: Any,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> tuple[Morph, ...]:
    """单遍遍历 MeCab 节点，组装 :class:`Morph` 序列（idx 从 0 起）。

    跳过 BOS/EOS 与纯空白节点。节点数据在遍历中即时提取（不保留节点引用）。
    """
    overrides = overrides or {}
    morphs: list[Morph] = []
    node = tagger.parseToNode(text)
    while node is not None:
        stat = node.stat
        surface = node.surface or ""
        if stat not in (_MECAB_BOS_NODE, _MECAB_EOS_NODE) and surface.strip():
            fields: _FeatureFields | None = None
            if stat != _MECAB_UNK_NODE:
                feature = node.feature or ""
                if feature and not feature.startswith("BOS/EOS"):
                    fields = _split_feature(feature)
            morphs.append(
                _build_morph(surface, fields, len(morphs), stat == _MECAB_UNK_NODE, overrides)
            )
        node = node.next
    return tuple(morphs)


def analyze(
    text: str,
    tagger: Any | None = None,
    homograph_overrides: dict[str, dict[str, Any]] | None = None,
) -> Stage1Result:
    """阶段一入口：精确查表分析 ``text``，返回「资料一」与展示行。

    :raises ValueError: 文本为空或全空白。
    :raises Stage1Error: 词典缺失或 MeCab 初始化失败。
    """
    if not text or not text.strip():
        raise ValueError("输入文本为空，无法进行阶段一分析")
    if tagger is None:
        tagger = build_tagger()
    morphs = parse_nodes(text, tagger, homograph_overrides)
    raw_lines = tuple(render_raw_line(m) for m in morphs) + ("EOS",)
    return Stage1Result(input=text, morphs=morphs, raw_lines=raw_lines)


def dump_raw_nodes(text: str, tagger: Any | None = None) -> list[str]:
    """调试辅助：逐节点打印 stat/surface/feature，用于人工核对列布局。"""
    if tagger is None:
        tagger = build_tagger()
    lines: list[str] = []
    node = tagger.parseToNode(text)
    while node is not None:
        lines.append(f"stat={node.stat}\tsurface={node.surface!r}\tfeature={node.feature!r}")
        node = node.next
    return lines


def _main(argv: list[str] | None = None) -> int:
    """自检入口：``python3 stage1_analyzer.py "米を盛る" [--dump]``。"""
    parser = argparse.ArgumentParser(
        description="阶段一：tdmelodic 组合词典基础分析（确切匹配，禁止调型推测）"
    )
    parser.add_argument("text", help="待分析文本")
    parser.add_argument("--dump", action="store_true", help="打印 MeCab 原始节点（列布局核对）")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    # 局部导入：自检入口读取同形語修正表；核心分析不依赖 env_util
    from env_util import load_rules_config

    config = load_rules_config()
    overrides = config.get("homograph_overrides", {})

    try:
        tagger = build_tagger()
        if args.dump:
            print("===== MeCab 原始节点（列布局核对用）=====")
            for line in dump_raw_nodes(args.text, tagger):
                print(line)
            print()
        result = analyze(args.text, tagger, overrides)
    except (Stage1Error, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print("===== 阶段一：词典基础分析（确切匹配，禁止推测）=====")
    for line in result.raw_lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
