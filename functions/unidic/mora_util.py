"""拍（モーラ）层面的确定性工具：分段、拍数、特殊拍判定、括号声调解码与 ＼/━ 渲染。

本模块为纯函数集合（无副作用、无随机），供阶段一（``stage1_analyzer``）、
阶段二（``stage2_rules``）与自检（``selfcheck``）共用。

括号声调解码（:func:`decode_bracket_accent`）依据
（tdmelodic ``nn/convert_dic.py`` 的 ``apply_all()`` 编码逻辑 + 本项目实测）：

- 组合词典中大音调词典（大词典推断产物）的词条「発音」字段用 ``[`` / ``]``
  标记音高移动：``]`` 附于某拍之后 = **该拍即声调核**（其后下降）；
  ``[`` = 上升标记（对核位置判定无影响）；
- 有 ``]`` → 核为 ``]`` 所在拍序号（1 起）；有 ``[`` 但无 ``]``（或两者皆无）
  → 平板型（0）；
- 实测对照（与辞书调型/用户确认一致）：``ジュ[ーミ]ンゼイ``→核3、
  ``ク]ーキ``→核1、``テ]レビ``→核1、``ア]イサツ``→核1、
  ``ガ[クセイ``→平板0、``パ[ソコン``→平板0、``ト[ーキョ]ーエキ``→核3、
  ``イ[ンターネ]ット``→核5；
- 因此「@ + []」的词携带完整声调信息，**不得**视作无调型（``is_unknown``）。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: 片假名 → 平假名 码位偏移（カタカナ U+30A1–U+30F6 ↔ ひらがな U+3041–U+3096）
_KATAKANA_TO_HIRAGANA_OFFSET = 0x60

#: 小写假名（拗音/小母音）：并入前一拍
SMALL_KANA: frozenset[str] = frozenset("ァィゥェォャュョヮヵヶ")

#: 特殊拍（不能作声调核）：拨音・促音・长音
SPECIAL_MORA: frozenset[str] = frozenset("ンッー")

#: 括号标记字符（発音字段中的推断声调标记，非拍）
BRACKET_MARKS = "[]"

#: 無声化倾向拍的首字符（近似集合，见《NHK Ⅲ 発音・アクセント全般》母音无声化节；
#: 核合法性规则中默认不启用，由 rules_config.json 的 nucleus_legality.avoid_devoiced 控制）
DEVOICED_HEAD: frozenset[str] = frozenset("キクシスチツヒフピプ")

#: 拍首字符 → 该拍元音（用于二重母音副音判定），ヤ行/ワ行按实际元音登记
_VOWEL_OF: dict[str, str] = {}


def _register_vowels(chars: str, vowels: str) -> None:
    for ch, vowel in zip(chars, vowels):
        _VOWEL_OF[ch] = vowel


_register_vowels("アイウエオ", "アイウエオ")
_register_vowels("カキクケコ", "アイウエオ")
_register_vowels("ガギグゲゴ", "アイウエオ")
_register_vowels("サシスセソ", "アイウエオ")
_register_vowels("ザジズゼゾ", "アイウエオ")
_register_vowels("タチツテト", "アイウエオ")
_register_vowels("ダヂヅデド", "アイウエオ")
_register_vowels("ナニヌネノ", "アイウエオ")
_register_vowels("ハヒフヘホ", "アイウエオ")
_register_vowels("バビブベボ", "アイウエオ")
_register_vowels("パピプペポ", "アイウエオ")
_register_vowels("マミムメモ", "アイウエオ")
_register_vowels("ヤユヨ", "アウオ")
_register_vowels("ラリルレロ", "アイウエオ")
_register_vowels("ワヲ", "アオ")
_register_vowels("ァィゥェォ", "アイウエオ")
_register_vowels("ャュョ", "アウオ")
_register_vowels("ヮ", "ア")

#: 二重母音副音判定中允许的前拍元音（ア/オ/ウ 段；不含 エ——「トケ＼イ」等
#: エイ 后的 イ 可为真正声调核，见 mora_util 说明与实测）
_DIPHTHONG_FIRST_VOWELS: frozenset[str] = frozenset("アオウ")


def is_katakana(ch: str) -> bool:
    """判断单字符是否为片假名（含 ヴ 等扩充区）。"""
    return 0x30A1 <= ord(ch) <= 0x30F6


def to_hiragana(text: str) -> str:
    """片假名 → 平假名（码位偏移法，确定性）。

    非片假名字符（含 ``ー``、``[]``、汉字、英数字）原样保留。
    """
    converted: list[str] = []
    for ch in text:
        if is_katakana(ch):
            converted.append(chr(ord(ch) - _KATAKANA_TO_HIRAGANA_OFFSET))
        else:
            converted.append(ch)
    return "".join(converted)


def strip_brackets(text: str) -> str:
    """去除発音字段中的 ``[`` / ``]`` 声调标记。"""
    return text.replace("[", "").replace("]", "")


def has_bracket_marks(text: str) -> bool:
    """判断文本是否携带 ``[`` / ``]`` 声调标记。"""
    return any(mark in text for mark in BRACKET_MARKS)


def split_moras(kana: str) -> list[str]:
    """将假名串切分为拍列表；小写假名并入前一拍，``[]`` 标记忽略。

    >>> split_moras("ジュ[ーミ]ンゼイ")
    ['ジュ', 'ー', 'ミ', 'ン', 'ゼ', 'イ']
    """
    moras: list[str] = []
    for ch in kana:
        if ch in BRACKET_MARKS:
            continue
        if ch in SMALL_KANA and moras:
            moras[-1] += ch
        else:
            moras.append(ch)
    return moras


def mora_spans(kana: str) -> list[tuple[int, int]]:
    """返回每个拍在字符串中的字符区间 ``[start, end)``。

    要求 ``kana`` 不含 ``[]`` 标记（调用方先经 :func:`strip_brackets`）。
    小写假名并入前一拍区间。
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(kana)
    while i < n:
        start = i
        i += 1
        while i < n and kana[i] in SMALL_KANA:
            i += 1
        spans.append((start, i))
    return spans


def mora_count(kana: str) -> int:
    """拍数（モーラ数）。空串返回 0。"""
    return len(mora_spans(strip_brackets(kana)))


def decode_bracket_accent(pron: str) -> tuple[str, int | None, bool]:
    """解码「発音」字段中的 ``[]`` 声调标记。

    返回三元组 ``(去标记发音, 声调核或 None, 是否含括号标记)``：

    - 无括号 → ``(pron, None, False)``；
    - 有括号：核 = 首个带 ``]`` 的拍序号（1 起，取首个——NHK「先示者为第1アクセント」）；
      无 ``]`` → 平板 ``0``；返回 ``(去标记发音, accent, True)``。
    """
    if not has_bracket_marks(pron):
        return pron, None, False

    moras: list[str] = []
    mora_marks: list[str] = []
    for ch in pron:
        if ch in BRACKET_MARKS:
            if mora_marks:
                mora_marks[-1] += ch
            continue
        if ch in SMALL_KANA and moras:
            moras[-1] += ch
        else:
            moras.append(ch)
            mora_marks.append("")

    clean = "".join(moras)
    accent: int = 0
    for i, marks in enumerate(mora_marks):
        if "]" in marks:
            accent = i + 1
            break
    return clean, accent, True


def is_special_mora(mora: str) -> bool:
    """判断拍是否为特殊拍（拨音 ン・促音 ッ・长音 ー）。"""
    return strip_brackets(mora) in SPECIAL_MORA


def _mora_last_char(mora: str) -> str:
    """取拍的末字符（用于元音判定；小写假名在末位）。"""
    clean = strip_brackets(mora)
    return clean[-1] if clean else ""


def mora_vowel(mora: str) -> str:
    """返回拍的元音（ア/イ/ウ/エ/オ），无法判定时返回空串。"""
    return _VOWEL_OF.get(_mora_last_char(mora), "")


def is_diphthong_glide(moras: list[str], idx: int) -> bool:
    """判断第 ``idx`` 拍（0 起）是否为二重母音副音（イ）。

    条件：该拍为「イ」，且前一拍元音为 ア/オ/ウ 段（アイ・オイ・ウイ 等）。
    此类拍不能作声调核（NHK Ⅰ複合名詞 1.2）但书＋Ⅲ全般 A）。
    """
    if idx <= 0 or idx >= len(moras):
        return False
    if strip_brackets(moras[idx]) != "イ":
        return False
    return _VOWEL_OF.get(_mora_last_char(moras[idx - 1]), "") in _DIPHTHONG_FIRST_VOWELS


def is_devoiced_mora(mora: str) -> bool:
    """判断拍是否属于「母音无声化倾向」拍（近似判定，见 ``DEVOICED_HEAD``）。

    仅为近似：真正的无声化需上下文（后接行・核位置・复合边界），
    因此核合法性规则中默认不使用该判定（rules_config.json 可开启）。
    """
    clean = strip_brackets(mora)
    return bool(clean) and clean[0] in DEVOICED_HEAD


def is_nucleus_eligible(moras: list[str], idx: int, avoid_devoiced: bool = False) -> bool:
    """判断第 ``idx`` 拍（0 起）能否承载声调核。

    不允许：特殊拍（ン・ッ・ー）、二重母音副音（イ）；
    ``avoid_devoiced=True`` 时另排除无声化倾向拍（默认关闭，见 NHK 现代倾向）。
    """
    if idx < 0 or idx >= len(moras):
        return False
    mora = moras[idx]
    if is_special_mora(mora):
        return False
    if is_diphthong_glide(moras, idx):
        return False
    if avoid_devoiced and is_devoiced_mora(mora):
        return False
    return True


def render_accent(kana: str, accent: int | None) -> str:
    """将「読み/発音 + 声调核」渲染为 ＼/━ 记法（NHK 记号，见 NHK Ⅰ 記号说明）。

    - ``accent`` 为 None 或 0 → ``kana + "━"``（平板型）；
    - ``1 <= accent < 拍数`` → 第 ``accent`` 拍之后插入 ``＼``（中高/頭高型）；
    - ``accent >= 拍数`` → 末尾插入 ``＼``（尾高型）。
    """
    clean = strip_brackets(kana)
    if accent is None or accent <= 0:
        return clean + "━"
    spans = mora_spans(clean)
    if not spans:
        return clean + "━"
    if accent >= len(spans):
        return clean + "＼"
    cut = spans[accent - 1][1]
    return clean[:cut] + "＼" + clean[cut:]


def accent_type_name(accent: int | None, mora_count_value: int) -> str:
    """声调型名称（东京式四分类）：平板型 / 頭高型 / 中高型 / 尾高型。"""
    if accent is None:
        return "未知型"
    if accent <= 0:
        return "平板型"
    if accent == 1:
        return "頭高型"
    if accent >= mora_count_value:
        return "尾高型"
    return "中高型"


def describe_accent(accent: int | None, mora_count_value: int) -> str:
    """生成「调型=N（xx型，核在第N拍）」类的中文说明（供规则报告 logic 字段）。"""
    if accent is None:
        return "调型未知"
    if accent <= 0:
        return "调型=0（平板型）"
    return f"调型={accent}（{accent_type_name(accent, mora_count_value)}，核在第{accent}拍）"
