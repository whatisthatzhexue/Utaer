"""付属語接続规则（资料二 UniDic 表12 F 系列 ＋ 资料三 NHK Ⅲ-1 名词接付属語）。

依据（四合一，已逐项核对）：

- **资料三 NHK Ⅲ-1 总原则『付属語不干渉』**：绝大多数付属語不影响前接名词的声调；
- **资料二 UniDic 手册 6.3–6.7 表12「アクセント結合型分類（助詞・助動詞）」**
  ——付属語的词典原生字段 ``a_con_type`` 携带**按前部品詞区分的 F 系列规格**
  （实测：を=``…名詞%F1``、の=``名詞%F1``、まで=``名詞%F2@1``、ぐらい=``名詞%F4@1``、
  らしい=``名詞%F4@2``），按公式计算文節アクセント型::

      F1      → M1（前部要素のアクセント型保持＝付属語不干渉）
      F2@M    → 前部 0 型: N1 + M；それ以外: M1（M1 时付属語核作为第 2 単位存活，
                与 NHK Ⅲ-1 1.2b/c「形容词部分の核も生きる」一致）
      F3@M    → 前部 0 型: M1；それ以外: N1 + M
      F4@M    → N1 + M（付属語決定型；NHK Ⅲ-1 2.2 ぐらい・らしい の原生实现）
      F5      → 0
      F6@M, L → 前部 0 型: N1 + M；それ以外: N1 + L
      N1: 前部要素のモーラ数, M1: 前部要素のアクセント型, M/M,L: 付属語の核位置参数

- **资料三 NHK Ⅲ-1 例外 2.1**：「の」接尾高型名词 → 名词核消失、整体平板化
  （コメ＼＋ノ → コメノ━；数詞（日時・回数等）与无声化致尾高的词除外）——
  由 ``R-PART-NO-ODAKA``（优先级高于 F1 默认）实现；
- 付属語无 F 数据时（如 ほど=空、`[]` 解码词）回落 NHK Ⅲ-1 的手工表中转
  （平板式表 / 起伏式表 / 决定型表），逻辑与 F 系列同构。

规则清单：

- ``R-PART-FLAT``：平板式付属語・基本接続（F1 / NHK 表兜底；验收样例 1 依据）；
- ``R-PART-KIFUKU``：起伏式付属語（F2/F3/F5/F6 / NHK 表兜底；前部核与付属語核并存）；
- ``R-PART-NO-ODAKA``：「の」接尾高型平板化（NHK Ⅲ-1 2.1 例外）；
- ``R-PART-DECIDING``：付属語決定型（F4 / NHK 2.2；名词核消失、付属語核生效）。

范围说明：本模块按 MVP 深度限定**名词性前部**（NHK Ⅲ-1）；动词/形容词接付属語
（NHK Ⅲ-2/Ⅲ-3，词典 ``動詞%F…``/``形容詞%F…`` 数据已就绪）留待后续里程碑扩展。
"""

from __future__ import annotations

import logging

import mora_util
from stage2_rules.base import MorphList, MorphState, Rule, RulePhase

logger = logging.getLogger(__name__)

#: F 系列型名
F1, F2, F3, F4, F5, F6 = "F1", "F2", "F3", "F4", "F5", "F6"

#: 平板式付属語（1 拍全部；NHK Ⅲ-1 1.1）——无 F 数据时的兜底（按**発音**匹配）
FLAT_PARTICLES_1MORA: frozenset[str] = frozenset({
    "カ", "ガ", "ダ", "デ", "ト", "ニ", "ノ", "ワ", "エ", "モ", "ヤ", "オ",
})

#: 平板式付属語（2 拍以上的一部分；NHK Ⅲ-1 1.1）——兜底表
FLAT_PARTICLES_MULTI: frozenset[str] = frozenset({
    "カラ", "ダケ", "ッテ", "トシテ", "ホド",
})

#: 起伏式付属語（NHK Ⅲ-1 1.2；值=付属語自身核位置）——无 F 数据时的兜底
KIFUKU_FALLBACK: dict[str, int] = {
    "カモ": 1, "コソ": 1, "サエ": 1, "シカ": 1, "スラ": 1,
    "ダッタ": 1, "ダッテ": 1, "ダト": 1, "ダロー": 2,
    "デシタ": 1, "デショー": 2, "デス": 1, "デワ": 1, "デモ": 1,
    "トカ": 1, "トワ": 1, "トモ": 1,
    "ナド": 1, "ナノダ": 1, "ナノデ": 1, "ナノニ": 1,
    "ナラ": 1, "ナラバ": 1, "ナンカ": 1, "ナンテ": 1,
    "ニワ": 1, "ニモ": 1, "ノミ": 1, "バカリ": 1, "エワ": 1, "エモ": 1,
    "マデ": 1, "ミタイダ": 1, "ヨリ": 1,
}

#: 付属語決定型（NHK Ⅲ-1 2.2；值=付属語自身核位置）——无 F 数据时的兜底
DECIDING_FALLBACK: dict[str, int] = {
    "グライ": 1, "クライ": 1, "ラシイ": 2,
}

#: 「の」平板化例外的词表（NHK Ⅲ-1 2.1：顺序词等；数詞另按 pos 判定）
NO_ODAKA_EXCEPTION_WORDS: frozenset[str] = frozenset({
    "次", "よそ", "基地", "地下", "ヒ素", "一日",
})


def _parse_noun_f(a_con_type: str) -> tuple[str, list[int]] | None:
    """从 ``a_con_type``（如 ``"動詞%F2@0,名詞%F1"``）解析「名詞」项的 F 规格。

    返回 ``(F 型名, 参数列表)``；无「名詞%」项或格式异常时返回 None。
    ``F6@M, L`` 的双参数以续接数字项合并（``F6@1`` + ``2`` → ``F6@1,2``）。
    """
    items: list[str] = []
    for raw in a_con_type.split(","):
        item = raw.strip()
        if not item:
            continue
        if item.replace("-", "").isdigit() and items:   # 续接参数（如 F6@M, L）
            items[-1] += "," + item
        else:
            items.append(item)
    for item in items:
        if item.startswith("名詞%"):
            spec = item[len("名詞%"):]
            f_type, _, params = spec.partition("@")
            numbers = [
                int(p) for p in params.split(",") if p.strip().lstrip("-").isdigit()
            ]
            return f_type.strip().upper(), numbers
    return None


def _place_total(front: MorphState, morph: MorphState, total: int) -> None:
    """把「文節型 = total（下降核位于文節第 total 拍之后）」编码到前后两个形态素。

    - ``total`` ≤ 0 → 整体平板；
    - ``total`` ≤ 前部拍数 → 核在前部内部（前部接管核位置）；
    - 否则 → 前部平板、核位于付属語内部（``total - N1`` 拍之后）。
    """
    total = max(0, total)
    n1 = front.mora_count
    if total == 0:
        front.accent = 0
        morph.accent = 0
    elif total <= n1:
        front.accent = total
        morph.accent = 0
    else:
        front.accent = 0
        morph.accent = total - n1


def _eligible(morphs: MorphList, i: int) -> bool:
    """付属語规则的公共前置条件：名词性前部已推导、本形态素未推导未占用。"""
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
    return True


def _result_and_target(morphs: MorphList, i: int, morph: MorphState) -> tuple[str, tuple[int, int]]:
    """渲染报告 result：前部为平板且付属語核生效等情形由调用方选择单/双单位。

    单单位：render_range(i-1, i)；双单位（付属語核作为第 2 アクセント単位）：
    ``前部・付属語``。
    """
    if morph.new_unit:
        return (
            morphs.render_range(i - 1, i - 1) + "・" + morphs.render_range(i, i),
            (i - 1, i),
        )
    return morphs.render_range(i - 1, i), (i - 1, i)


class PartFlatRule(Rule):
    """平板式付属語・基本接続（F1＝付属語不干渉；验收样例 1 的 R-PART-FLAT）。"""

    rule_id = "R-PART-FLAT"
    name = "平板式付属語・基本接続"
    source_ref = "NHK Ⅲ-1 1.1（『付属語不干渉』）"
    priority = 200
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if not _eligible(morphs, i):
            return False
        morph = morphs[i]
        f_spec = _parse_noun_f(morph.a_con_type)
        if f_spec is not None:
            return f_spec[0] == F1        # 词典 F 数据：F1 = 付属語不干渉
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


class PartKifukuRule(Rule):
    """起伏式付属語・基本接続（F2/F3/F5/F6 或 NHK 1.2 表兜底）。

    - F2：前部平板 → 核进付属語（窓口 サケマ＼デ）；前部起伏 → 前部核保持
      ＋付属語核作为第 2 アクセント単位（ミ＼ソ・マ＼デ，NHK 1.2b）；
    - F3/F5/F6：按表12 公式；无 F 数据时按 NHK 表：前部平板→付属語核；
      否则前部核保持＋付属語第 2 単位。
    """

    rule_id = "R-PART-KIFUKU"
    name = "起伏式付属語・基本接続"
    source_ref = "NHK Ⅲ-1 1.2＋ 资料二 UniDic 表12 F2/F3/F5/F6"
    priority = 200
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if not _eligible(morphs, i):
            return False
        morph = morphs[i]
        f_spec = _parse_noun_f(morph.a_con_type)
        if f_spec is not None:
            return f_spec[0] in (F2, F3, F5, F6)
        return mora_util.strip_brackets(morph.pron) in KIFUKU_FALLBACK

    def apply(self, morphs: MorphList, i: int) -> None:
        front, morph = morphs[i - 1], morphs[i]
        n1 = front.mora_count
        f_spec = _parse_noun_f(morph.a_con_type)

        if f_spec is None:
            # NHK Ⅲ-1 1.2 兜底：付属語自身核位置来自手工表
            particle_accent = KIFUKU_FALLBACK[mora_util.strip_brackets(morph.pron)]
            if front.accent == 0:
                _place_total(front, morph, n1 + particle_accent)
                logic = (
                    f"「{morph.morph}」为起伏式付属語（NHK Ⅲ-1 1.2）→ 前部为平板型，"
                    f"付属語核生效：文節型 = N1 + M（{n1} + {particle_accent}）"
                )
            else:
                morph.accent = particle_accent
                morph.new_unit = True
                logic = (
                    f"「{morph.morph}」为起伏式付属語（NHK Ⅲ-1 1.2 b）→ 前部核保持，"
                    "付属語核作为第 2 アクセント単位（・分隔）"
                )
            self._report(morphs, i, morph, logic)
            return

        f_type, params = f_spec
        m1_param = params[0] if params else 1
        m2_param = params[1] if len(params) > 1 else m1_param

        if f_type == F2:
            if front.accent == 0:
                _place_total(front, morph, n1 + m1_param)
                logic = (
                    f"「{morph.morph}」结合型 {f_type}@{m1_param}（资料二 表12）→ "
                    f"前部为 0 型：文節型 = N1 + M（{n1} + {m1_param}），付属語内に核"
                )
            else:
                morph.accent = m1_param
                morph.new_unit = True
                logic = (
                    f"「{morph.morph}」结合型 {f_type}@{m1_param}（资料二 表12）→ "
                    "前部起伏：文節型 = M1（前部核保持），付属語核作为第 2 アクセント単位（NHK Ⅲ-1 1.2 b）"
                )
        elif f_type == F3:
            if front.accent == 0:
                morph.accent = 0
                logic = (
                    f"「{morph.morph}」结合型 F3@{m1_param}（资料二 表12）→ "
                    "前部为 0 型：文節型 = M1（=0，整体保持）"
                )
            else:
                _place_total(front, morph, n1 + m1_param)
                logic = (
                    f"「{morph.morph}」结合型 F3@{m1_param}（资料二 表12）→ "
                    f"前部起伏：文節型 = N1 + M（{n1} + {m1_param}）"
                )
        elif f_type == F4:
            _place_total(front, morph, n1 + m1_param)
            logic = (
                f"「{morph.morph}」结合型 F4@{m1_param}（付属語決定型）→ "
                f"文節型 = N1 + M（{n1} + {m1_param}）"
            )
        elif f_type == F5:
            front.accent = 0
            morph.accent = 0
            logic = f"「{morph.morph}」结合型 F5（资料二 表12）→ 文節型 = 0（平板）"
        else:  # F6@M, L
            total = n1 + (m1_param if front.accent == 0 else m2_param)
            _place_total(front, morph, total)
            logic = (
                f"「{morph.morph}」结合型 F6@{m1_param},{m2_param}（资料二 表12）→ "
                f"文節型 = N1 + {'M' if front.accent == 0 else 'L'}（{total}）"
            )
        self._report(morphs, i, morph, logic)

    def _report(self, morphs: MorphList, i: int, morph: MorphState, logic: str) -> None:
        morph.derived_by = self.rule_id
        result, target = _result_and_target(morphs, i, morph)
        morphs.add_report(self, target, logic, result)


class PartNoOdakaRule(Rule):
    """「の」接尾高型名词 → 整体平板化（NHK Ⅲ-1 2.1 例外）。

    除外：数詞（日時・回数等，``数詞`` 出现在品詞中）与顺序词/无声化致尾高的
    词表（``NO_ODAKA_EXCEPTION_WORDS``——NHK 列举为部分枚举，后续可扩充）。
    """

    rule_id = "R-PART-NO-ODAKA"
    name = "「の」接尾高型・平板化例外"
    source_ref = "NHK Ⅲ-1 2.1（尾高型＋の → 平板型）"
    priority = 210
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if not _eligible(morphs, i):
            return False
        morph = morphs[i]
        if mora_util.strip_brackets(morph.pron) != "ノ":
            return False
        prev = morphs[i - 1]
        if prev.accent != prev.mora_count or prev.mora_count <= 0:
            return False                      # 仅尾高型（核位于末拍之后）
        if "数詞" in prev.pos:
            return False                      # 数詞（日時・回数等）保留
        if prev.morph in NO_ODAKA_EXCEPTION_WORDS:
            return False                      # 顺序词/无声化致尾高等例外表
        return True

    def apply(self, morphs: MorphList, i: int) -> None:
        front, morph = morphs[i - 1], morphs[i]
        front.accent = 0
        morph.accent = 0
        front.derived_by = morph.derived_by = self.rule_id
        logic = (
            f"前部「{front.morph}」为尾高型，「の」接续时例外的に名词部分下がり目消失 → "
            "整体平板化（NHK Ⅲ-1 2.1）"
        )
        morphs.add_report(self, (i - 1, i), logic, morphs.render_range(i - 1, i))


class PartDecidingRule(Rule):
    """付属語決定型（F4 / NHK Ⅲ-1 2.2）：名词核消失、付属語核生效。

    （ぐらい サケグ＼ライ、らしい ミソラシ＼イ——NHK 2.2 所列第 1 形式。）
    """

    rule_id = "R-PART-DECIDING"
    name = "付属語決定型（ぐらい・らしい 等）"
    source_ref = "NHK Ⅲ-1 2.2（付属語決定型）＋ 资料二 UniDic 表12 F4"
    priority = 200
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if not _eligible(morphs, i):
            return False
        morph = morphs[i]
        f_spec = _parse_noun_f(morph.a_con_type)
        if f_spec is not None:
            return f_spec[0] == F4
        return mora_util.strip_brackets(morph.pron) in DECIDING_FALLBACK

    def apply(self, morphs: MorphList, i: int) -> None:
        front, morph = morphs[i - 1], morphs[i]
        n1 = front.mora_count
        f_spec = _parse_noun_f(morph.a_con_type)
        if f_spec is not None:
            particle_accent = (f_spec[1] or [1])[0]
            source = f"资料二 表12 F4@{particle_accent}"
        else:
            particle_accent = DECIDING_FALLBACK[mora_util.strip_brackets(morph.pron)]
            source = "NHK Ⅲ-1 2.2"
        _place_total(front, morph, n1 + particle_accent)
        front.derived_by = morph.derived_by = self.rule_id
        logic = (
            f"「{morph.morph}」为付属語決定型（{source}）→ 名词部分核消失，"
            f"文節型 = N1 + M（{n1} + {particle_accent}），付属語核生效"
        )
        morphs.add_report(self, (i - 1, i), logic, morphs.render_range(i - 1, i))
