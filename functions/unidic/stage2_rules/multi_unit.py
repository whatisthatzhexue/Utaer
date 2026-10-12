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

from stage2_rules.base import MorphList, Rule, RulePhase, Unit

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
                or morph.is_symbol          # 标点等记号并入前单位
                or prev.join_next           # 复合词/接辞合并标记
                or prev.pos_head == "接頭辞"  # 接头辞与其后续词同单位
            )
        )
        if not attach:
            units.append(Unit(unit_id=len(units), start=start, end=i - 1))
            start = i
    units.append(Unit(unit_id=len(units), start=start, end=len(morphs) - 1))
    return units


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
