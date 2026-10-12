"""复合词规则（资料二 UniDic 手册 表10 C1–C5 ＋ 资料三 NHK Ⅰ複合名詞）。

依据（四合一，已逐项核对）：

- **资料二 UniDic 手册 6.3–6.7 表10「アクセント結合型分類（普通名詞・接尾辞）」**
  （本模块规则的直接实现对象；结合型为词典原生字段 ``MorphState.a_con_type``，
  实测核对：税/席=C3、心(ココロ)=C1、油=C2、島/系=C4）::

      結合型  複合語のアクセント型   例（後部要素）      对应 NHK Ⅰ複合名詞 四型
      C1      N1 + M2              手続き, 日間        後部保存型
      C2      N1 + 1               生活, 時間          後部一型
      C3      N1                   湾, 学              前部末型
      C4      0                    島, 系              平板型
      C5      M1                   殿                  前部アクセント保持
      N1: 前部要素のモーラ数, M1: 前部要素のアクセント型, M2: 後部要素のアクセント型

- **资料三 NHK Ⅰ複合名詞**（拍数倾向，用于后部无结合型字段时的确定性兜底判定）：
  后部 1–2 拍 → 几乎全为前部末型（部分平板例外 〜語・化・間・顔・級・金・性・製・的）；
  后部 3–4 拍 → 平板/頭高（尾高）的后部词为後部一型，其余为後部保存型；
  后部 ≥5 拍 → 後部保存型；
- **平板例外表优先级**（NHK Ⅰ複合名詞 ①原文「一部分は平板型：《例》〜語，〜化，〜間
  （1拍）；〜顔，〜級，〜金，〜性，〜製，〜的（2拍）」）：上述后部要素默认
  **优先于词典 C 值** 取 C4 平板型（资料三惯例优先，如 語 的词典值 C3 → 平板；
  例：日本語（日本+語 切分时）→ 平板）。可在 rules_config.json 的
  ``compound.nhk_flat_exceptions_priority`` 置 false 恢复词典严密优先；
- 前部末型遇前部末拍为特殊拍/二重母音副音 → 由 ``R-NUCLEUS-SPECIAL``（校验遍）
  前移核，形成完整链路（住民税：C3 → ジューミン＼ゼイ → 移位 → ジューミ＼ンゼイ）。

规则清单：

- ``R-COMPOUND-C1``（後部保存型）、``R-COMPOUND-C2``（後部一型）、
  ``R-COMPOUND-C3``（前部末型，受理样例 2 依据）、``R-COMPOUND-C4``（平板型）、
  ``R-COMPOUND-C5``（前部アクセント保持）；各规则同时处理「后部无结合型字段」时的
  NHK 拍数规律兜底判定。
"""

from __future__ import annotations

import logging

from stage2_rules.base import MorphList, MorphState, Rule, RulePhase, parse_accent_value

logger = logging.getLogger(__name__)

#: 有效结合型值（资料二 表10）
CONNECTION_TYPES: frozenset[str] = frozenset({"C1", "C2", "C3", "C4", "C5"})

#: NHK Ⅰ複合名詞：后部 1–2 拍中的平板例外（〜語・化・間・顔・級・金・性・製・的）
FLAT_REAR_EXCEPTIONS: frozenset[str] = frozenset({
    "語", "化", "間", "顔", "級", "金", "性", "製", "的",
})

#: 复合词的合法前部/后部品詞（资料二 表10 标题：普通名詞・接尾辞）
FRONT_POS_HEADS: frozenset[str] = frozenset({"名詞"})
REAR_POS_HEADS: frozenset[str] = frozenset({"名詞", "接尾辞"})


def _eligible_pair(morphs: MorphList, i: int) -> bool:
    """判断 [i, i+1] 是否为可结合的名词对（双方未推导、未占用）。"""
    if i < 0 or i + 1 >= len(morphs):
        return False
    front, rear = morphs[i], morphs[i + 1]
    if front.claimed or rear.claimed or front.accent is not None or rear.accent is not None:
        return False
    if front.pos_head not in FRONT_POS_HEADS or rear.pos_head not in REAR_POS_HEADS:
        return False
    if front.mora_count <= 0 or rear.mora_count <= 0:
        return False
    return True


def _rear_connection_type(rear: MorphState, nhk_flat_first: bool = True) -> str | None:
    """返回后部要素的结合型（确定性判定，见模块 docstring）。

    - ``nhk_flat_first``（默认 true）：``FLAT_REAR_EXCEPTIONS``（NHK Ⅰ複合名詞 ①
    原文列出的「一部分平板型」：〜語・化・間・顔・級・金・性・製・的）**优先**于
    词典 C 值 → C4 平板型（资料三 NHK 惯例优先，可在 rules_config.json 的
    ``compound.nhk_flat_exceptions_priority`` 关闭）；
    - ``a_con_type`` 为 C1–C5 → 直接采用（资料二，确切匹配）；
    - ``a_con_type`` 为空 → NHK Ⅰ複合名詞 拍数规律（资料三）；
    - 其他值（P 系列接頭辞 / F 系列付属語）→ 非复合词结合型，返回 None。
    """
    if nhk_flat_first and rear.morph in FLAT_REAR_EXCEPTIONS:
        return "C4"
    a_con = rear.a_con_type.strip().upper()
    if a_con in CONNECTION_TYPES:
        return a_con
    if a_con:  # P 系列 / F 系列字符串（如 "名詞%F1"）——非本规则处理对象
        return None
    # —— 无结合型字段：NHK 拍数规律兜底（資料三） ——
    mora = rear.mora_count
    main, _ = parse_accent_value(rear.accent_raw)
    if mora <= 2:
        return "C4" if rear.morph in FLAT_REAR_EXCEPTIONS else "C3"
    if mora <= 4:
        if main is None:
            return "C1"
        if main in (0, 1) or main == mora:   # 平板・頭高・尾高 → 後部一型
            return "C2"
        return "C1"                          # 中高 → 後部保存型
    return "C1"                              # 5 拍以上 → 後部保存型


class _CompoundBase(Rule):
    """复合词规则公共实现（表10 公式应用；各 C 型由子类指定 ``c_type``）。"""

    c_type: str = ""                      # "C1".."C5"
    c_name: str = ""                      # 四型中文名
    priority = 250
    phase = RulePhase.DERIVATION
    config_section = "compound"           # rules_config.json 的 compound 节注入 options

    def _nhk_flat_first(self) -> bool:
        """NHK 平板例外表是否优先于词典 C 值（默认 true，可配置）。"""
        return bool(self.options.get("nhk_flat_exceptions_priority", True))

    def match(self, morphs: MorphList, i: int) -> bool:
        if not _eligible_pair(morphs, i):
            return False
        return _rear_connection_type(morphs[i + 1], self._nhk_flat_first()) == self.c_type

    def apply(self, morphs: MorphList, i: int) -> None:
        front, rear = morphs[i], morphs[i + 1]
        n1 = front.mora_count
        m1, _ = parse_accent_value(front.accent_raw)
        m2, _ = parse_accent_value(rear.accent_raw)

        if self.c_type == "C1":            # N1 + M2（後部保存型）
            front.accent = 0
            rear.accent = m2 if m2 is not None else 0
            formula = f"N1 + M2（{n1} + {rear.accent} = {n1 + rear.accent}）"
        elif self.c_type == "C2":          # N1 + 1（後部一型）
            front.accent = 0
            rear.accent = 1
            formula = f"N1 + 1（{n1} + 1 = {n1 + 1}）"
        elif self.c_type == "C3":          # N1（前部末型）
            front.accent = n1
            rear.accent = 0
            formula = f"N1（前部要素のモーラ数 {n1}）"
        elif self.c_type == "C4":          # 0（平板型）
            front.accent = 0
            rear.accent = 0
            formula = "0"
        else:                              # C5：M1（前部アクセント保持）
            front.accent = m1 if m1 is not None else 0
            rear.accent = 0
            formula = f"M1（前部要素のアクセント型 {front.accent}）"

        rear.claimed = True
        front.join_next = True
        front.derived_by = self.rule_id
        rear.derived_by = self.rule_id

        if self._nhk_flat_first() and rear.morph in FLAT_REAR_EXCEPTIONS:
            from_field = "NHK Ⅰ複合名詞 ①平板例外表（〜語・化・間・顔・級・金・性・製・的；资料三优先）"
        elif rear.a_con_type.strip().upper() in CONNECTION_TYPES:
            from_field = "C1–C5（資料二 表10）"
        else:
            from_field = "无结合型字段，按 NHK Ⅰ複合名詞 拍数规律兜底判定"
        logic = (
            f"后部要素「{rear.morph}」アクセント結合型 {self.c_type} → "
            f"複合語アクセント型 = {formula} ＝{self.c_name}；依据：{from_field}"
        )
        morphs.add_report(self, (i, i + 1), logic, morphs.render_range(i, i + 1))


class CompoundC1Rule(_CompoundBase):
    """C1：複合語アクセント型 = N1 + M2（後部保存型；表10）。"""

    rule_id = "R-COMPOUND-C1"
    name = "复合词・後部保存型"
    source_ref = "资料二 UniDic 表10 C1＋ 资料三 NHK Ⅰ複合名詞 1.3）"
    c_type = "C1"
    c_name = "後部保存型"


class CompoundC2Rule(_CompoundBase):
    """C2：複合語アクセント型 = N1 + 1（後部一型；表10）。"""

    rule_id = "R-COMPOUND-C2"
    name = "复合词・後部一型"
    source_ref = "资料二 UniDic 表10 C2＋ 资料三 NHK Ⅰ複合名詞 1.1）／2.1）②"
    c_type = "C2"
    c_name = "後部一型"


class CompoundC3Rule(_CompoundBase):
    """C3：複合語アクセント型 = N1（前部末型；表10；受理样例 2 依据）。"""

    rule_id = "R-COMPOUND-C3"
    name = "复合词・前部末型"
    source_ref = "NHK Ⅰ複合名詞 1.2）＋ UniDic 表10 C3"
    c_type = "C3"
    c_name = "前部末型"


class CompoundC4Rule(_CompoundBase):
    """C4：複合語アクセント型 = 0（平板型；表10）。"""

    rule_id = "R-COMPOUND-C4"
    name = "复合词・平板型"
    source_ref = "资料二 UniDic 表10 C4＋ 资料三 NHK Ⅰ複合名詞 1.4）"
    c_type = "C4"
    c_name = "平板型"


class CompoundC5Rule(_CompoundBase):
    """C5：複合語アクセント型 = M1（前部アクセント保持；表10）。"""

    rule_id = "R-COMPOUND-C5"
    name = "复合词・前部アクセント保持"
    source_ref = "资料二 UniDic 表10 C5"
    c_type = "C5"
    c_name = "前部アクセント保持"
