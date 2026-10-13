"""複合動詞声调预处理（首位動詞规则；用户确认）。

规则（用户的完备规则表述）：

> 对于复合动词的声调型，**始终只考虑最前面的动词的声调型**。
> 若最前面的动词声调型为**平板**，则复合动词为**中高[-2]**；
> 若最前面动词声调型为**非平板**，则复合动词为**平板**。

（对应资料三 NHK Ⅲ全般 1. k 的历史规则描述；现代虽倾向一律中高，本项目按用户
确认的经典规则执行。）

触发条件：词典中携带**多调型**（逗号分隔，如 ``思い込ん＝"4,0,2"``）的動詞 token
——多调型即规则未决的歧义项，按首位動詞规则确定性裁定；
单词型调型的词典条目保持词典值不变。

首位動詞的检出：对 token 表層形做前缀分解（借 MeCab 组合词典），取可解析为
動詞（或非サ変的名詞——如「思い」这类動詞連用形名词化）且读音为整词读音前缀的
最长前缀；后缀亦须可解析为動詞。「参加し」等 サ変（名詞+し）不属複合動詞，排除。

用例对照：思い込ん（"4,0,2"；首位 思い＝オモイ 非平板）→ 平板 0 →
思い込んだら → オモイコンダ＼ラ（平板動詞＋だら 插入）。
"""

from __future__ import annotations

import logging

import mora_util
import stage1_analyzer
from stage2_rules.base import MorphList, MorphState, parse_accent_value

logger = logging.getLogger(__name__)

#: 预处理报告（六字段契约）
_RULE_ID = "R-CONJ-COMPOUND-VERB"
_RULE_NAME = "複合動詞・首位動詞规则"
_SOURCE_REF = "NHK Ⅲ全般 1. k（複合動詞：首位動詞の型で定まる；用户确认）"


def _find_first_verb(
    morph: MorphState, tagger, overrides: dict
) -> MorphState | None:
    """检出複合動詞的首位動詞（见模块 docstring）；检出失败返回 None。"""
    surface = morph.morph
    if len(surface) < 3:
        return None
    for k in range(len(surface) - 1, 0, -1):
        prefix = surface[:k]
        suffix = surface[k:]
        if not suffix:
            continue
        parts = stage1_analyzer.parse_nodes(prefix, tagger, overrides)
        if not parts or parts[0].is_unknown:
            continue
        first = parts[0]
        first_pos_head = first.pos.split("-")[0] if first.pos else ""
        is_verb_stem = first_pos_head == "動詞" or (
            first_pos_head == "名詞" and "サ変" not in first.pos
        )
        if not is_verb_stem:
            continue
        if not first.pron or not morph.pron.startswith(first.pron):
            continue                      # 读音前缀校验（防误切）
        tail = stage1_analyzer.parse_nodes(suffix, tagger, overrides)
        if not tail or not any(
            (p.pos.split("-")[0] if p.pos else "") == "動詞" for p in tail
        ):
            continue                      # 后缀须含動詞（込ん/出す/取る…）
        return first
    return None


def apply_compound_verb_rule(ctx: MorphList, tagger, overrides: dict) -> int:
    """对多调型動詞 token 应用複合動詞首位规则；返回改动数。"""
    reports: list[dict] = []
    changed = 0
    for morph in ctx:
        if morph.claimed or morph.accent is not None:
            continue
        if morph.pos_head != "動詞" or "," not in morph.accent_raw:
            continue
        v1 = _find_first_verb(morph, tagger, overrides)
        if v1 is None:
            continue
        v1_accent, _ = parse_accent_value(v1.accent_raw)
        v1_accent = v1_accent or 0
        if v1_accent == 0:
            accent = max(1, morph.mora_count - 1)   # 中高[-2]
            kind = "中高型[-2]"
        else:
            accent = 0                              # 平板型
            kind = "平板型"
        morph.accent = accent
        morph.derived_by = _RULE_ID
        reports.append({
            "rule_id": _RULE_ID,
            "name": _RULE_NAME,
            "source_ref": _SOURCE_REF,
            "target": [morph.idx, morph.idx],
            "logic": (
                f"「{morph.morph}」为多调型複合動詞（词典调型 {morph.accent_raw}）；"
                f"首位動詞「{v1.morph}」调型={v1_accent}"
                f"（{'平板' if v1_accent == 0 else '非平板'}）→ 複合動詞取 {kind}"
            ),
            "result": _render(morph),
        })
        changed += 1

    if reports:
        ctx.report[:0] = reports
        logger.info("複合動詞规则：裁定 %d 个多调型動詞", changed)
    return changed


def _render(morph: MorphState) -> str:
    return mora_util.render_accent(
        morph.pron, morph.accent if morph.accent is not None else 0
    )
