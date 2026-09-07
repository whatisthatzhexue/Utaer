/**
 * 平假名 / 片假名 -> 罗马字（Hepburn 风格）纯前端实现。
 * 注意：只转换“假名”字符，汉字保持原样输出（汉字读音建议用后端 ruby_pairs 的 reading 再转换）。
 */

const HIRA: Record<string, string> = {
  あ: 'a', い: 'i', う: 'u', え: 'e', お: 'o',
  か: 'ka', き: 'ki', く: 'ku', け: 'ke', こ: 'ko',
  が: 'ga', ぎ: 'gi', ぐ: 'gu', げ: 'ge', ご: 'go',
  さ: 'sa', し: 'shi', す: 'su', せ: 'se', そ: 'so',
  ざ: 'za', じ: 'ji', ず: 'zu', ぜ: 'ze', ぞ: 'zo',
  た: 'ta', ち: 'chi', つ: 'tsu', て: 'te', と: 'to',
  だ: 'da', ぢ: 'ji', づ: 'zu', で: 'de', ど: 'do',
  な: 'na', に: 'ni', ぬ: 'nu', ね: 'ne', の: 'no',
  は: 'ha', ひ: 'hi', ふ: 'fu', へ: 'he', ほ: 'ho',
  ば: 'ba', び: 'bi', ぶ: 'bu', べ: 'be', ぼ: 'bo',
  ぱ: 'pa', ぴ: 'pi', ぷ: 'pu', ぺ: 'pe', ぽ: 'po',
  ま: 'ma', み: 'mi', む: 'mu', め: 'me', も: 'mo',
  や: 'ya', ゆ: 'yu', よ: 'yo',
  ら: 'ra', り: 'ri', る: 'ru', れ: 're', ろ: 'ro',
  わ: 'wa', を: 'o', ん: 'n',
  きゃ: 'kya', きゅ: 'kyu', きょ: 'kyo',
  ぎゃ: 'gya', ぎゅ: 'gyu', ぎょ: 'gyo',
  しゃ: 'sha', しゅ: 'shu', しょ: 'sho',
  じゃ: 'ja', じゅ: 'ju', じょ: 'jo',
  ちゃ: 'cha', ちゅ: 'chu', ちょ: 'cho',
  ぢゃ: 'ja', ぢゅ: 'ju', ぢょ: 'jo',
  にゃ: 'nya', にゅ: 'nyu', にょ: 'nyo',
  ひゃ: 'hya', ひゅ: 'hyu', ひょ: 'hyo',
  びゃ: 'bya', びゅ: 'byu', びょ: 'byo',
  ぴゃ: 'pya', ぴゅ: 'pyu', ぴょ: 'pyo',
  みゃ: 'mya', みゅ: 'myu', みょ: 'myo',
  りゃ: 'rya', りゅ: 'ryu', りょ: 'ryo',
  でぃ: 'di', てぃ: 'ti', とぅ: 'tu',
  うぃ: 'wi', うぇ: 'we', うぉ: 'wo',
  ふぁ: 'fa', ふぃ: 'fi', ふぇ: 'fe', ふぉ: 'fo',
  ゔぁ: 'va', ゔぃ: 'vi', ゔ: 'vu', ゔぇ: 've', ゔぉ: 'vo',
  しぇ: 'she', じぇ: 'je', ちぇ: 'che',
  つぁ: 'tsa', つぃ: 'tsi', つぇ: 'tse', つぉ: 'tso',
  くぁ: 'kwa', くぃ: 'kwi', くぇ: 'kwe', くぉ: 'kwo',
  ぐぁ: 'gwa', ぐぃ: 'gwi', ぐぇ: 'gwe', ぐぉ: 'gwo',
  ぁ: 'a', ぃ: 'i', ぅ: 'u', ぇ: 'e', ぉ: 'o',
  ゃ: 'ya', ゅ: 'yu', ょ: 'yo', ゎ: 'wa',
  っ: 'っ',
}

/** 片假名转平假名（用于统一查表） */
function toHira(ch: string): string {
  const code = ch.charCodeAt(0)
  if (code >= 0x30a1 && code <= 0x30f6) {
    return String.fromCharCode(code - 0x60)
  }
  return ch
}

/** 将任意字符串中可转的假名转换为罗马字 */
export function toRomaji(input: string): string {
  const chars = Array.from(input)
  let out = ''
  for (let i = 0; i < chars.length; i++) {
    const c = chars[i]
    if (c === 'っ' || c === 'ッ') {
      // 促音：吞掉，下一音节辅音双写
      const next = i + 1 < chars.length ? toHira(chars[i + 1]) : ''
      const syl = HIRA[next + (i + 2 < chars.length ? toHira(chars[i + 2]) : '')] ?? HIRA[next] ?? ''
      if (syl) {
        out += /^ch/.test(syl) ? 't' : syl.slice(0, 1)
      }
      continue
    }
    // 两字符拗音
    const two = toHira(c) + (i + 1 < chars.length ? toHira(chars[i + 1]) : '')
    if (HIRA[two]) {
      out += HIRA[two]
      i += 1
      continue
    }
    const one = toHira(c)
    if (HIRA[one] && one !== 'っ') {
      let rom = HIRA[one]
      if (one === 'ん') {
        const nxt = i + 1 < chars.length ? toHira(chars[i + 1]) : ''
        if (/^[bpm]/.test(HIRA[nxt] ?? '')) rom = 'm'
      }
      out += rom
      continue
    }
    // 长音：おう / おお -> ō
    if (one === 'お' && i + 1 < chars.length) {
      const nxt = toHira(chars[i + 1])
      if (nxt === 'う' || nxt === 'お') {
        out += 'ō'
        i += 1
        continue
      }
    }
    if (one === 'う' && i + 1 < chars.length && toHira(chars[i + 1]) === 'う') {
      out += 'ū'
      i += 1
      continue
    }
    // 其他字符原样
    out += c
  }
  return out
}