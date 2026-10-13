"""核合法性规则（后处理校验型）：特殊拍・二重母音副音・无声化拍不能承载声调核。

依据（四合一）：

- 资料三 NHK Ⅰ複合名詞 1.2）但书：前部要素の最終拍が特殊拍（ン・ッ・ー）、
  またはそれに準ずる音（二重母音の第 2 要素や無声化音）である場合、
  下がり目が 1 拍前にずれる（例：住民税 ジューミ＼ンゼー、指定席 シテ＼ーセキ、
  警戒心 ケーカ＼イシン）；
- 资料三 NHK Ⅲ全般 A：長音［ー］/撥音［ン］の後に下がり目を置かない
  （カレ＼ーパン，非 カレー＼パン）；二重母音副音［イ］の後も原則避ける；
- 资料四（Wikipedia 非自立拍理论）：特殊拍と deficient morae は核になれない；
  規則が核をそこに置いた場合は accent shift。

契约注意（《本项目配置教程.md》3.8.1）：本规则是**后处理校验型**，
其优先级应始终高于其他推导型规则；实现上由 ``Rule.phase = VALIDATION``
保证永远在推导之后执行（见 ``stage2_rules.run_engine`` 两遍机制）。

配置（``rules_config.json`` → ``nucleus_legality``）：

- ``avoid_devoiced``（默认 false）：是否把「无声化倾向拍」也视为不可承载核。
  NHK 现代倾向为「核不动」（Ⅲ全般 C 型），故默认关闭。
"""

from __future__ import annotations

import logging

import mora_util
from stage2_rules.base import MorphList, Rule, RulePhase

logger = logging.getLogger(__name__)


def _join_chain(morphs: MorphList, i: int) -> tuple[int, int]:
    """返回包含位置 ``i`` 的 ``join_next`` 合并链区间（复合词/接辞区间）。

    无合并标记时即 ``(i, i)``。
    """
    start = i
    while start > 0 and morphs[start - 1].join_next:
        start -= 1
    end = i
    while end < len(morphs) - 1 and morphs[end].join_next:
        end += 1
    return start, end


class NucleusSpecialRule(Rule):
    """核合法性・特殊拍核移位（后处理校验型；详见模块 docstring）。"""

    rule_id = "R-NUCLEUS-SPECIAL"
    name = "核合法性・特殊拍核移位"
    source_ref = "NHK Ⅰ複合名詞 1.2）但书＋ Ⅲ全般 A（＋ Wikipedia 非自立拍）"
    priority = 1000
    phase = RulePhase.VALIDATION
    config_section = "nucleus_legality"

    def _illegal_reason(self, morph: MorphState, moras: list[str], idx: int) -> str:
        """返回第 idx 拍不可承载核的原因；可承载时返回空串。"""
        mora = moras[idx]
        if mora_util.is_special_mora(mora):
            # 動詞末尾的「ー」（ウ 的口语缩合，如 いう→ユー）允许承载尾高核
            # （用例对照：ユー＼ノガ；名词性长音仍按 NHK Ⅲ全般 A 回避，如 カレ＼ーパン）
            if mora == "ー" and morph.pos_head == "動詞" and idx == len(moras) - 1:
                return ""
            return f"「{mora}」为特殊拍（拨音/促音/长音）"
        if mora_util.is_diphthong_glide(moras, idx):
            return f"「{mora}」为二重母音副音（イ）"
        if bool(self.options.get("avoid_devoiced", False)) and mora_util.is_devoiced_mora(mora):
            return f"「{mora}」为无声化倾向拍"
        return ""

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is None or morph.accent <= 0:
            return False
        moras = mora_util.split_moras(morph.pron)
        if not moras:
            return False
        nucleus_index = min(morph.accent, len(moras)) - 1
        return bool(self._illegal_reason(morph, moras, nucleus_index))

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        moras = mora_util.split_moras(morph.pron)
        nucleus_index = min(morph.accent, len(moras)) - 1
        reason = self._illegal_reason(morph, moras, nucleus_index)
        before = morph.accent
        morph.accent = max(0, (before or 0) - 1)
        morph.derived_by = self.rule_id

        start, end = _join_chain(morphs, i)
        logic = f"{reason}，核不可置于其后 → 下降核前移1拍（调型 {before}→{morph.accent}）"
        morphs.add_report(self, (start, end), logic, morphs.render_range(start, end))
