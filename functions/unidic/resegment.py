"""未知词再切分（确定性词典分解）——M3 里程碑新增的管线预步骤。

背景（实测）：组合词典对大音调词典未收录（``@`` 且无 ``[]`` 标注）的整词
（如「住民税」在某些形态下、生造词、罕见复合词）可能只给出一个无调型的形态素；
此时若直接走兜底规则，会丢失复合词规则（资料二 C1–C5 / 资料三 NHK Ⅰ複合名詞）
可推导的调型。

本模块以**确定性词典分解**弥补：把整词按组合词典条目切分为已知成分
（成分调型全部来自确切查表，逐层递归直至可用），再交由阶段二规则引擎处理
（复合词规则 → 核合法性校验）。**不引入任何推测**（禁用 s2ya/sy2a 的约束同样适用）。

算法（贪心最左最长，确定性）：

1. 对每个「真未收录」（``is_unknown``）且表層形长度 ≥ 2 的形态素尝试分解；
2. 在切分点自右向左枚举（等价于最左最长），左右两段分别用组合词典解析；
   解析结果中若含新的未收录成分 → 递归分解该成分；任一单字未收录成分
   → 该切分失败，继续尝试更短的左段；
3. 全部分解成功 → 以成分形态素替换原形态素（idx 连续重编号），
   并登记 ``R-DECOMP-LEX`` 报告条目（六字段，供 rule_report.json）。

分解产物随后进入阶段二：例如 住民税 → ［住民（C3 后部「税」）］，
由 ``R-COMPOUND-C3`` 得 ジューミン＼ゼイ，再由 ``R-NUCLEUS-SPECIAL``
前移为 ジューミ＼ンゼイ（与 NHK 辞典用例一致）。
"""

from __future__ import annotations

import logging
from typing import Any

import stage1_analyzer
from stage2_rules.base import MorphList, MorphState

logger = logging.getLogger(__name__)

#: 分解递归深度上限（确定性保护；表層形为短词，正常深度 ≤ 2）
MAX_DEPTH = 4

#: 报告条目（六字段契约）
_RULE_ID = "R-DECOMP-LEX"
_RULE_NAME = "未知词再切分（确定性词典分解）"
_SOURCE_REF = "总 AGENTS.md §9＋AGENT.md 3.1（词典确切匹配；禁止调型推测）"


def _resolve_term(
    term: str,
    tagger: Any,
    overrides: dict[str, dict[str, Any]],
    depth: int = 0,
) -> tuple[Any, ...] | None:
    """解析单个词段；含未收录成分时递归分解。全部分量可用才返回形态素元组。"""
    if not term or depth > MAX_DEPTH:
        return None
    morphs = stage1_analyzer.parse_nodes(term, tagger, overrides)
    if not morphs:
        return None
    resolved: list[Any] = []
    for morph in morphs:
        if not morph.is_unknown:
            resolved.append(morph)
            continue
        if len(morph.morph) < 2:          # 单字未收录：无法再分
            return None
        sub = _decompose(morph.morph, tagger, overrides, depth + 1)
        if sub is None:
            return None
        resolved.extend(sub)
    return tuple(resolved)


def _decompose(
    surface: str,
    tagger: Any,
    overrides: dict[str, dict[str, Any]],
    depth: int = 0,
) -> tuple[Any, ...] | None:
    """贪心最左最长分解：返回成分形态素元组；无法分解返回 None。"""
    if len(surface) < 2 or depth > MAX_DEPTH:
        return None
    for split in range(len(surface) - 1, 0, -1):
        left = _resolve_term(surface[:split], tagger, overrides, depth + 1)
        if left is None:
            continue
        right = _resolve_term(surface[split:], tagger, overrides, depth + 1)
        if right is None:
            continue
        return left + right
    return None


def decompose(
    surface: str,
    tagger: Any | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> tuple[Any, ...] | None:
    """对外入口：确定性分解 ``surface``（供自检与调试使用）。"""
    if tagger is None:
        tagger = stage1_analyzer.build_tagger()
    return _decompose(surface, tagger, overrides or {}, depth=0)


def resegment_unknowns(
    ctx: MorphList,
    tagger: Any,
    overrides: dict[str, dict[str, Any]],
) -> int:
    """对上下文中的真未收录整词执行再切分；返回成功分解的词数。

    成功分解时：以成分形态素（:class:`MorphState`）替换原形态素并重编号 idx，
    且在 ``ctx.report`` 头部插入 ``R-DECOMP-LEX`` 条目（先于后续规则触发顺序）。
    """
    new_morphs: list[MorphState] = []
    reports: list[dict[str, Any]] = []

    for morph in ctx:
        if not morph.is_unknown or len(morph.morph) < 2:
            new_morphs.append(morph)
            continue
        parts = _decompose(morph.morph, tagger, overrides, depth=0)
        if parts is None or len(parts) < 2:
            new_morphs.append(morph)
            continue

        start = len(new_morphs)
        for part in parts:
            new_morphs.append(MorphState.from_morph(part))
        reports.append({
            "rule_id": _RULE_ID,
            "name": _RULE_NAME,
            "source_ref": _SOURCE_REF,
            "target": [start, len(new_morphs) - 1],
            "logic": (
                f"「{morph.morph}」整词未收录（@ 且无 [] 标注）→ "
                f"按组合词典条目确定性切分为 " + "＋".join(p.morph for p in parts)
            ),
            "result": "".join(p.pron for p in parts),
        })

    if not reports:
        return 0

    ctx.clear()
    ctx.extend(new_morphs)
    for i, morph in enumerate(ctx):
        morph.idx = i
    ctx.report[:0] = reports
    logger.info("再切分：%d 个未收录整词被确定性分解", len(reports))
    return len(reports)
