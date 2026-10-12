"""兜底规则：词典直取（R-LEX-DICT）与未收录/无调型兜底（R-FALLBACK-*）。

依据（四合一）：

- 资料一（阶段一输出）：词典 aType 数字 / ``@`` 词经発音字段 ``[]`` 解码的调型
  （解码依据见 ``mora_util.decode_bracket_accent``）——R-LEX-DICT 直取；
- 总 AGENTS.md §9：未收录词按「語種倾向 → 默认平板型」兜底，
  并在 notes 标注「词典未收录」；**禁止**用调型推测（s2ya/sy2a）补齐。

规则清单：

- ``R-LEX-DICT``：词典收录且调型有效 → 直取主值（逗号多调型的其余值进 variants）；
- ``R-FALLBACK-GOSHU-*``：NHK Ⅲ全般 1. 語種倾向表分条兜底（KANGO11/KANGO21/
  KANGO22/GAIRAI3/GAIRAI4/GAIRAI5/VERB/ADJ）；
- ``R-FALLBACK-HEIBAN``：兜底默认平板型（語種倾向规则未截获时的终档）。
"""

from __future__ import annotations

import logging

import mora_util
from stage2_rules.base import MorphList, MorphState, Rule, RulePhase, parse_accent_value

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


def _is_kanji_char(ch: str) -> bool:
    """单字符汉字判定（CJK 统一表意文字 + 扩展 A + 々〆）。"""
    code = ord(ch)
    return (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF) or ch in "々〆"


class GoshuKango11Rule(Rule):
    """語種倾向兜底：二字漢語(1+1) → 頭高型（NHK Ⅲ全般 1. a）。"""

    rule_id = "R-FALLBACK-GOSHU-KANGO11"
    name = "語種倾向兜底・二字漢語(1+1)・頭高型"
    source_ref = "NHK Ⅲ全般 1. a（二字漢語(1+1)は頭高型）"
    priority = 60
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed or not morph.is_unknown:
            return False
        surface = morph.morph
        return (
            len(surface) == 2
            and all(_is_kanji_char(ch) for ch in surface)
            and morph.mora_count == 2
        )

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        morph.accent = 1
        morph.derived_by = self.rule_id
        if "词典未收录" not in morph.notes:
            morph.notes.append("词典未收录")
        logic = (
            f"「{morph.morph}」词典未收录（@ 且无 [] 标注）→ "
            "按 NHK Ⅲ全般 1. a 語種倾向（二字漢語(1+1)は頭高型）取 调型=1（頭高型）"
        )
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class GoshuGaira3Rule(Rule):
    """語種倾向兜底：外来語 3 拍以下 → 頭高型；末拍特殊拍 → 中高（NHK Ⅲ全般 1. e）。"""

    rule_id = "R-FALLBACK-GOSHU-GAIRAI3"
    name = "語種倾向兜底・外来語3拍以下"
    source_ref = "NHK Ⅲ全般 1. e（外来語3拍以下は頭高型；末拍特殊拍は中高）"
    priority = 60
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed or not morph.is_unknown:
            return False
        if morph.mora_count < 1 or morph.mora_count > 3:
            return False
        surface = morph.morph
        return bool(surface) and all(
            mora_util.is_katakana(ch) or ch == "ー" for ch in surface
        )

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        moras = mora_util.split_moras(morph.pron)
        if moras and len(moras) >= 3 and mora_util.is_special_mora(moras[-1]):
            morph.accent = len(moras) - 1   # 末拍特殊拍 → 中高（[-2] 相当）
            kind = f"中高型（末拍「{moras[-1]}」为特殊拍）"
        else:
            morph.accent = 1                # 頭高型
            kind = "頭高型"
        morph.derived_by = self.rule_id
        if "词典未收录" not in morph.notes:
            morph.notes.append("词典未收录")
        logic = (
            f"「{morph.morph}」词典未收录（@ 且无 [] 标注）→ "
            f"按 NHK Ⅲ全般 1. e 語種倾向（外来語3拍以下は頭高型）取 调型={morph.accent}（{kind}）"
        )
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class GoshuKango21Rule(Rule):
    """語種倾向兜底：二字漢語 3 拍（2+1／1+2）→ 頭高型（名词性；サ変可能→平板）。

    NHK Ⅲ全般 1. b/c：二字漢語(2+1) 名词性头高、动词性多平板；
    (1+2) 平板——本机数据无法确定性区分 2+1 与 1+2 结构，按名词性/サ変
    两种 pos 分支处理（近似实现，见模块说明）。
    """

    rule_id = "R-FALLBACK-GOSHU-KANGO21"
    name = "語種倾向兜底・二字漢語 3 拍"
    source_ref = "NHK Ⅲ全般 1. b/c（二字漢語(2+1)/(1+2)）"
    priority = 60
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed or not morph.is_unknown:
            return False
        if morph.pos_head != "名詞" or morph.mora_count != 3:
            return False
        surface = morph.morph
        return len(surface) == 2 and all(_is_kanji_char(ch) for ch in surface)

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        if "サ変" in morph.pos:               # 动词性多平板（NHK 1. b）
            morph.accent = 0
            kind = "平板型（动词性・サ変可能）"
        else:
            morph.accent = 1
            kind = "頭高型"
        morph.derived_by = self.rule_id
        if "词典未收录" not in morph.notes:
            morph.notes.append("词典未收录")
        logic = f"「{morph.morph}」词典未收录 → 按 NHK Ⅲ全般 1. b/c 語種倾向取 {kind}"
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class GoshuKango22Rule(Rule):
    """語種倾向兜底：二字漢語 4 拍（2+2）→ 平板型（NHK Ⅲ全般 1. d）。"""

    rule_id = "R-FALLBACK-GOSHU-KANGO22"
    name = "語種倾向兜底・二字漢語 4 拍・平板型"
    source_ref = "NHK Ⅲ全般 1. d（二字漢語(2+2)は平板型）"
    priority = 60
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed or not morph.is_unknown:
            return False
        if morph.pos_head != "名詞" or morph.mora_count != 4:
            return False
        surface = morph.morph
        return len(surface) == 2 and all(_is_kanji_char(ch) for ch in surface)

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        morph.accent = 0
        morph.derived_by = self.rule_id
        if "词典未收录" not in morph.notes:
            morph.notes.append("词典未收录")
        logic = f"「{morph.morph}」词典未收录 → 按 NHK Ⅲ全般 1. d 語種倾向（二字漢語(2+2)）取 平板型（0）"
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


def _is_katakana_surface(morph: MorphState) -> bool:
    """表層形是否为片假名（含长音符）。"""
    surface = morph.morph
    return bool(surface) and all(
        mora_util.is_katakana(ch) or ch == "ー" for ch in surface
    )


class GoshuGaira4Rule(Rule):
    """語種倾向兜底：外来語 4 拍（NHK Ⅲ全般 1. f）。

    2 拍目特殊拍 → 頭高；3 拍目特殊拍 → 中高[-3]（=2）；末拍特殊拍 → 頭高；无特殊拍 → 平板。
    """

    rule_id = "R-FALLBACK-GOSHU-GAIRAI4"
    name = "語種倾向兜底・外来語 4 拍"
    source_ref = "NHK Ⅲ全般 1. f（外来語4拍：按特殊拍位置）"
    priority = 60
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed or not morph.is_unknown:
            return False
        return morph.mora_count == 4 and _is_katakana_surface(morph)

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        moras = mora_util.split_moras(morph.pron)
        if len(moras) == 4 and mora_util.is_special_mora(moras[1]):
            morph.accent, kind = 1, "頭高型（2 拍目特殊拍）"
        elif len(moras) == 4 and mora_util.is_special_mora(moras[2]):
            morph.accent, kind = 2, "中高型[-3]（3 拍目特殊拍）"
        elif len(moras) == 4 and mora_util.is_special_mora(moras[3]):
            morph.accent, kind = 1, "頭高型（末拍特殊拍）"
        else:
            morph.accent, kind = 0, "平板型（无特殊拍）"
        morph.derived_by = self.rule_id
        if "词典未收录" not in morph.notes:
            morph.notes.append("词典未收录")
        logic = f"「{morph.morph}」词典未收录 → 按 NHK Ⅲ全般 1. f 語種倾向取 {kind}"
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class GoshuGaira5Rule(Rule):
    """語種倾向兜底：外来語 5 拍以上 → 中高[-3]；5/6 拍末长音 → 中高[-4]（NHK Ⅲ全般 1. g）。"""

    rule_id = "R-FALLBACK-GOSHU-GAIRAI5"
    name = "語種倾向兜底・外来語 5 拍以上・中高型"
    source_ref = "NHK Ⅲ全般 1. g（外来語5拍以上は中高[-3]；末拍長音 5/6拍は [-4]）"
    priority = 60
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed or not morph.is_unknown:
            return False
        return morph.mora_count >= 5 and _is_katakana_surface(morph)

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        moras = mora_util.split_moras(morph.pron)
        count = len(moras)
        if count in (5, 6) and moras and moras[-1] == "ー":
            morph.accent = max(1, count - 3)          # [-4]
            kind = "中高型[-4]（末拍長音）"
        else:
            morph.accent = max(1, count - 2)          # [-3]
            kind = "中高型[-3]"
        morph.derived_by = self.rule_id
        if "词典未收录" not in morph.notes:
            morph.notes.append("词典未收录")
        logic = f"「{morph.morph}」词典未收录 → 按 NHK Ⅲ全般 1. g 語種倾向取 {kind}"
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class GoshuVerbRule(Rule):
    """語種倾向兜底：動詞（3 拍以上）→ 中高[-2]（NHK Ⅲ全般 1. i）。"""

    rule_id = "R-FALLBACK-GOSHU-VERB"
    name = "語種倾向兜底・動詞・中高型"
    source_ref = "NHK Ⅲ全般 1. i（動詞3拍以上は中高[-2]）"
    priority = 60
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed or not morph.is_unknown:
            return False
        return morph.pos_head == "動詞" and morph.mora_count >= 3

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        morph.accent = max(1, morph.mora_count - 1)   # [-2]
        morph.derived_by = self.rule_id
        if "词典未收录" not in morph.notes:
            morph.notes.append("词典未收录")
        logic = f"「{morph.morph}」词典未收录 → 按 NHK Ⅲ全般 1. i 語種倾向（動詞3拍以上）取 中高型[-2]（{morph.accent}）"
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class GoshuAdjRule(Rule):
    """語種倾向兜底：形容詞 → 中高[-2]；2 拍则頭高（NHK Ⅲ全般 1. j）。"""

    rule_id = "R-FALLBACK-GOSHU-ADJ"
    name = "語種倾向兜底・形容詞・中高型"
    source_ref = "NHK Ⅲ全般 1. j（形容詞は中高[-2]；2拍は頭高）"
    priority = 60
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed or not morph.is_unknown:
            return False
        return morph.pos_head == "形容詞" and morph.mora_count >= 2

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        if morph.mora_count == 2:
            morph.accent, kind = 1, "頭高型（2拍）"
        else:
            morph.accent, kind = max(1, morph.mora_count - 1), "中高型[-2]"
        morph.derived_by = self.rule_id
        if "词典未收录" not in morph.notes:
            morph.notes.append("词典未收录")
        logic = f"「{morph.morph}」词典未收录 → 按 NHK Ⅲ全般 1. j 語種倾向取 {kind}"
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
