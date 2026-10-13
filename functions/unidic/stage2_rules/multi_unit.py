"""多单位/句级规则（资料三 NHK Ⅲ全般 4. 複数の単位からなる語 ＋ 资料四 アクセント単位）。

依据：

- NHK Ⅲ全般 4.：「韻律上の 1 つの単位」内に「下がり目」が 1 か所か、あるいはゼロ
  （平板式）——**每个アクセント単位至多一个核**；2 単位形用中点「・」表示；
- 资料四（Wikipedia 东京式理论）：a minor phrase can have maximally one nucleus；
- 单位切分（确定性）：付属語（助詞/助動詞/接尾辞）与记号并入前部；
  接头辞（お・ご 等）与其后续词同单位；复合词规则以 ``join_next`` 标记合并区间；
  其余自立语各自开启新单位。

规则清单：

- ``R-MULTI-UNIT``：整句规则（``whole_sequence``），在逐形态素推导后执行：
  切分アクセント単位、分配 ``unit_id``、校验「每单位至多一个核」，
  并以「・」连接各单位渲染（如 ``コメ＼オ・モル━``）。
"""

from __future__ import annotations

import logging

import mora_util
from stage2_rules.base import MorphList, Rule, RulePhase, Unit
from stage2_rules.particles import KIFUKU_FALLBACK

logger = logging.getLogger(__name__)


def compute_units(morphs: MorphList) -> list[Unit]:
    """按 NHK 複数単位规则切分アクセント単位（确定性，见模块 docstring）。

    ``new_unit`` 标记（如起伏式付属語核作为第 2 単位）优先于一切并入规则。
    """
    if not morphs:
        return []
    units: list[Unit] = []
    start = 0
    for i in range(1, len(morphs)):
        morph = morphs[i]
        prev = morphs[i - 1]
        attach = (
            not morph.new_unit               # 强制新単位标记优先（起伏式付属語第 2 単位等）
            and (
                morph.is_particle_like      # 付属語紧跟前部（NHK Ⅲ-1 付属語不干渉）
                # 标点等无读音记号并入前单位；有读音的记号形（如（笑）→ワライ）独立成単位
                or (morph.is_symbol and not morph.pron)
                or prev.join_next           # 复合词/接辞合并标记
                # 接头辞与其后续词同单位——但自带调型的接头辞独立成単位
                # （用例对照：第3期が → ダ＼イ・サ＼ンキガ；お米 的 お 无调型仍并入）
                or (prev.pos_head == "接頭辞" and not prev.accent_raw)
                # サ変（動詞-非自立可能）并入前部単位：
                # 名詞＋し/する（勉強+し）或 て/で＋补助动词（〜て+いる → イッテイタ）；
                # 主用言用法（買い物に+行き）不并入；
                # 命令形补助动词（〜して＋ください 用例对照：サンコーニ━・シテ━・クダサ＼イ）独立成単位
                or (
                    morph.pos_head == "動詞"
                    and "非自立" in morph.pos
                    and morph.conj_form != "命令形"
                    and (
                        prev.pos_head == "名詞"
                        or (
                            prev.pos_head == "助詞"
                            and mora_util.strip_brackets(prev.pron) in ("テ", "デ")
                        )
                    )
                )
                # 非自立の ない/なる（形容词接续，NHK Ⅲ-3 1.2）并入前部単位：
                # 如 アマクナ＼イ；起伏式第 2 単位由 new_unit 排除（高くない → タカ＼ク・ナ＼イ）；
                # 主用言用法（買い物に+行き）不并入
                or (
                    "非自立" in morph.pos
                    and morph.pos_head in ("形容詞", "動詞")
                    and mora_util.strip_brackets(morph.pron) in KIFUKU_FALLBACK
                )
            )
        )
        if not attach:
            units.append(Unit(unit_id=len(units), start=start, end=i - 1))
            start = i
    units.append(Unit(unit_id=len(units), start=start, end=len(morphs) - 1))
    return units


#: 指示副詞＋いう 的定型複合単位（用例对照：そういう → ソーユー━）
_SHIIU_FRONTS: frozenset[str] = frozenset({"そう", "こう", "どう", "ああ"})


class UnitJoinRule(Rule):
    """定型複合単位：指示副詞＋「いう」（そういう→ソーユー━ 等）。

    前部（そう/こう/どう/ああ）与「いう」合并为单一アクセント単位并整体平板化
    （NHK アクセント慣例；用例对照：そういう中 → ソーユー━・ナ＼カデ）。
    """

    rule_id = "R-UNIT-JOIN"
    name = "定型複合単位（そういう 等）"
    source_ref = "NHK アクセント慣例（そういう→ソーユー━；用例对照）"
    priority = 220
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if i + 1 >= len(morphs):
            return False
        front, rear = morphs[i], morphs[i + 1]
        if front.claimed or rear.claimed or front.accent is not None or rear.accent is not None:
            return False
        return front.morph in _SHIIU_FRONTS and rear.morph == "いう"

    def apply(self, morphs: MorphList, i: int) -> None:
        front, rear = morphs[i], morphs[i + 1]
        front.accent = 0
        rear.accent = 0
        front.join_next = True
        rear.claimed = True
        front.derived_by = rear.derived_by = self.rule_id
        logic = (
            f"「{front.morph}いう」为定型複合（NHK アクセント慣例 ソーユー━）→ "
            "合并为单一アクセント単位并整体平板化"
        )
        morphs.add_report(self, (i, i + 1), logic, morphs.render_range(i, i + 1))


class NumTwoUnitRule(Rule):
    """数詞＋助数詞の2単位語（NHK Ⅱ 1. 2）②）。

    NHK Ⅱ 明文：「15」（一部「14（ジューヨ）」「19（ジューク）」も）に **2拍以下の
    助数詞** が付く場合は中点「・」でアクセント単位を区切り2単位語とする
    （例：ジュ＼ー・ゴネン━，1単位形 ジュ＼ーゴネン 并记）。

    本规则覆盖 MeCab 拆分为 ``[十][四|五|九][助数詞]`` 的形态：
    第 1 単位 = 十（頭高 ジュ＼ー）；第 2 単位 = 一の位＋助数詞（平板 ゴネン━）。
    该拆分的连续性由 ``new_unit``/``join_next`` 标记交给 R-MULTI-UNIT 渲染。

    范围说明：「21〜99（10の倍数除く）」的2単位形因仓库内无 NHK Ⅱ 助数詞一覧表
    数据（无法确定切分位置）暂未实现。
    """

    rule_id = "R-NUM-TWO-UNIT"
    name = "数詞＋助数詞・2単位語（15/14/19）"
    source_ref = "NHK Ⅱ 1. 2）②（2単位語：ジュ＼ー・ゴネン━）"
    priority = 260                       # 先于复合词 C 规则（250）处理数词链
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if i + 2 >= len(morphs):
            return False
        ten, unit_digit, counter = morphs[i], morphs[i + 1], morphs[i + 2]
        if ten.claimed or unit_digit.claimed or counter.claimed:
            return False
        if ten.accent is not None or unit_digit.accent is not None or counter.accent is not None:
            return False
        if ten.morph != "十" or unit_digit.morph not in ("四", "五", "九"):
            return False
        if ten.pos_head != "名詞" or unit_digit.pos_head != "名詞":
            return False
        if counter.mora_count <= 0 or counter.mora_count > 2:   # 2拍以下の助数詞
            return False
        return "助数詞" in counter.pos or counter.pos_head == "接尾辞"

    def apply(self, morphs: MorphList, i: int) -> None:
        ten, unit_digit, counter = morphs[i], morphs[i + 1], morphs[i + 2]
        ten.accent = 1                    # ジュ＼ー（頭高）
        unit_digit.accent = 0             # 第2単位（一の位＋助数詞，平板）
        unit_digit.new_unit = True
        unit_digit.join_next = True
        counter.accent = 0
        counter.claimed = True
        ten.derived_by = unit_digit.derived_by = counter.derived_by = self.rule_id
        logic = (
            f"数詞「十{unit_digit.morph}」（NHK Ⅱ 2単位語：15/14/19＋2拍以下助数詞）→ "
            f"中点分隔：第1単位 十（頭高）・第2単位 「{unit_digit.morph}{counter.morph}」（平板）"
        )
        result = morphs.render_range(i, i) + "・" + morphs.render_range(i + 1, i + 2)
        morphs.add_report(self, (i, i + 2), logic, result)


class MultiUnitRule(Rule):
    """複数単位（句级）：切分アクセント単位并渲染整句（每单位至多一个核）。"""

    rule_id = "R-MULTI-UNIT"
    name = "複数単位（句级）"
    source_ref = "NHK Ⅲ全般 4.（複数の単位からなる語）"
    priority = 150
    phase = RulePhase.DERIVATION
    whole_sequence = True

    def match(self, morphs: MorphList, i: int) -> bool:  # pragma: no cover - 整句规则
        """整句规则不走逐 idx 扫描（见 run_engine），恒返回 False。"""
        return False

    def apply(self, morphs: MorphList, i: int = 0) -> None:
        units = compute_units(morphs)
        morphs.units = units
        for unit in units:
            for k in range(unit.start, unit.end + 1):
                morphs[k].unit_id = unit.unit_id

        if len(units) < 2:
            # 单一アクセント単位：无「・」分隔语义，不登记报告
            return

        names = ["「" + morphs.surface_text(u.start, u.end) + "」" for u in units]
        joined = names[0] + "与" + names[1] if len(names) == 2 else "、".join(names)
        logic = f"{joined}各为独立アクセント単位；每单位至多一个核"
        morphs.add_report(self, (0, len(morphs) - 1), logic, morphs.render_units())
