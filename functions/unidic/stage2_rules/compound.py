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
- ``R-COMPOUND-NAME-TITLE``：个人名＋肩書き不复合（NHK Ⅰ 2））；
- ``R-COMPOUND-HEAD-TYPE``：**后部一型要素表**（NHK Ⅰ ② 〜主義・〜価値・〜都市）——
  词典已合并为整体词条（完璧主義）时的后部定调路径。
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

#: 不参与 C 系列复合的接尾辞（结合式的形容词性接尾辞）
#:
#: 「らしい」作**接尾辞**时（完璧主義らしい・人間らしい）不是复合名词的后部要素——
#: 前部核的存续由 ``R-PART-RASHII``（校验遍）按前件定稿核位判定。若在此放行，
#: ``R-COMPOUND-C1`` 会在 i=0 就吃掉整组并把前件置平，使 ``R-COMPOUND-HEAD-TYPE``
#: 无从修正前件核位。（助動詞らしい——米らしい等——本就不在 REAR_POS_HEADS 内。）
NON_COMPOUND_REAR: frozenset[str] = frozenset({"らしい", "ラシイ"})

#: NHK Ⅰ複合名詞 ②「後部要素が２拍の場合は後部一型となる場合もある
#: 《例》〜価値，〜主義，〜都市など」——后部一型要素表： 表層形 → (读音, 拍数)。
#:
#: 词典把「完璧主義」这类整体词条以**推断值**收录（発音字段 ``カ[ンペキ]シュギ``
#: → 核 4），而 NHK 以**后部要素**定调（〜主義＝後部一型）→ 前部拍数 + 1。
#: 可在 rules_config.json 的 ``compound.head_type_elements`` 覆盖/扩充。
HEAD_TYPE_ELEMENTS: dict[str, tuple[str, int]] = {
    "主義": ("シュギ", 2),
    "価値": ("カチ", 2),
    "都市": ("トシ", 2),
}

#: NHK Ⅰ複合名詞 2）的肩書き（〜氏・名人・博士 等；个人名不复合规则对象）
TITLE_WORDS: frozenset[str] = frozenset({
    "氏", "名人", "博士", "監督", "議員", "教授", "司令官", "大臣", "長官",
})

#: 和語数詞（词典 pos 标注不可靠时的兜底；数詞＋普通名詞不复合，用例对照：
#: ひとつ中止 → ヒト＼ツ・チューシニ━）
WAGO_NUMERALS: frozenset[str] = frozenset({
    "ひとつ", "ふたつ", "みっつ", "よっつ", "いつつ", "むっつ",
    "ななつ", "やっつ", "ここのつ", "とお", "いくつ",
})


def _is_numeral_front(morph: MorphState) -> bool:
    """前部是否为数詞（pos 的 ``数詞`` 标注、和语数詞表、或含阿拉伯数字的表記）。

    含阿拉伯数字的词（如 10月・2日）与后续普通名词在韵律上是独立単位
    （用例对照：10月｜2日 → ジューガツ━・フツカ━）。
    """
    return (
        "数詞" in morph.pos
        or morph.morph in WAGO_NUMERALS
        or any(ch.isascii() and ch.isdigit() for ch in morph.morph)
    )


def _is_counter_rear(morph: MorphState) -> bool:
    """後部是否为助数詞性要素（接尾辞・助数詞可能・数詞——数詞+助数詞的复合仍要走 C 规则）。"""
    return (
        morph.pos_head == "接尾辞"
        or "助数詞" in morph.pos
        or "数詞" in morph.pos
    )

#: 复合词的合法前部/后部品詞（资料二 表10 标题：普通名詞・接尾辞）
FRONT_POS_HEADS: frozenset[str] = frozenset({"名詞"})
REAR_POS_HEADS: frozenset[str] = frozenset({"名詞", "接尾辞"})


def _eligible_pair(morphs: MorphList, i: int) -> bool:
    """判断 [i, i+1] 是否为可结合的名词对（双方未推导、未占用）。

    数詞（含和语数词表）＋普通名词（非助数詞性）不复合——数词与被数词在韵律上
    是独立的アクセント単位（用例对照：ひとつ中止 → ヒト＼ツ・チューシニ━）。
    """
    if i < 0 or i + 1 >= len(morphs):
        return False
    front, rear = morphs[i], morphs[i + 1]
    if front.claimed or rear.claimed or front.accent is not None or rear.accent is not None:
        return False
    if front.pos_head not in FRONT_POS_HEADS or rear.pos_head not in REAR_POS_HEADS:
        return False
    if rear.pos_head == "接尾辞" and rear.morph in NON_COMPOUND_REAR:
        return False                       # 结合式接尾辞らしい → R-PART-RASHII 专管
    if front.mora_count <= 0 or rear.mora_count <= 0:
        return False
    if _is_numeral_front(front) and not _is_counter_rear(rear):
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
    # NHK Ⅰ 2）：普通语素＋肩書き（〜氏/名人/博士/監督 等）复合为 1 単位的默认型
    # ＝後部一型（釣り名人 → ツリメ＼ージン、文学博士 → ブンガクハ＼クシ）
    if rear.morph in TITLE_WORDS and mora <= 4:
        return "C2"
    if mora <= 2:
        return "C4" if rear.morph in FLAT_REAR_EXCEPTIONS else "C3"
    if mora <= 4:
        if main is None:
            return "C1"
        if main in (0, 1) or main == mora:   # 平板・頭高・尾高 → 後部一型
            return "C2"
        return "C1"                          # 中高 → 後部保存型
    # 5 拍以上：後部保存型——后部自身调型完整保留，作为独立アクセント単位呈现
    # （不合并单位；用例对照：中国｜南東部の → チュ＼ーゴク・ナント＼ーブノ）
    return None


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


class CompoundNameTitleRule(Rule):
    """个人名＋肩書き・不复合（2アクセント単位；NHK Ⅰ複合名詞 2））。

    NHK 原文：「前部要素が『高橋，佐藤，清水』など，**個人名**の場合には，
    複合しない（アクセント単位としては，２単位）」（タカ＼ハシ・メージ＼ン）。

    判别：前部品詞に ``人名`` 包含（固有名詞-人名-姓/名 等）。前部・肩書き
    各自保持词典调型，肩書き以 ``new_unit`` 开启第 2 単位。

    注：本机词典对部分姓氏的品詞标注为 固有名詞-一般（无 人名 细分类），
    此类前部的 2 単位化无法确定性判别，按复合路径处理（拍数规律）。
    """

    rule_id = "R-COMPOUND-NAME-TITLE"
    name = "个人名＋肩書き・不复合（2単位）"
    source_ref = "NHK Ⅰ複合名詞 2）（タカ＼ハシ・メージ＼ン）"
    priority = 255                        # 先于复合词 C 规则（250）
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if not _eligible_pair(morphs, i):
            return False
        front, rear = morphs[i], morphs[i + 1]
        return "人名" in front.pos and rear.morph in TITLE_WORDS

    def apply(self, morphs: MorphList, i: int) -> None:
        front, rear = morphs[i], morphs[i + 1]
        front_main, _ = parse_accent_value(front.accent_raw)
        rear_main, _ = parse_accent_value(rear.accent_raw)
        front.accent = front_main if front_main is not None else 0
        rear.accent = rear_main if rear_main is not None else 0
        rear.new_unit = True
        rear.claimed = True
        front.derived_by = rear.derived_by = self.rule_id
        logic = (
            f"前部「{front.morph}」为个人名（固有名詞-人名）→ 依 NHK Ⅰ 2）不复合："
            f"2アクセント単位（前部「{front.morph}」・肩書き「{rear.morph}」各自保留调型）"
        )
        result = morphs.render_range(i, i) + "・" + morphs.render_range(i + 1, i + 1)
        morphs.add_report(self, (i, i + 1), logic, result)


class CompoundHeadTypeRule(Rule):
    """后部一型要素表：〜主義／〜価値／〜都市（NHK Ⅰ複合名詞 ②）。

    NHK 原文：「なお，後部要素が２拍の場合は後部一型となる場合もある。
    《例》〜価値，〜主義，〜都市など。」

    词典把「完璧主義」这类词以**推断值**整体收录（発音字段 ``カ[ンペキ]シュギ``
    → 核 4），NHK 规则以**后部要素**定调 → 複合語アクセント型 = 前部拍数 + 1
    （完璧主義：6 − 2 + 1 = 5 → カンペキシュ＼ギ）。

    判定按**读音后缀**（表内要素自身不适用：``mora_count <= 後部拍数`` 时跳过），
    故 主義・価値・都市 単独、以及 年（トシ=2 拍）等同音短词不受影响。
    """

    rule_id = "R-COMPOUND-HEAD-TYPE"
    name = "复合词・后部一型要素表（〜主義・〜価値・〜都市）"
    source_ref = "NHK Ⅰ複合名詞 ②（後部要素が２拍の場合は後部一型となる場合もある）"
    priority = 240
    phase = RulePhase.DERIVATION
    config_section = "compound"

    def _table(self) -> dict[str, tuple[str, int]]:
        """后部一型要素表（rules_config.json 的 ``compound.head_type_elements`` 可覆盖）。"""
        raw = self.options.get("head_type_elements")
        if isinstance(raw, dict) and raw:
            table: dict[str, tuple[str, int]] = {}
            for surface, value in raw.items():
                if isinstance(value, dict):
                    kana, moras = value.get("kana", ""), value.get("moras", 0)
                elif isinstance(value, (list, tuple)) and len(value) == 2:
                    kana, moras = value[0], value[1]
                else:
                    continue
                try:
                    moras_int = int(moras)
                except (TypeError, ValueError):
                    continue
                if kana and moras_int > 0:
                    table[str(surface)] = (str(kana), moras_int)
            if table:
                return table
        return HEAD_TYPE_ELEMENTS

    def _head_type_of(self, morph: MorphState) -> tuple[str, str, int] | None:
        """返回 ``(表層形, 读音, 拍数)``；非后部一型要素词条则返回 None。

        **表記（漢字）と读音の両方**が一致することを要求する——読みだけでは
        同音の和語と衝突するため（用例对照：今年（コトシ）は 〜都市（トシ）と
        末尾 2 拍が一致するが、後部一型要素ではない）。
        """
        for surface, (kana, moras) in self._table().items():
            if morph.mora_count <= moras:
                continue                   # 该要素自身（主義・都市 等）不适用
            if morph.morph.endswith(surface) and morph.pron.endswith(kana):
                return surface, kana, moras
        return None

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.claimed or morph.accent is not None:
            return False
        if morph.pos_head not in ("名詞", "接尾辞"):
            return False
        return self._head_type_of(morph) is not None

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        surface, kana, moras = self._head_type_of(morph)
        accent = morph.mora_count - moras + 1
        morph.accent = accent
        morph.derived_by = self.rule_id
        logic = (
            f"「{morph.morph}」的末部为后部一型要素「〜{surface}（{kana}）」→ "
            f"依 NHK Ⅰ複合名詞 ② 複合語アクセント型 = 前部拍数 + 1"
            f"（{morph.mora_count} − {moras} + 1 = {accent}）"
        )
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))
