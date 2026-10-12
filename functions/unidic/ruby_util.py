"""ruby_pairs（表記-かな 对齐）工具（总 AGENTS.md §7.4）。

契约：``ruby_pairs`` 为 ``[[表記, かな], ...]``；首元素为 ``null`` 表示该读音片段
没有对应的表记字符（如纯假名词「を」→ ``[[null, "を"]]``）。
かな一律为**平假名**（由「読み」字段转换；部分词条読み与発音不同，
如 を：読み ヲ / 発音 オ，ruby 取読み）。

对齐算法（确定性贪心，粒度=形态素）：

- 无读音 → ``[[null, 表層形]]``；纯假名（无汉字）→ ``[[null, 読み平假名]]``；
- 含汉字：从左到右扫描——假名字符与かな逐字配对（送假名，如 盛る→
  ``[["盛","も"],["る","る"]]``）；连续汉字串按「剩余かな字符数 − 其后非汉字表记
  字符数」消费かな；消费数小于 1 或大于 3（熟字訓・长汉字串・送假名小写假名等
  歧义情形）→ 整词作单一配对兜底（如 今日→``[["今日","きょう"]]``、
  住民税→``[["住民税","じゅうみんぜい"]]``）。
"""

from __future__ import annotations

import logging
import re

import mora_util

logger = logging.getLogger(__name__)

#: 汉字判定（CJK 统一表意文字 + 扩展 A + 兼容区 + 々〆）
_KANJI_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿々〆]")


def _is_kanji(ch: str) -> bool:
    return bool(_KANJI_RE.match(ch))


def has_kanji(text: str) -> bool:
    """判断文本是否含汉字（含 々〆）。"""
    return any(_is_kanji(ch) for ch in text)


def align_ruby_pairs(morph: str, reading: str) -> list[list[str | None]]:
    """对齐表層形与読み，返回 ``ruby_pairs``（详见模块 docstring）。"""
    hira = mora_util.to_hiragana(reading) if reading else ""
    if not hira:
        return [[None, morph]]
    if not has_kanji(morph):
        return [[None, hira]]

    pairs: list[list[str | None]] = []
    i = 0
    j = 0
    n = len(morph)
    while i < n:
        if _is_kanji(morph[i]):
            start = i
            while i < n and _is_kanji(morph[i]):
                i += 1
            kanji_run = morph[start:i]
            trailing_kana = sum(1 for c in morph[i:] if not _is_kanji(c))
            take = len(hira) - j - trailing_kana
            if take < 1 or take > 3:
                return [[morph, hira]]
            pairs.append([kanji_run, hira[j:j + take]])
            j += take
        else:
            if j >= len(hira):
                return [[morph, hira]]
            pairs.append([morph[i], hira[j]])
            j += 1
            i += 1
    if j != len(hira):
        return [[morph, hira]]
    return pairs
