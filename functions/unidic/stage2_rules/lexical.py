"""語彙用法規則（句5–7 帰納；用户确认）。

词典（tdmelodic 组合词典）给出的是**词条单読時の调型**，而实际句中用法会改变
读音与调型。本模块收录由参照例句（``selfcheck`` 句5/句6/句7）归纳、并逐条经用户确认的
**用法依赖型**规则——每条都只用确定性条件判断（前接品詞・活用形・後接助詞・文境界），
不含任何字符串整句匹配。

依据：

- **惯用句表**（``R-LEX-PHRASE``）：「しょうがない」＝「しようがない」の口语缩略形。
  该连语自身无核（0 調）→ 前部「しょう」を平板化する。付属語「ない」固有の
  下がり目は生きる（NHK Ⅲ-1 1.2a「名詞部分が平板式の場合 ⇒ 付属語の「下がり目」も
  生きる」）→ ショーガナ＼イッテ（しょう[0]＋が[平板式]＋ない[ナ＼イ]＋って[〜ッテ 平板式]）。
- **形式名詞「とき」**（``R-LEX-TOKI``）：用言の連体形に接する用法では语法化し 1 調
  （ト＼キモ）；実質名詞の「時（とき）」は 2 調。
- **方式用法「通り」**（``R-LEX-TOORI``）：動詞連体形に接する「〜通り」は表方式の
  语法用法で 1 調（ト＼ーリノ）；実質名詞の「通り」は 3 調。
- **「何」の読み分け**（``R-LEX-NANI``）：後接が格助詞・係助詞「が・を・に・も・と・は・へ」
  のとき ナニ（ナ＼ニガ）；「の・だ・です・助数詞」に接するとき ナン。
- **接続詞「でも」**（``R-LEX-DEMO``）：文頭・句点直後の「で（格助詞）＋も（係助詞）」は
  一語の接続詞「でも」［〜デ＼モ］（NHK Ⅲ-1 1.2 起伏式付属語表）。格助詞「で」は
  前部名詞を要求するため、前部を持たない文頭位置は接続詞と确定性判定できる。

规则清单：

- ``R-LEX-PHRASE``（慣用句表）、``R-LEX-TOKI``（形式名詞とき）、
  ``R-LEX-TOORI``（方式用法通り）、``R-LEX-NANI``（何→ナニ）、
  ``R-LEX-DEMO``（接続詞でも）。
"""

from __future__ import annotations

import logging

import mora_util
from stage2_rules.base import MorphList, MorphState, Rule, RulePhase

logger = logging.getLogger(__name__)

#: 惯用句表：表層形连语 → {该连语内的形態素表層形: 覆盖后的調型}
#: 命中时**只改写表内列出的形态素**，其余形态素照常走既有规则
#: （如 しょうがない 的 が/ない/って 仍由 R-PART-FLAT・R-LEX-DICT 推导）。
#: 可在 rules_config.json 的 ``lexical.phrase_overrides`` 覆盖/扩充。
PHRASE_OVERRIDES: dict[str, dict[str, int]] = {
    "しょうがない": {"しょう": 0},
}

#: 形式名詞「とき」的读音与语法化调型（実質名詞は词典值 2）
TOKI_PRON: str = "トキ"
TOKI_FORMAL_ACCENT: int = 1

#: 方式用法「通り」的读音与调型（実質名詞は词典值 3）
TOORI_PRON: str = "トーリ"
TOORI_MANNER_ACCENT: int = 1

#: 「何」の読み分け：ナニ を取る後接（格助詞・係助詞・副助詞の発音）
#:
#: 「か」＝ナニ（なにか）——副助詞の か のみ。「何か？」の文末終助詞 か は
#: ``_match`` 側で「終助詞」を除外済みのため混入しない。
#: 「に」「と」は**ナン**（なんにしますか／なんと言う）——用户指摘（句7 補正）。
#: 従って「の・だ・です・助数詞」に加え「に・と」も ナン 側。
NANI_FOLLOWERS: frozenset[str] = frozenset({"ガ", "オ", "モ", "ワ", "エ", "カ"})

#: 用言の連体形判定（活用形の表記に「連体形」を含む）
RENTAIKEI = "連体形"


def _is_rentaikei(morph: MorphState) -> bool:
    """形态素が連体形か（活用形标注に「連体形」を含む）。"""
    return RENTAIKEI in (morph.conj_form or "")


def _match_phrase(
    morphs: MorphList, i: int, table: dict[str, dict[str, int]]
) -> tuple[str, dict[str, int], int] | None:
    """从 i 起贪心拼接表層形，返回 ``(连语键, 覆盖表, 结束 idx)``；不匹配则 None。"""
    if not table:
        return None
    acc = ""
    for j in range(i, len(morphs)):
        acc += morphs[j].morph
        if acc in table:
            return acc, table[acc], j
        if not any(k.startswith(acc) for k in table):
            return None
    return None


class PhraseOverrideRule(Rule):
    """慣用句表：连语单位内指定形態素の調型を上書き（用户确认；句5）。

    连语自身为平板（0 調）时，只需把该连语内被词典赋予核的形态素置平即可——
    付属語固有の下がり目（ない → ナ＼イ）は NHK Ⅲ-1 1.2a により生き残る。
    """

    rule_id = "R-LEX-PHRASE"
    name = "慣用句表・连语调型覆盖"
    source_ref = "用户确认（句5）；NHK Ⅲ-1 1.2a（付属語の「下がり目」も生きる）"
    priority = 245
    phase = RulePhase.DERIVATION
    config_section = "lexical"

    def _table(self) -> dict[str, dict[str, int]]:
        raw = self.options.get("phrase_overrides")
        if isinstance(raw, dict) and raw:
            table: dict[str, dict[str, int]] = {}
            for phrase, overrides in raw.items():
                if isinstance(overrides, dict) and overrides:
                    try:
                        table[str(phrase)] = {
                            str(k): int(v) for k, v in overrides.items()
                        }
                    except (TypeError, ValueError):
                        continue
            if table:
                return table
        return PHRASE_OVERRIDES

    def match(self, morphs: MorphList, i: int) -> bool:
        morph = morphs[i]
        if morph.claimed or morph.accent is not None:
            return False
        hit = _match_phrase(morphs, i, self._table())
        if hit is None:
            return False
        _, overrides, end = hit
        span = range(i, end + 1)
        if not all(morphs[k].accent is None and not morphs[k].claimed for k in span):
            return False
        return any(morphs[k].morph in overrides for k in span)

    def apply(self, morphs: MorphList, i: int) -> None:
        phrase, overrides, end = _match_phrase(morphs, i, self._table())
        applied: list[MorphState] = []
        for k in range(i, end + 1):
            target = overrides.get(morphs[k].morph)
            if target is None:
                continue
            morphs[k].accent = int(target)
            morphs[k].derived_by = self.rule_id
            applied.append(morphs[k])
        names = "・".join(m.morph for m in applied)
        accent = overrides[applied[0].morph]
        logic = (
            f"「{phrase}」为慣用連語（調型 0）→ 表内形態素「{names}」を平板化"
            f"（调型={accent}）；付属語固有の下がり目は保持（NHK Ⅲ-1 1.2a）"
        )
        morphs.add_report(self, (i, end), logic, morphs.render_range(i, end))


class TokiFormalNounRule(Rule):
    """形式名詞「とき」：用言の連体形に接する用法 → 1 調（用户确认；句5）。

    実質名詞の「時（とき）」（〜の時、時を告げる 等）は词典値 2 調のまま；
    連体形に直接接する「〜するとき／〜したとき」は语法化した形式名詞で 1 調
    （思うときもあります → オモ＼ウ・ト＼キモ）。
    """

    rule_id = "R-LEX-TOKI"
    name = "形式名詞とき・用言連体形接续"
    source_ref = "用户确认（句5）：语法化とき=1 調／実質名詞=2 調"
    priority = 235
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if i <= 0:
            return False
        morph = morphs[i]
        if morph.claimed or morph.accent is not None:
            return False
        if morph.pos_head != "名詞":
            return False
        if mora_util.strip_brackets(morph.pron) != TOKI_PRON:
            return False
        prev = morphs[i - 1]
        return prev.pos_head in ("動詞", "形容詞") and _is_rentaikei(prev)

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        prev = morphs[i - 1]
        morph.accent = TOKI_FORMAL_ACCENT
        morph.derived_by = self.rule_id
        logic = (
            f"「{morph.morph}」接在用言「{prev.morph}」的連体形之后 → 语法化的形式名詞，"
            f"取 调型={TOKI_FORMAL_ACCENT}（実質名詞は 2 調）"
        )
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class TooriMannerRule(Rule):
    """方式用法「通り」：動詞の連体形に接する用法 → 1 調（用户确认；句6）。

    実質名詞の「通り」（道路・街路；単独 3 調）は词典値のまま；
    「〜する通り（に）」の表方式语法用法は 1 調（君が望む通りの私はどう？
    → ノゾム━・ト＼ーリノ）。
    """

    rule_id = "R-LEX-TOORI"
    name = "方式用法通り・動詞連体形接续"
    source_ref = "用户确认（句6）：方式语法「通り」=1 調／実質名詞=3 調"
    priority = 235
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if i <= 0:
            return False
        morph = morphs[i]
        if morph.claimed or morph.accent is not None:
            return False
        if morph.pos_head != "名詞":
            return False
        if mora_util.strip_brackets(morph.pron) != TOORI_PRON:
            return False
        prev = morphs[i - 1]
        return prev.pos_head == "動詞" and _is_rentaikei(prev)

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        prev = morphs[i - 1]
        morph.accent = TOORI_MANNER_ACCENT
        morph.derived_by = self.rule_id
        logic = (
            f"「{morph.morph}」接在动词「{prev.morph}」的連体形之后 → 表方式的语法用法，"
            f"取 调型={TOORI_MANNER_ACCENT}（実質名詞は 3 調）"
        )
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class NaniReadingRule(Rule):
    """「何」の読み分け：後接の助詞により ナニ／ナン（用户确认；句7）。

    「何」は後接語によって読みが交替する（ナニ／ナン は**同じ 2 拍**なので、
    拍数・調型は不変で読みだけが変わる）：

    - 後接が「が・を・も・は・へ・か（副助詞）」→ **ナニ**
      （ナ＼ニガ・なにか）；
    - 後接が「に・と・の・だ・です・助数詞」等 → **ナン**（词典既定値のまま）——
      「に」「と」は ナン（なんにしますか／なんと言う）であり、用户指摘により
      ナニ 側から除外した（文末終助詞の か も ``pos`` 判定で除外）。
    """

    rule_id = "R-LEX-NANI"
    name = "「何」の読み分け（ナニ／ナン）"
    source_ref = "用户确认（句7）＋現代日本語の慣用（何＋が/を/に は ナニ）"
    priority = 235
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if i + 1 >= len(morphs):
            return False
        morph = morphs[i]
        if morph.claimed or morph.accent is not None:
            return False
        if morph.morph != "何":
            return False
        nxt = morphs[i + 1]
        if nxt.pos_head != "助詞" or "終助詞" in nxt.pos:
            return False
        return mora_util.strip_brackets(nxt.pron) in NANI_FOLLOWERS

    def apply(self, morphs: MorphList, i: int) -> None:
        morph = morphs[i]
        nxt = morphs[i + 1]
        before = morph.pron
        morph.pron = "ナニ"
        morph.reading = "ナニ"
        morph.accent = 1
        morph.derived_by = self.rule_id
        logic = (
            f"「何」後接「{nxt.morph}」→ 読みは ナニ（{before} ではない）；"
            f"拍数不変（2 拍）のため调型も 1 のまま"
        )
        morphs.add_report(self, (i, i), logic, morphs.render_range(i, i))


class ConjunctionDemoRule(Rule):
    """接続詞「でも」：文頭・句点直後の「で＋も」を一語扱い（用户确认；句5）。

    格助詞「で」は前部名詞を要求する。文頭（または句点の直後）に現れる「で」には
    その前部が存在しないため、〔で＋も〕は一語の接続詞「でも」［〜デ＼モ］と
    确定性判定できる（NHK Ⅲ-1 1.2 起伏式付属語表の でも）。

    用例对照：〜あります。でも自分は → アリマ＼ス・デ＼モ（句点＝文境界により
    第 2 単位が開く。文境界判定は ``MorphState.is_sentence_end``）。
    """

    rule_id = "R-LEX-DEMO"
    name = "接続詞でも・文頭/句点直後の で＋も"
    source_ref = "用户确认（句5）；NHK Ⅲ-1 1.2（でも［〜デ＼モ］）"
    priority = 215
    phase = RulePhase.DERIVATION

    def match(self, morphs: MorphList, i: int) -> bool:
        if i + 1 >= len(morphs):
            return False
        morph, nxt = morphs[i], morphs[i + 1]
        if morph.claimed or nxt.claimed:
            return False
        if morph.accent is not None or nxt.accent is not None:
            return False
        if morph.morph != "で" or "格助詞" not in morph.pos:
            return False
        if nxt.morph != "も" or "係助詞" not in nxt.pos:
            return False
        # 前部が存在しない位置（文頭、または文末記号の直後）に限る
        if i == 0:
            return True
        return morphs[i - 1].is_sentence_end

    def apply(self, morphs: MorphList, i: int) -> None:
        morph, nxt = morphs[i], morphs[i + 1]
        morph.accent = 1                      # デ＼モ
        nxt.accent = 0
        nxt.claimed = True
        morph.derived_by = nxt.derived_by = self.rule_id
        where = "文頭" if i == 0 else "句点直後"
        logic = (
            f"{where}の「で」には格助詞の前部が存在しない → "
            "〔で＋も〕を一語の接続詞「でも」と判定（NHK Ⅲ-1 1.2 〜デ＼モ）"
        )
        morphs.add_report(self, (i, i + 1), logic, morphs.render_range(i, i + 1))
