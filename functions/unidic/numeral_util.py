"""数詞读法工具（数字读法 ＋ 促音规则；依据 NHK Ⅱ《数詞＋助数詞の発音とアクセント》）。

职责（纯函数，确定性）：

- 阿拉伯数字串 → 值（:func:`digits_to_int`）；
- 值 → 汉数词读法（:func:`compose_number_kana`）——含十/百/千/万的
  促音化与連濁（百：300 サンビャク／600 ロッピャク／800 ハッピャク；
  千：3000 サンゼン／8000 ハッセン；万：10000 イチマン 等）；
- 助数詞接続时的**促音化**（:func:`apply_sokuon`）——NHK Ⅱ 2. 2) 注 2：
  「イチ・ロク・ハチ・ジュー」后接**か行・さ行・た行・は行・ぱ行**语头时促音化
  （イチ→イッ、ロク→ロッ、ハチ→ハッ、ジュー→ジュッ）；个别词有慣用例外
  （如 10月＝ジューガツ、10時＝ジュージ），由 :data:`SOKUON_EXCEPTIONS` 处理；
- 合并数词（数字＋助数詞）的アクセント：取首位构成要素的基準アクセント
  （イチ2／ニ1／サン0／ヨン1／ゴ1／ロク2／ナナ2／ハチ2／キュー1／
  ジュー1／ヒャク1／セン1／マン1；用例对照：10選→ジュ＼ッセン＝アクセント1）。

注：数字读法的アクセント细则（21〜99 的 2 単位形等）依赖 NHK Ⅱ 助数詞一覧表，
仓库内暂无该表；本模块实现可确证的读法＋促音＋首位アクセント规则。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: 促音化触发语头（か行・さ行・た行・は行・ぱ行，含各浊音/半浊音变体）
SOKUON_INITIALS: frozenset[str] = frozenset(
    "カキクケコガギグゲゴ"
    "サシスセソザジズゼゾ"
    "タチツテトダヂヅデド"
    "ハヒフヘホバビブベボパピプペポ"
)

#: 促音化の慣用例外（助数詞表層形；NHK Ⅱ「語によって慣用が異なる」）
SOKUON_EXCEPTIONS: frozenset[str] = frozenset({"月", "時"})

#: 基準数詞读法（1〜9）
_DIGIT_KANA: tuple[str, ...] = (
    "", "イチ", "ニ", "サン", "ヨン", "ゴ", "ロク", "ナナ", "ハチ", "キュー",
)

#: 百位读法（連濁・促音化；NHK Ⅱ 2. 2)①）
_HYAKU: dict[int, str] = {
    1: "ヒャク", 2: "ニヒャク", 3: "サンビャク", 4: "ヨンヒャク", 5: "ゴヒャク",
    6: "ロッピャク", 7: "ナナヒャク", 8: "ハッピャク", 9: "キューヒャク",
}

#: 千位读法
_SEN: dict[int, str] = {
    1: "セン", 2: "ニセン", 3: "サンゼン", 4: "ヨンセン", 5: "ゴセン",
    6: "ロクセン", 7: "ナナセン", 8: "ハッセン", 9: "キューセン",
}


def digits_to_int(text: str) -> int | None:
    """阿拉伯数字串 → 整数；非数字返回 None。"""
    if text and text.isdigit():
        return int(text)
    return None


def compose_number_kana(value: int) -> tuple[str, int]:
    """整数 → ``(汉数词读法, 基準アクセント)``。

    支持 1〜99999999（万/千/百/十/一 的构成与促音・連濁）；
    アクセント取首位構成要素的基準値（如 10→(ジュー, 1)、15→(ジューゴ, 1)、
    300→(サンビャク, 0)、21→(ニジューイチ, 1)）。
    """
    if value <= 0 or value > 99_999_999:
        return "", 0

    parts: list[str] = []
    remainder = value
    for unit_value, unit_name in ((10_000, "マン"), (1_000, ""), (100, ""), (10, "")):
        if unit_value == 10_000:
            count, remainder = divmod(remainder, unit_value)
            if count:
                parts.append(compose_number_kana(count)[0] + unit_name)
            continue
        # 千/百/十 位
        divisor = unit_value
        digit, remainder = divmod(remainder, divisor)
        if digit == 0:
            continue
        if divisor == 1_000:
            parts.append(_SEN[digit])
        elif divisor == 100:
            parts.append(_HYAKU[digit])
        else:
            parts.append(("ジュー" if digit == 1 else _DIGIT_KANA[digit] + "ジュー"))
    if remainder:
        parts.append(_DIGIT_KANA[remainder])

    kana = "".join(parts)
    # アクセント（可确证范围）：10 系（ジュー 起始，10〜19）→ 頭高 1
    # （用例对照：10選→ジュ＼ッセンオ）；其余暂取平板 0，待 NHK Ⅱ 助数詞一覧表补全
    base = 1 if kana.startswith("ジュー") else 0
    return kana, base


def apply_sokuon(kana: str, classifier_surface: str, classifier_reading: str = "") -> str:
    """数词读法 ＋ 助数詞 的促音化（NHK Ⅱ 促音规则）。

    - 数词读法末尾为 イチ/ハチ → ッ；ロク → ッ；ジュー → ッ；
    - 仅当助数詞语头（读法首字）∈ :data:`SOKUON_INITIALS`；
    - 助数詞表層形 ∈ :data:`SOKUON_EXCEPTIONS` 时不促音（10月＝ジューガツ 等）。
    """
    if classifier_surface in SOKUON_EXCEPTIONS:
        return kana
    initial = (classifier_reading or classifier_surface)[:1]
    if initial not in SOKUON_INITIALS:
        return kana
    if kana.endswith(("イチ", "ハチ", "ロク")):
        return kana[:-1] + "ッ"
    if kana.endswith("ジュー"):
        return kana[:-1] + "ッ"
    return kana
