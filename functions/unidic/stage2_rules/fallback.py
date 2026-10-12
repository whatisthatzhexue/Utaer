"""兜底规则：词典直取（R-LEX-DICT）与未收录/无调型兜底（R-FALLBACK-*）。

依据（四合一）：

- 资料一（阶段一输出）：词典 aType 数字 / ``@`` 词经発音字段 ``[]`` 解码的调型
  （解码依据见 ``mora_util.decode_bracket_accent``）——R-LEX-DICT 直取；
- 总 AGENTS.md §9：未收录词按「語種倾向 → 默认平板型」兜底，
  并在 notes 标注「词典未收录」；**禁止**用调型推测（s2ya/sy2a）补齐。

规则清单：

- ``R-LEX-DICT``：词典收录且调型有效 → 直取主值（逗号多调型的其余值进 variants）；
- ``R-FALLBACK-HEIBAN``：兜底默认平板型（M3 起由更细的語種倾向规则先行截获）。
"""

from __future__ import annotations

import logging

import mora_util
from stage2_rules.base import MorphList, Rule, RulePhase, parse_accent_value

logger = logging.getLogger(__name__)

# 声调来源标记（值同 stage1_analyzer.ACCENT_SOURCE_*；此处用字面量保持分层，
# 阶段二不反向依赖阶段一模块）
_SOURCE_BRACKET = "bracket"


class LexDictRule(Rule):
    """词典直取：采用阶段一确切匹配得到的调型（aType 数字或 ``[]`` 解码值）。

    ``accent_source == "bracket"`` 的词（``@`` + ``[]`` 标注）不是无音调——
    其推断调型经発音字段标记确证，同样按词典确切匹配直取（非推测）。
    """

    rule_id = "R-LEX-DICT"
    name = "词典直取（阶段一・确切匹配）"
    source_ref = "tdmelodic 组合词典（UniDic 2.1.2 + 大音调词典）"
    priority = 100
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.claimed or morph.accent is not None or morph.is_unknown:
            return False
        return parse_accent_value(morph.accent_raw)[0] is not None

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        main, variants = parse_accent_value(morph.accent_raw)
        morph.accent = main
        morph.variants = variants
        morph.derived_by = self.rule_id
        desc = mora_util.describe_accent(main, morph.mora_count)
        if morph.accent_source == _SOURCE_BRACKET:
            logic = f"「{morph.morph}」词典收录（推断调型经発音字段[]标记确证），{desc}→ 直接采用"
        else:
            logic = f"「{morph.morph}」词典收录，{desc}→ 直接采用"
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class FallbackHeibanRule(Rule):
    """兜底：无任何调型来源时取默认平板型 0（NHK 語種倾向表的终档）。"""

    rule_id = "R-FALLBACK-HEIBAN"
    name = "兜底・默认平板型"
    source_ref = "总 AGENTS.md §9（未收录词兜底）＋ NHK Ⅲ全般 1.（語種倾向终档）"
    priority = 50
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        return morph.accent is None and not morph.claimed

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        morph.accent = 0
        morph.derived_by = self.rule_id
        if morph.is_unknown:
            if "词典未收录" not in morph.notes:
                morph.notes.append("词典未收录")
            logic = (
                f"「{morph.morph}」词典未收录（@ 且无 [] 标注）→ "
                "按兜底规则取默认平板型（0）；notes 标注「词典未收录」"
            )
        elif morph.is_particle_like:
            logic = f"「{morph.morph}」为付属語（无固有调型）→ 默认平板 0（付属語不干渉）"
        elif morph.is_symbol:
            logic = f"「{morph.morph}」为记号类（无读音）→ 默认平板 0"
        else:
            logic = f"「{morph.morph}」无可用词典调型 → 默认平板型（0）"
        result = morphs.render_range(i, i) if morph.pron else morph.morph
        morphs.add_report(self, (i, i), logic, result)
