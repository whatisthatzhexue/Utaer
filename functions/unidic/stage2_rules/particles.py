"""付属語接続规则（资料三 NHK Ⅲ-1：名词接付属語 ＋『付属語不干渉』原则）。

依据（NHK Ⅲ-1 名詞に付属語が付いた場合の発音とアクセント）：

- **总原则「付属語不干渉」**：绝大多数付属語不影响前接名词部分的声调；
- **1.1 平板式付属語**（自身无下がり目）→ 直接连读：
  - 1 拍全部付属語：か・が・だ・で・と・に・の・は・へ・も・や・を
    （匹配按**発音**：は→ワ、へ→エ、を→オ）；
  - 2 拍以上的一部分：から・だけ・って・として・ほど；
- **4.1 付属語決定型**与**1.2 起伏式付属語**（です・まで・ばかり・ぐらい 等）
  以及**2.1「の」接尾高名词平板化**属后续里程碑（见模块 TODO）。

规则清单：

- ``R-PART-FLAT``：平板式付属語・基本接続（自身调型置 0，前部保持，直接连读）。
"""

from __future__ import annotations

import logging

import mora_util
from stage2_rules.base import MorphList, Rule, RulePhase

logger = logging.getLogger(__name__)

#: 平板式付属語（1 拍全部；NHK Ⅲ-1 1.1）——按**発音**匹配
FLAT_PARTICLES_1MORA: frozenset[str] = frozenset({
    "カ", "ガ", "ダ", "デ", "ト", "ニ", "ノ", "ワ", "エ", "モ", "ヤ", "オ",
})

#: 平板式付属語（2 拍以上的一部分；NHK Ⅲ-1 1.1）——按発音匹配
FLAT_PARTICLES_MULTI: frozenset[str] = frozenset({
    "カラ", "ダケ", "ッテ", "トシテ", "ホド",
})


class PartFlatRule(Rule):
    """平板式付属語・基本接続（NHK Ⅲ-1 1.1）。

    条件：付属語（助詞/助動詞）自身调型为空且在平板式付属語表内，
    前接形态素为**名词性**（名词/代名词）且已推导出调型。
    动作：付属語调型置 0（不产生新核），前部调型保持，直接连读。
    """

    rule_id = "R-PART-FLAT"
    name = "平板式付属語・基本接続"
    source_ref = "NHK Ⅲ-1 1.1（『付属語不干渉』）"
    priority = 200
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if i <= 0:
            return False
        morph = morphs[i]
        if morph.accent is not None or morph.claimed:
            return False
        if morph.pos_head not in ("助詞", "助動詞"):
            return False
        prev = morphs[i - 1]
        if prev.accent is None or not prev.is_nominal:
            return False
        pron = mora_util.strip_brackets(morph.pron)
        return pron in FLAT_PARTICLES_1MORA or pron in FLAT_PARTICLES_MULTI

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        morph.accent = 0
        morph.derived_by = self.rule_id
        logic = (
            f"「{morph.morph}」为平板式付属語（无自身下がり目）→ "
            "名詞部分调型保持，直接连读"
        )
        morphs.add_report(self, (i - 1, i), logic, morphs.render_range(i - 1, i))
