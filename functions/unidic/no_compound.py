"""の-复合名词（格助词「ノ」连接的名词组合）音调结合预处理（用户规则）。

规则（用户确认）：

> 像「クスリヤノヒトリゴト」这类由格助词「ノ」连接的名词复合组合，当作为整体
> 复合词处理时，必须严格计算「ノ」前后的单词原音调与结合后的平板化/下落位置。
> 例：クスリヤ[0] ＋ ノ ＋ ヒトリゴト[0] → クスリヤノヒトリゴト[0]（━ 整体平板）。

实现：

- **整词含 の 的词典条目**（如 薬屋のひとりごと 为单一词典 token）：按 の 分解为
  ``[A][の][B]``（借 MeCab 词典解析，分量均须非未知词）；
- **已分离的 [A][の][B] 序列**：直接检查；
- 仅当 **A 与 B 的词典调型均为平板（0）** 时合并为单一アクセント単位并整体平板
  （用户规则的可确证范围）；其余组合保持既有处理（の 的付属語不干渉等），
  避免破坏既有 NHK 规则（如 キノーノ━・ヨル 型）。

合并结果：三形态素同单位（join_next 链），アクセント全 0，登记 R-COMPOUND-NO。
"""

from __future__ import annotations

import logging

import mora_util
import stage1_analyzer
from stage2_rules.base import MorphList, MorphState, parse_accent_value

logger = logging.getLogger(__name__)

#: 预处理报告（六字段契约）
_RULE_ID = "R-COMPOUND-NO"
_RULE_NAME = "の-复合名词・结合律"
_SOURCE_REF = "用户规则（格助词ノ连接的名词组合・结合后平板化）；NHK Ⅰ複合名詞 系"


def _parse_parts(text: str, tagger, overrides: dict) -> tuple[MorphState, ...] | None:
    """解析分量；含未知词或空结果返回 None。"""
    if not text:
        return None
    parts = stage1_analyzer.parse_nodes(text, tagger, overrides)
    if not parts or any(p.is_unknown for p in parts):
        return None
    return tuple(MorphState.from_morph(p) for p in parts)


def _try_split_no(surface: str, tagger, overrides: dict) -> tuple[MorphState, ...] | None:
    """把含 の 的表層形分解为 [A][の][B]；失败返回 None。"""
    start = 0
    while True:
        idx = surface.find("の", start)
        if idx == -1:
            return None
        a_text, b_text = surface[:idx], surface[idx + 1:]
        parts_a = _parse_parts(a_text, tagger, overrides)
        parts_b = _parse_parts(b_text, tagger, overrides)
        if parts_a and parts_b:
            no_morph = _parse_parts("の", tagger, overrides)
            return parts_a + (no_morph or ()) + parts_b if no_morph else None
        start = idx + 1


def _flat_accent_raw(morph: MorphState) -> bool:
    """形态素的词典调型是否为平板（0）。"""
    main, _ = parse_accent_value(morph.accent_raw)
    return main == 0


def _mark_merged(parts: tuple[MorphState, ...]) -> None:
    """把分解/序列分量标记为单一平板单位（join_next 链 + 全 0）。"""
    for k, part in enumerate(parts):
        part.idx = 0
        part.accent = 0
        part.claimed = True
        part.derived_by = _RULE_ID
        if k < len(parts) - 1:
            part.join_next = True


def apply_no_compound_rule(ctx: MorphList, tagger, overrides: dict) -> int:
    """应用 の-复合名词结合律；返回合并组数。

    两条路径：① 已分离的 [A][の][B] 序列；② 整词含 の 的词典条目（分解后判定）。
    仅双平板组合合并，其余保持既有处理。
    """
    merged = 0
    reports: list[dict] = []

    # —— 路径①：已分离的 [N1][の][N2]（双平板）——
    stage: list[MorphState] = []
    i = 0
    while i < len(ctx):
        if (
            i + 2 < len(ctx)
            and ctx[i].pos_head == "名詞" and ctx[i + 2].pos_head == "名詞"
            and ctx[i + 1].morph == "の"
            and (i == 0 or ctx[i - 1].pos_head != "名詞")
            and not ctx[i].claimed and not ctx[i + 1].claimed and not ctx[i + 2].claimed
            and ctx[i].accent is None and ctx[i + 1].accent is None and ctx[i + 2].accent is None
            and _flat_accent_raw(ctx[i]) and _flat_accent_raw(ctx[i + 2])
        ):
            group: tuple[MorphState, ...] = (ctx[i], ctx[i + 1], ctx[i + 2])
            start = len(stage)
            _mark_merged(group)
            stage.extend(group)
            reports.append({
                "rule_id": _RULE_ID,
                "name": _RULE_NAME,
                "source_ref": _SOURCE_REF,
                "target": [start, len(stage) - 1],
                "logic": (
                    f"「{ctx[i].morph}の{ctx[i + 2].morph}」为格助词ノ连接的名词复合"
                    "（分量均平板）→ 依结合律整体平板化"
                ),
                "result": _render_flat(group),
            })
            merged += 1
            i += 3
            continue
        stage.append(ctx[i])
        i += 1

    # —— 路径②：整词含 の 的词典条目（分解为 [A][の][B] 后判定）——
    final: list[MorphState] = []
    for morph in stage:
        if (
            morph.pos_head == "名詞"
            and not morph.claimed
            and morph.accent is None
            and "の" in morph.morph
            and len(morph.morph) >= 3
        ):
            parts = _try_split_no(morph.morph, tagger, overrides)
            if parts is not None and _split_both_flat(parts):
                start = len(final)
                _mark_merged(parts)
                final.extend(parts)
                reports.append({
                    "rule_id": _RULE_ID,
                    "name": _RULE_NAME,
                    "source_ref": _SOURCE_REF,
                    "target": [start, len(final) - 1],
                    "logic": (
                        f"「{morph.morph}」为格助词ノ连接的名词复合（分量均平板）→ "
                        "依结合律整体平板化（如 クスリヤ[0]＋ノ＋ヒトリゴト[0] → クスリヤノヒトリゴト[0]）"
                    ),
                    "result": _render_flat(parts),
                })
                merged += 1
                continue
        final.append(morph)

    if merged == 0:
        return 0

    ctx.clear()
    ctx.extend(final)
    for k, m in enumerate(ctx):
        m.idx = k
    ctx.report[:0] = reports
    logger.info("の-复合：合并 %d 组", merged)
    return merged


def _split_both_flat(parts: tuple[MorphState, ...]) -> bool:
    """分解结果是否满足「ノ 前后分量均为平板」——の 本身（助詞）不参与判定。"""
    for morph in parts:
        if morph.pos_head == "助詞" and morph.morph == "の":
            continue
        main, _ = parse_accent_value(morph.accent_raw)
        if main != 0:
            return False
    return True


def _render_flat(parts: tuple[MorphState, ...]) -> str:
    kana = "".join(p.pron for p in parts)
    return mora_util.render_accent(kana, 0)
