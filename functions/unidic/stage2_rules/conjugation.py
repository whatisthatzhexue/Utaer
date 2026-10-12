"""活用形规则（资料二 UniDic 手册 表9 アクセント修飾型 ＋ 资料三 NHK Ⅲ-2 活用形）。

依据（四合一，已逐项核对）：

- **资料二 表9「アクセント修飾型分類」**（本模块核心实现对象；词典原生字段
  ``MorphState.a_mod_type``，实测：意志推量形 token=``M1@1``、たかっ=``M2@2``、
  たけれ=``M2@2``）::

      修飾型   基本形のアクセント型が 0型 →       ／ それ以外 →      例
      M1@M     N0 − M（无 0 型分支）                              意志推量形
      M2@M     0型→M0（保持）                     ／ N0 − M        一段・サ変活用の命令形
      M4@M     0型→M0（保持）                     ／ M0 − M        一段活用の未然形
      N0: 当該活用形のモーラ数, M0: 基本形のアクセント型, M: 修飾価

- **资料三 NHK Ⅲ-2 4.1 付属語決定型**（数値验证）：意志推量形（タベヨ＼ー、
  ノモ＼ー、ヨモ＼ー——M1@1 = N0−1）、たかった（〜タ＼カッタ——M2@2 = N0−2）、
  たけれ（〜タ＼ケレバ）与 表9 公式逐字吻合；M1/M2 应用时前部（動詞/形容詞）核消失
  （付属語決定型：動詞部分のアクセントが消え，付属語のアクセントが生きる）；
- **资料三 NHK Ⅲ-2 活用形一覧表**：命令形（食べろ タベ＼ロ、見ろ ミ＼ロ、
  飲め ノ＼メ、来い コ＼イ、する→しろ シロ━）——本模块对 ``cForm=命令形`` 的
  動詞 token 按「base 0 型→保持平板；否则 N0−1」实现（词典该形态无 aMod 数据）。

规则清单：

- ``R-CONJ-MOD``：表9 アクセント修飾型（M1@M/M2@M/M4@M）＋ 命令形（NHK 一览表）。
  优先级 280——依契约默认链「核合法性 > **活用形** > 复合词 > 付属語 …」，
  先于复合词（250）与词典直取（100）处理活用形 token。
"""

from __future__ import annotations

import logging

import mora_util
from stage2_rules.base import MorphList, MorphState, Rule, RulePhase, parse_accent_value
from stage2_rules.particles import TA_TE_SHORT, TA_TE_TARA

logger = logging.getLogger(__name__)

#: 表9 修飾型应用时允许被置平的前部品詞（付属語決定型：動詞部分のアクセントが消える）
_FRONT_POS_TO_FLATTEN: frozenset[str] = frozenset({"動詞", "形容詞", "形状詞"})

#: た形・て形家族（た/だ/て/で/たら/だら/たり/だり）：由 R-PART-TA-TE（NHK Ⅲ-2
#: 活用形一覧表）处理；词典中 たら/だら 携带的 M2@1 数据与该表冲突，按资料三优先排除。
_TA_TE_FAMILY: frozenset[str] = TA_TE_SHORT | TA_TE_TARA


class ConjModRule(Rule):
    """表9 アクセント修飾型 ＋ 命令形（详见模块 docstring）。"""

    rule_id = "R-CONJ-MOD"
    name = "活用形・アクセント修飾型（表9）＋命令形"
    source_ref = "资料二 UniDic 表9＋ 资料三 NHK Ⅲ-2 4.1/活用形一覧表"
    priority = 280
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.accent is not None or morph.claimed:
            return False
        # た・て 家族（動詞接续）让位 R-PART-TA-TE（NHK Ⅲ-2 活用形一覧表，
        # 词典 たら/だら 的 M2@1 数据与该表冲突时以资料三为准）
        if (
            morph.pos_head in ("助詞", "助動詞")
            and mora_util.strip_brackets(morph.pron) in _TA_TE_FAMILY
            and i > 0
            and morphs[i - 1].pos_head == "動詞"
        ):
            return False
        a_mod = morph.a_mod_type.strip().upper()
        if a_mod.startswith(("M1@", "M2@", "M4@")):
            return True
        # 命令形（词典无 aMod 数据；NHK Ⅲ-2 活用形一覧表）
        return morph.conj_form == "命令形" and morph.pos_head == "動詞"

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        front = morphs[i - 1] if i > 0 else None
        a_mod = morph.a_mod_type.strip().upper()
        n0 = morph.mora_count
        flattened = False

        if a_mod:
            m_type, _, param = a_mod.partition("@")
            modifier = int(param) if param.lstrip("-").isdigit() else 1
            base = self._base_accent(front, morph)

            if m_type == "M1":
                # 意志推量形：N0 − M（无 0 型分支；实测 タベヨ＼ー/ノモ＼ー 一致）
                morph.accent = max(0, n0 - modifier)
                logic = (
                    f"表9 M1@{modifier}（意志推量形 等）→ 活用形アクセント型 = "
                    f"N0 − M（{n0} − {modifier} = {morph.accent}）"
                )
            elif m_type == "M2":
                flattened = self._flatten_front(front)
                if base == 0:
                    morph.accent = 0
                    logic = (
                        f"表9 M2@{modifier}（一段・サ変命令形 等）→ 基本形 0 型 → "
                        "保持平板（M0 = 0）；前部置平"
                    )
                else:
                    morph.accent = max(0, n0 - modifier)
                    logic = (
                        f"表9 M2@{modifier}（一段・サ変命令形 等）→ 基本形非 0 型 → "
                        f"N0 − M（{n0} − {modifier} = {morph.accent}）；前部核消失（付属語決定型）"
                    )
            else:  # M4（一段活用の未然形）
                if base == 0:
                    morph.accent = 0
                    logic = f"表9 M4@{modifier}（一段活用の未然形）→ 基本形 0 型 → 保持平板（M0 = 0）"
                else:
                    morph.accent = max(0, base - modifier)
                    logic = (
                        f"表9 M4@{modifier}（一段活用の未然形）→ 基本形非 0 型 → "
                        f"M0 − M（{base} − {modifier} = {morph.accent}）"
                    )
        else:
            # 命令形（NHK Ⅲ-2 活用形一覧表：タベ＼ロ、ノ＼メ、コ＼イ、シロ━）
            base = self._base_accent(front, morph)
            if base == 0:
                morph.accent = 0
                logic = "命令形（NHK Ⅲ-2 活用形一覧表）→ 基本形 0 型 → 保持平板（シロ━）"
            else:
                morph.accent = max(1, min(base, n0 - 1))
                logic = (
                    f"命令形（NHK Ⅲ-2 活用形一覧表）→ 核位置 = min(基本形型, N0 − 1)"
                    f"（{base} / {n0 - 1} → {morph.accent}；タベ＼ロ、ノ＼メ）"
                )

        morph.derived_by = self.rule_id
        start = i - 1 if flattened else i
        result = morphs.render_range(start, i)
        morphs.add_report(self, (start, i), logic, result)

    @staticmethod
    def _base_accent(front: MorphState | None, morph: MorphState) -> int:
        """基本形のアクセント型（M0）：前部（已推导）优先，否则取本 token 的词典值。"""
        if front is not None and front.accent is not None and not front.claimed:
            return front.accent
        base, _ = parse_accent_value(morph.accent_raw)
        return base if base is not None else 0

    def _flatten_front(self, front: MorphState | None) -> bool:
        """付属語決定型：前部（動詞/形容詞/形状詞）の核を消失させる。

        返回是否实际置平（用于报告 target 区间判定）。
        """
        if front is None or front.claimed or front.accent is None:
            return False
        if front.pos_head in _FRONT_POS_TO_FLATTEN:
            front.accent = 0
            front.derived_by = self.rule_id
            return True
        return False
