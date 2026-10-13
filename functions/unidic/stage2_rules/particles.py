"""付属語接続规则（资料二 UniDic 表12 F 系列 ＋ 资料三 NHK Ⅲ-1/Ⅲ-2）。

依据（四合一，已逐项核对）：

- **资料三 NHK Ⅲ-1 总原则『付属語不干渉』**（名词）/ **NHK Ⅲ-2**（动词）：
  绝大多数付属語不影响前接词部分的声调；
- **资料二 UniDic 手册 6.3–6.7 表12「アクセント結合型分類（助詞・助動詞）」**
  ——付属語的词典原生字段 ``a_con_type`` 携带**按前部品詞区分的 F 系列规格**
  （实测：を=``名詞%F1``、まで=``名詞%F2@1``、ぐらい=``名詞%F4@1``、
  が=``動詞%F2@0,名詞%F1``、ます=``動詞%F4@1``、た=``動詞%F2@1``），
  按前部品詞选中条目后按公式计算文節アクセント型::

      F1      → M1（前部要素のアクセント型保持＝付属語不干渉）
      F2@M    → 前部 0 型: N1 + M；それ以外: M1
                （M≥1 时付属語核作为第 2 単位存活＝NHK Ⅲ-2 1.2a / Ⅲ-1 1.2b；
                 M=0 时无第 2 下降＝直接連続＝NHK Ⅲ-2 1.1b「そのまま連なる」）
      F3@M    → 前部 0 型: M1；それ以外: N1 + M
      F4@M    → N1 + M（付属語決定型；NHK Ⅲ-2 4.1 ます・Ⅲ-1 2.2 ぐらい 的原生实现）
      F5      → 0
      F6@M, L → 前部 0 型: N1 + M；それ以外: N1 + L
      N1: 前部要素のモーラ数, M1: 前部要素のアクセント型, M/M,L: 付属語の核位置参数

- **资料三 NHK Ⅲ-1 例外 2.1**：「の」接尾高型名词 → 名词核消失、整体平板化
  （コメ＼＋ノ → コメノ━；数詞（日時・回数等）与无声化致尾高的词除外）——
  由 ``R-PART-NO-ODAKA``（优先级高于 F1 默认）实现；
- **资料三 NHK Ⅲ-2 た形・て形家族**（た・だ・て・で・たら・だら・たり・だり，
  1.1a/1.2a ＋ 活用形一覧表）：平板动词保持；五段（起伏）核保持；
  一段・カ変・サ変核前移 1 拍（食べた タ＼ベタ、食べたら タ＼ベタラ、来た キ＼タ；
  供する キョ＼ーシ 由核合法性级联处理）——由 ``R-PART-TA-TE`` 实现
  （词典 F2@1 数据与 NHK 活用形表冲突时，以资料三 NHK 表为准）；
- 付属語无 F 数据时（如 ほど=空、`[]` 解码词、`に` 无動詞%条目）回落手工表
  （平板式表 / 起伏式表 / 决定型表），逻辑与 F 系列同构。

规则清单：

- ``R-PART-FLAT``：平板式付属語・基本接続（F1 / NHK 表兜底；验收样例 1 依据）；
- ``R-PART-KIFUKU``：起伏式付属語（F2/F3/F5/F6 / NHK 表兜底；前部核与付属語核并存）；
- ``R-PART-TA-TE``：た形・て形接続（NHK Ⅲ-2；一段/カ変/サ変核前移）；
- ``R-PART-NO-ODAKA``：「の」接尾高型平板化（NHK Ⅲ-1 2.1 例外）；
- ``R-PART-DECIDING``：付属語決定型（F4 / NHK Ⅲ-2 4.1・Ⅲ-1 2.2）。

范围说明：前部支持**名词/代名词（NHK Ⅲ-1）、动词（NHK Ⅲ-2）与形容词（NHK Ⅲ-3）**；
形状詞（ナ形容词，如 きれいです）尚未纳入（数据仅含 名詞%/動詞%/形容詞% 三类规格）。
NHK Ⅲ-3 的活用形接续由同一 F 机制精确复现（实测：甘かっ+た 的 ``形容詞%F4@-2``
→ アマ＼カッタ、冷たかっ→ツメタ＼カッタ、甘く+て 的 ``F2@-1`` → アマ＼クテ，
均与 NHK 一览表一致）；ない/なる（非自立）按 NHK Ⅲ-3 1.2 走 KIFUKU 兜底表。
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

#: 起伏式付属語（NHK Ⅲ-1 1.2 / Ⅲ-3 1.2；值=付属語自身核位置）——无 F 数据时的兜底
KIFUKU_FALLBACK: dict[str, int] = {
    "カモ": 1, "コソ": 1, "サエ": 1, "シカ": 1, "スラ": 1,
    "ダッタ": 1, "ダッテ": 1, "ダト": 1, "ダロー": 2,
    "デシタ": 1, "デショー": 2, "デス": 1, "デワ": 1, "デモ": 1,
    "トカ": 1, "トワ": 1, "トモ": 1,
    "ナド": 1, "ナノダ": 1, "ナノデ": 1, "ナノニ": 1,
    "ナラ": 1, "ナラバ": 1, "ナンカ": 1, "ナンテ": 1,
    "ニワ": 1, "ニモ": 1, "ノミ": 1, "バカリ": 1, "エワ": 1, "エモ": 1,
    "マデ": 1, "ミタイダ": 1, "ヨリ": 1,
    # NHK Ⅲ-3 1.2（形容词接续）：ない（アマクナ＼イ）・なる（アマクナ＼ル）
    "ナイ": 1, "ナル": 1,
}

#: 付属語決定型（NHK Ⅲ-1 2.2；值=付属語自身核位置）——无 F 数据时的兜底
DECIDING_FALLBACK: dict[str, int] = {
    "グライ": 1, "クライ": 1, "ラシイ": 2,
}

#: た形・て形家族（NHK Ⅲ-2 1.1a/1.2a；按発音匹配）
TA_TE_SHORT: frozenset[str] = frozenset({"タ", "ダ", "テ", "デ"})
TA_TE_TARA: frozenset[str] = frozenset({"タラ", "ダラ", "タリ", "ダリ"})

#: 「の」平板化例外的词表（NHK Ⅲ-1 2.1：顺序词等；数詞另按 pos 判定）
NO_ODAKA_EXCEPTION_WORDS: frozenset[str] = frozenset({
    "次", "よそ", "基地", "地下", "ヒ素", "一日",
})


#: 前部品詞 → F 规格前缀（表12 按品詞区分；未列出的品詞不适用 F 规则）
_FRONT_POS_PREFIX: dict[str, str] = {
    "名詞": "名詞%",
    "代名詞": "名詞%",   # 代名詞 使用 名詞% 规格
    "動詞": "動詞%",
    "形容詞": "形容詞%",  # i-形容词（NHK Ⅲ-3）
    "形状詞": "名詞%",   # ナ形容词（大変+でし→タイヘンデ＼シ 等，用例对照）
    "助動詞": "動詞%",   # 付属語链尾（〜ていた+けど→イッテイタ＼ケド 等，用例对照）
}

#: F 系列规则适用的前部品詞（NHK Ⅲ-1/Ⅲ-2/Ⅲ-3 ＋ 形状詞・付属語链尾的用例对照）
F_RULE_FRONT_POS: frozenset[str] = frozenset(
    {"名詞", "代名詞", "動詞", "形容詞", "形状詞", "助動詞"}
)

#: F2@M（M≥1）不拆第 2 単位、与 M1 合并保持的付属語（です/でし：用例对照
#: 港町です→ミナト＼マチデス、大変でした→タイヘンデ＼シタ）
_MERGED_AUX: frozenset[str] = frozenset({"デス", "デシ"})

#: 名词性前部（R-PART-NO-ODAKA 等 NHK Ⅲ-1 专属规则）
NOMINAL_FRONT_POS: frozenset[str] = frozenset({"名詞", "代名詞"})


def _parse_f_spec(a_con_type: str, front_pos_head: str) -> tuple[str, list[int]] | None:
    """按**前部品詞**从 ``a_con_type`` 解析 F 规格（表12 按品詞区分条目）。

    例：``"動詞%F2@0,名詞%F1"`` 在前部为动词时返回 ``("F2", [0])``、
    为名词时返回 ``("F1", [])``。前部品詞无对应前缀条目或格式异常时返回 None
    （调用方回落手工表或跳过，即「付属語不干渉」的保持行为）。
    ``F6@M, L`` 的双参数以续接数字项合并（``F6@1`` + ``2`` → ``F6@1,2``）。
    """
    prefix = _FRONT_POS_PREFIX.get(front_pos_head)
    if prefix is None:
        return None
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
        if item.startswith(prefix):
            spec = item[len(prefix):]
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


def _is_auxiliary_like(morph: MorphState) -> bool:
    """付属語或须按付属語处理的自立語形判定。

    - 助詞・助動詞 → True；
    - 非自立の ない/なる（NHK Ⅲ-3 1.2 的 形容词接续对象，pos 为
      形容詞/動詞-非自立可能）→ 仅当其发音在 ``KIFUKU_FALLBACK`` 表内时 True
      （避免把 ある/いる 等其它非自立词卷入 F 规则）。
    """
    if morph.pos_head in ("助詞", "助動詞"):
        return True
    if "非自立" in morph.pos and morph.pos_head in ("形容詞", "動詞"):
        return mora_util.strip_brackets(morph.pron) in KIFUKU_FALLBACK
    return False


def _eligible(morphs: MorphList, i: int, front_pos_heads: frozenset[str]) -> bool:
    """付属語规则的公共前置条件：前部（指定品詞）已推导、本形态素未推导未占用。

    文末终助词（な・ね・よ・ぞ・ぜ・わ等）不在 NHK 接续表内（Ⅲ-1 明示排除
    文末终助词）——不参与 F 规则推导，走兜底平板（用例对照：〜ケタナッテ）。
    """
    if i <= 0:
        return False
    morph = morphs[i]
    if morph.accent is not None or morph.claimed:
        return False
    if "終助詞" in morph.pos:
        return False
    if not _is_auxiliary_like(morph):
        return False
    prev = morphs[i - 1]
    if prev.accent is None or prev.pos_head not in front_pos_heads:
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
        if not _eligible(morphs, i, F_RULE_FRONT_POS):
            return False
        morph = morphs[i]
        f_spec = _parse_f_spec(morph.a_con_type, morphs[i - 1].pos_head)
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
        if not _eligible(morphs, i, F_RULE_FRONT_POS):
            return False
        morph = morphs[i]
        f_spec = _parse_f_spec(morph.a_con_type, morphs[i - 1].pos_head)
        if f_spec is not None:
            return f_spec[0] in (F2, F3, F5, F6)
        return mora_util.strip_brackets(morph.pron) in KIFUKU_FALLBACK

    def apply(self, morphs: MorphList, i: int) -> None:
        front, morph = morphs[i - 1], morphs[i]
        n1 = front.mora_count
        f_spec = _parse_f_spec(morph.a_con_type, front.pos_head)

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
            # 助動詞链尾且 M≥1（如 〜れ+た 的 た）：合并保持不插入
            # （用例对照：エガカ＼レタ）；M=0 型（けど等下がり目插入型）不受此限
            # （用例对照：イッテイタ＼ケド）
            if front.accent == 0 and not (front.pos_head == "助動詞" and m1_param >= 1):
                _place_total(front, morph, n1 + m1_param)
                logic = (
                    f"「{morph.morph}」结合型 {f_type}@{m1_param}（资料二 表12）→ "
                    f"前部为 0 型：文節型 = N1 + M（{n1} + {m1_param}），付属語内に核"
                )
            elif (
                m1_param >= 1
                and front.pos_head != "助動詞"                       # 付属語链尾不拆単位
                and mora_util.strip_brackets(morph.pron) not in _MERGED_AUX
            ):
                morph.accent = m1_param
                morph.new_unit = True
                logic = (
                    f"「{morph.morph}」结合型 {f_type}@{m1_param}（资料二 表12）→ "
                    "前部起伏：文節型 = M1（前部核保持），付属語核作为第 2 アクセント単位"
                    "（NHK Ⅲ-1 1.2 b／Ⅲ-2 1.2a）"
                )
            else:
                # M=0（直接連続）／です・でし（合并保持）／付属語链尾：前部核保持、付属語置平
                morph.accent = 0
                logic = (
                    f"「{morph.morph}」结合型 {f_type}@{m1_param}（资料二 表12）→ "
                    "前部核保持、付属語直接連続（M=0／です・でし／付属語链尾）"
                )
        elif f_type == F3:
            if front.accent == 0:
                morph.accent = 0
                logic = (
                    f"「{morph.morph}」结合型 F3@{m1_param}（资料二 表12）→ "
                    "前部为 0 型：文節型 = M1（=0，整体保持）"
                )
            elif front.accent == n1 and n1 > 0:
                # 前部为尾高型：核在接合部、付属語不干渉（如 描か＼+れ 保持 → エガカ＼レタ）
                morph.accent = 0
                logic = (
                    f"「{morph.morph}」结合型 F3@{m1_param}（资料二 表12）→ "
                    "前部为尾高型：核保持在接合部，付属語置平（不干渉）"
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
    """「の」接续的平板化例外（NHK Ⅲ-1 2.1）。

    - **尾高型** ＋ の → 整体平板化（コメ＼＋ノ → コメノ━）；
    - **中高型且末拍为特殊拍（二重母音副音含む）** ＋ の → 平板化倾向
      （キノ＼ー＋ノ → キノーノ━、オトト＼イ＋ノ → オトトイノ━、
      ニホ＼ン＋ノ → ニホンノ━——NHK 2.1 所列倾向，本引擎取该首列形）。

    除外：数詞（日時・回数等，``数詞`` 出现在品詞中）与顺序词/无声化致尾高的
    词表（``NO_ODAKA_EXCEPTION_WORDS``——NHK 列举为部分枚举，后续可扩充）。
    """

    rule_id = "R-PART-NO-ODAKA"
    name = "「の」接尾高型・平板化例外"
    source_ref = "NHK Ⅲ-1 2.1（尾高型/中高特定末拍＋の → 平板型）"
    priority = 210
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if not _eligible(morphs, i, NOMINAL_FRONT_POS):
            return False
        morph = morphs[i]
        if mora_util.strip_brackets(morph.pron) != "ノ":
            return False
        prev = morphs[i - 1]
        if prev.accent is None or prev.mora_count <= 0:
            return False
        moras = mora_util.split_moras(prev.pron)
        if not moras:
            return False

        is_odaka = prev.accent == prev.mora_count                       # 尾高型
        last_index = len(moras) - 1
        last_specialish = (
            mora_util.is_special_mora(moras[last_index])
            or mora_util.is_diphthong_glide(moras, last_index)          # 二重母音副音
        )
        # 中高型（核が2拍目以降）のみが对象。頭高型（核=1拍目）は の 接续で保持
        # （用例对照：今回→コ＼ンカイノ、廈門→ア＼モイノ、ミソ→ミ＼ソノ）
        is_mid_high_special = (1 < prev.accent < prev.mora_count) and last_specialish
        if not (is_odaka or is_mid_high_special):
            return False
        if "数詞" in prev.pos:
            return False                      # 数詞（日時・回数等）保留
        if prev.morph in NO_ODAKA_EXCEPTION_WORDS:
            return False                      # 顺序词/无声化致尾高等例外表
        return True

    def apply(self, morphs: MorphList, i: int) -> None:
        front, morph = morphs[i - 1], morphs[i]
        kind = "尾高型" if front.accent == front.mora_count else "中高型（末拍为特殊拍/二重母音副音）"
        front.accent = 0
        morph.accent = 0
        front.derived_by = morph.derived_by = self.rule_id
        logic = (
            f"前部「{front.morph}」为{kind}，「の」接续时名词部分下がり目消失 → "
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
        if not _eligible(morphs, i, F_RULE_FRONT_POS):
            return False
        morph = morphs[i]
        f_spec = _parse_f_spec(morph.a_con_type, morphs[i - 1].pos_head)
        if f_spec is not None:
            return f_spec[0] == F4
        return mora_util.strip_brackets(morph.pron) in DECIDING_FALLBACK

    def apply(self, morphs: MorphList, i: int) -> None:
        front, morph = morphs[i - 1], morphs[i]
        n1 = front.mora_count
        f_spec = _parse_f_spec(morph.a_con_type, front.pos_head)
        if f_spec is not None:
            particle_accent = (f_spec[1] or [1])[0]
            source = f"资料二 表12 F4@{particle_accent}"
        else:
            particle_accent = DECIDING_FALLBACK[mora_util.strip_brackets(morph.pron)]
            source = "NHK Ⅲ-1 2.2"
        # 付属語決定型：按文節型 = N1 + M 配置核，仅清零**紧邻前部**（如 います 的 い）；
        # 更早的动词核保留（用例对照：飲んでいます → ノ＼ンデイマ＼ス，双下降）
        _place_total(front, morph, n1 + particle_accent)
        front.derived_by = morph.derived_by = self.rule_id
        logic = (
            f"「{morph.morph}」为付属語決定型（{source}）→ 名词部分核消失，"
            f"文節型 = N1 + M（{n1} + {particle_accent}），付属語核生效"
        )
        morphs.add_report(self, (i - 1, i), logic, morphs.render_range(i - 1, i))


class PartTaTeRule(Rule):
    """た形・て形（含 たら・たり 系）接续（NHK Ⅲ-2 1.1a/1.2a ＋ 活用形一覧表）。

    规则（前部=動詞）：

    - **平板动词**：た/だ/て/で → 直接連続保持平板（モッタ━）；
      たら/だら/たり/だり → 付属語内に下がり目を挿入（モッタ＼ラ）；
    - **五段（起伏）动词**：动词核保持、付属語直接連続（ノ＼ンダ，ノ＼ンダラ）；
    - **一段・カ変・サ変动词**：核**前移 1 拍**（食べた タ＼ベタ、食べて タ＼ベテ、
      食べたら タ＼ベタラ、来た キ＼タ；供する キョ＼ーシ 的音位由 R-NUCLEUS-SPECIAL
      级联处理）——NHK 活用形一覧表「中止法」列（食べる→``タ＼ベ``）与用户确认。

    冲突说明：词典 ``た`` 的 F 数据（``動詞%F2@1``）对平板动词/一段动词给出与 NHK
    活用形表不同的结果；本规则（资料三 NHK）优先级 205 高于通用 F 规则，按 NHK 表实现。
    """

    rule_id = "R-PART-TA-TE"
    name = "た形・て形接続（一段・カ変・サ変 核前移）"
    source_ref = "NHK Ⅲ-2 1.1a/1.2a（活用形一覧表 食べる→タ＼ベ）"
    priority = 205
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if i <= 0:
            return False
        morph = morphs[i]
        if morph.accent is not None or morph.claimed:
            return False
        if morph.pos_head not in ("助詞", "助動詞"):
            return False
        pron = mora_util.strip_brackets(morph.pron)
        if pron not in TA_TE_SHORT and pron not in TA_TE_TARA:
            return False
        front = morphs[i - 1]
        return front.accent is not None and front.pos_head == "動詞"

    def apply(self, morphs: MorphList, i: int) -> None:
        front, morph = morphs[i - 1], morphs[i]
        pron = mora_util.strip_brackets(morph.pron)
        base = front.accent or 0
        shifted_class = ("一段" in front.conj_type) or ("変格" in front.conj_type)

        if base == 0:
            if pron in TA_TE_TARA:
                _place_total(front, morph, front.mora_count + 1)
                logic = (
                    "前部为平板动词 → たら/たり 接続时于付属語内插入下降核"
                    "（モッタ＼ラ；NHK Ⅲ-2 1.2a）"
                )
            else:
                morph.accent = 0
                logic = "前部为平板动词 → た/て 直接連続，保持平板（モッタ━；NHK Ⅲ-2 1.1a）"
        elif shifted_class:
            before = base
            front.accent = max(1, base - 1)
            morph.accent = 0
            logic = (
                f"前部为一段/カ変/サ変活用（{front.conj_type or '活用型未知'}）→ "
                f"核前移1拍（调型 {before}→{front.accent}；NHK Ⅲ-2 活用形一覧表）"
            )
        else:
            morph.accent = 0
            logic = (
                "前部为五段（起伏）动词 → 动词核保持，付属語直接連続"
                "（ノ＼ンダ；NHK Ⅲ-2 1.1a）"
            )
        front.derived_by = morph.derived_by = self.rule_id
        morphs.add_report(self, (i - 1, i), logic, morphs.render_range(i - 1, i))
