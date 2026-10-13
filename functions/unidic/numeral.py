"""数詞读法预处理（阿拉伯数字链 ＋ 助数詞 → 合成读音；NHK Ⅱ 数字读法＋促音规则）。

背景：MeCab 对阿拉伯数字逐位分词（如 ``10選`` → ``1``＋``0``＋``選``，逐位读
イチ＋ゼロ），与「十選＝ジュッセン」等实际读法不符。本模块在阶段二规则引擎前
做**确定性预处理**（与 ``resegment`` 同层）：

- 相邻的阿拉伯数字 token（``1``・``2``…）合并为一个数词；
- 其后的助数詞性 token（助数詞・接尾辞・助数詞可能）一并并入同一合成形态素；
- 合成读法由 :mod:`numeral_util` 按 NHK Ⅱ 的基准读法＋促音规则生成
  （10選→ジュッセン、11階→ジューイッカイ、600階→ロッピャクカイ 等）；
- 合成形态素的アクセント取数词首位构成要素的基準アクセント
  （用例对照：10選→ジュ＼ッセンオ）。

不适用：汉字数词（十・百・千…）——其读法与促音已由词典 token 承载，
既有规则（R-NUM-TWO-UNIT・复合词 C 规则等）继续处理，本模块只接管数字链。
"""

from __future__ import annotations

import logging

import mora_util
import numeral_util
from stage2_rules.base import MorphList, MorphState

logger = logging.getLogger(__name__)

#: 预处理报告（六字段契约）
_RULE_ID = "R-NUM-READING"
_RULE_NAME = "数詞读法（阿拉伯数字链＋助数詞・NHK Ⅱ）"
_SOURCE_REF = "NHK Ⅱ 2. 2)（基准数词读法・促音化：イチ/ロク/ハチ/ジュー＋かさたはぱ行）"


def _is_digit_token(morph: MorphState) -> bool:
    """阿拉伯数字 token（表層形为纯数字）。"""
    return morph.morph.isdigit() and morph.morph.isascii()


def _is_classifier(morph: MorphState) -> bool:
    """助数詞性 token（接尾辞・助数詞・助数詞可能）。"""
    return (
        morph.pos_head == "接尾辞"
        or "助数詞" in morph.pos
    )


def merge_numerals(ctx: MorphList) -> int:
    """合并阿拉伯数字链（及紧邻助数詞）为合成形态素；返回合并组数。"""
    new_morphs: list[MorphState] = []
    reports: list[dict] = []
    i = 0
    n = len(ctx)
    merged_groups = 0

    while i < n:
        morph = ctx[i]
        if not _is_digit_token(morph) or morph.claimed or morph.accent is not None:
            new_morphs.append(morph)
            i += 1
            continue

        # 收集连续数字 token
        j = i
        digits = ""
        while j < n and _is_digit_token(ctx[j]) and not ctx[j].claimed and ctx[j].accent is None:
            digits += ctx[j].morph
            j += 1
        value = numeral_util.digits_to_int(digits)
        if value is None:
            new_morphs.append(morph)
            i += 1
            continue

        # 紧邻的助数詞
        classifier = None
        if j < n and _is_classifier(ctx[j]) and not ctx[j].claimed and ctx[j].accent is None:
            classifier = ctx[j]

        kana, base_accent = numeral_util.compose_number_kana(value)
        if not kana:
            new_morphs.append(morph)
            i += 1
            continue
        if classifier is not None:
            classifier_kana = classifier.reading or classifier.pron
            kana = numeral_util.apply_sokuon(kana, classifier.morph, classifier_kana) + classifier_kana

        surface = digits + (classifier.morph if classifier is not None else "")
        group_start = len(new_morphs)
        merged = MorphState(
            idx=0,                                  # 稍后统一重编
            morph=surface,
            lemma=surface,
            reading=kana,
            pron=kana,
            pos="名詞-数詞",
            conj_type="",
            conj_form="",
            accent_raw=str(base_accent),
            mora_count=mora_util.mora_count(kana),
            is_unknown=False,
            accent_source="numeral",
            accent=base_accent,
            derived_by=_RULE_ID,
            claimed=True,                           # 合成形态素不再被其他规则改写
        )
        new_morphs.append(merged)
        merged_groups += 1

        consumed = digits
        logic = (
            f"阿拉伯数字串「{digits}」"
            + (f"＋助数詞「{classifier.morph}」" if classifier is not None else "")
            + f"→ NHK Ⅱ 读法「{kana}」（促音・連濁 按基准规则）"
            + f"；アクセント取首位构成要素基準值 {base_accent}"
        )
        reports.append({
            "rule_id": _RULE_ID,
            "name": _RULE_NAME,
            "source_ref": _SOURCE_REF,
            "target": [group_start, group_start],
            "logic": logic,
            "result": mora_util.render_accent(
                merged.pron, merged.accent if merged.accent is not None else 0
            ),
        })
        i = j + (1 if classifier is not None else 0)

    if merged_groups == 0:
        return 0

    ctx.clear()
    ctx.extend(new_morphs)
    for k, morph in enumerate(ctx):
        morph.idx = k
    ctx.report[:0] = reports
    logger.info("数詞读法：合并 %d 组阿拉伯数字链", merged_groups)
    return merged_groups
