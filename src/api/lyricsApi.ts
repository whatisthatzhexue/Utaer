import type {
  EmotionKey,
  EmotionResult,
  EmotionScore,
  GrammarItem,
  LyricsAnalysisRequest,
  LyricsAnalysisResult,
  PitchSeries,
  TokenAnalysisItem,
  TokenItem,
} from '../types'
import { hasWord } from './wordApi'

/**
 * 歌词声调 · 情感分析的 Mock 实现
 *
 * 说明：该模块不访问真实后端，而是根据输入的日语歌词，
 * 用内置词库 + 规则打分 + 确定性伪随机数生成一份“像模像样”的分析结果，
 * 用于前端流程联调与演示。后续接入真实 UniDic / LLM 服务时，
 * 将本文件替换为后端调用即可（函数签名保持不变）。
 */

/** Mock 歌词词典：用于“分词 + 解析”（surface -> 词条信息） */
const LEXICON: Record<string, { reading: string; pos: string; posDetail: string; meaning: string }> = {
  晴れ: { reading: 'はれ', pos: '名词', posDetail: '普通名词', meaning: '晴天' },
  空: { reading: 'そら', pos: '名词', posDetail: '普通名词', meaning: '天空' },
  下: { reading: 'した', pos: '名词', posDetail: '方位名词', meaning: '下方' },
  夢: { reading: 'ゆめ', pos: '名词', posDetail: '普通名词', meaning: '梦想' },
  走り: { reading: 'はしり', pos: '动词', posDetail: '五段·连用形', meaning: '奔跑' },
  出す: { reading: 'だす', pos: '动词', posDetail: '五段（补助）', meaning: '开始…' },
  今日: { reading: 'きょう', pos: '名词', posDetail: '时点名词', meaning: '今天' },
  幸せ: { reading: 'しあわせ', pos: '名词', posDetail: '名词·形容动词', meaning: '幸福' },
  君: { reading: 'きみ', pos: '名词', posDetail: '人称代词', meaning: '你' },
  届く: { reading: 'とどく', pos: '动词', posDetail: '五段', meaning: '到达、传达' },
  笑い: { reading: 'わらい', pos: '动词', posDetail: '五段·连用形', meaning: '笑' },
  歌: { reading: 'うた', pos: '名词', posDetail: '普通名词', meaning: '歌' },
  光: { reading: 'ひかり', pos: '名词', posDetail: '普通名词', meaning: '光' },
  夜: { reading: 'よる', pos: '名词', posDetail: '时点名词', meaning: '夜晚' },
  星: { reading: 'ほし', pos: '名词', posDetail: '普通名词', meaning: '星星' },
  願い: { reading: 'ねがい', pos: '名词', posDetail: '普通名词', meaning: '愿望' },
  涙: { reading: 'なみだ', pos: '名词', posDetail: '普通名词', meaning: '眼泪' },
  季節: { reading: 'きせつ', pos: '名词', posDetail: '普通名词', meaning: '季节' },
  心: { reading: 'こころ', pos: '名词', posDetail: '普通名词', meaning: '心' },
  優しい: { reading: 'やさしい', pos: '形容词', posDetail: 'イ形容词', meaning: '温柔' },
  さよなら: { reading: 'さよなら', pos: '感叹词', posDetail: '寒暄语', meaning: '再见' },
  会える: { reading: 'あえる', pos: '动词', posDetail: '一段·可能形', meaning: '能相见' },
  メロディ: { reading: 'めろでぃ', pos: '名词', posDetail: '外来语', meaning: '旋律' },
  響け: { reading: 'ひびけ', pos: '动词', posDetail: '五段·命令形', meaning: '响彻' },
  た: { reading: 'た', pos: '助动词', posDetail: '过去/完成', meaning: '表过去' },
  の: { reading: 'の', pos: '助词', posDetail: '格助词', meaning: '的（定语）' },
  で: { reading: 'で', pos: '助词', posDetail: '格助词', meaning: '在…' },
  を: { reading: 'を', pos: '助词', posDetail: '格助词', meaning: '（宾语）' },
  が: { reading: 'が', pos: '助词', posDetail: '格助词', meaning: '（主语）' },
  は: { reading: 'は', pos: '助词', posDetail: '提示助词', meaning: '（主题）' },
  に: { reading: 'に', pos: '助词', posDetail: '格助词', meaning: '向…/在…' },
  へ: { reading: 'へ', pos: '助词', posDetail: '格助词', meaning: '向…' },
  も: { reading: 'も', pos: '助词', posDetail: '提示助词', meaning: '也' },
  と: { reading: 'と', pos: '助词', posDetail: '格助词', meaning: '和…/与…' },
  て: { reading: 'て', pos: '助词', posDetail: '接续助词', meaning: '（接续）' },
  る: { reading: 'る', pos: '助动词', posDetail: '辞书形词尾', meaning: '（终止形）' },
}

const EMOTION_KEYWORDS: Record<EmotionKey, string[]> = {
  joy: ['笑い', '幸せ', '夢', '晴れ', '光', '歌', '好き', '輝く', 'ありがとう', '届く', '走り'],
  sad: ['涙', '悲', '別れ', '寂', '泣', '痛', '暗', 'さよなら', '届かない', '叶わない'],
  miss: ['思い出', '記憶', '月', '星', '夜', '季節', 'あの日', '忘れない', '変わら', '想い'],
  fire: ['走れ', '叫', '燃', '風', '明日', '信じ', '強く', '飛', '越え', '立ち上が'],
  tender: ['優', 'そば', '抱き', '守', '暖', '微笑', 'そっと', '手を', '君', 'あなた'],
}

const EMOTION_LABEL: Record<EmotionKey, string> = {
  joy: '喜悦',
  sad: '悲伤',
  miss: '怀念',
  fire: '激昂',
  tender: '温柔',
}

const GRAMMAR_RULES: Array<{ test: string; pattern: string; explanation: string }> = [
  { test: 'ている', pattern: '～ている', explanation: '表示动作的持续或状态的延续。' },
  { test: 'てしまう', pattern: '～てしまう', explanation: '表示动作完结，或带有遗憾、强调的语气。' },
  { test: 'ように', pattern: '～ように', explanation: '表示目的或样态（为了… / 像…一样）。' },
  { test: 'たい', pattern: '～たい', explanation: '第一人称愿望：想…。' },
  { test: 'ながら', pattern: '～ながら', explanation: '一边…一边…。' },
  { test: 'たら', pattern: '～たら', explanation: '假设/条件：如果…的话。' },
  { test: 'ます', pattern: '～ます', explanation: '礼貌体（丁宁体）结尾。' },
  { test: 'ない', pattern: '～ない', explanation: '否定形式。' },
]

/** 从歌词文本中取出字符序列（忽略空白与标点） */
function cleanLyric(lyric: string): string {
  return lyric.replace(/[\s、。！？「」『』（）()…·・—\-–]/g, '')
}

/** 基于 seed 的确定性伪随机数（同一输入 -> 同一结果） */
function makeRng(seed: string): () => number {
  let h = 2166136261
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  let state = h >>> 0
  return () => {
    state = (state + 0x6d2b79f5) | 0
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** 贪心最长匹配分词（Mock） */
function tokenize(lyric: string): TokenItem[] {
  const text = cleanLyric(lyric)
  const keys = Object.keys(LEXICON).sort((a, b) => b.length - a.length)
  const result: TokenItem[] = []
  let i = 0
  while (i < text.length) {
    let matched = false
    for (const key of keys) {
      if (text.startsWith(key, i)) {
        const info = LEXICON[key]
        result.push({
          surface: key,
          reading: info.reading,
          pos: info.pos,
          posDetail: info.posDetail,
          meaning: info.meaning,
        })
        i += key.length
        matched = true
        break
      }
    }
    if (!matched) {
      const ch = text[i]
      result.push({
        surface: ch,
        reading: ch,
        pos: '未分词（Mock）',
        posDetail: hasWord(ch) ? '收录于示例词典' : '待 UniDic 解析',
        meaning: '',
      })
      i += 1
    }
  }
  return result
}

/** 情感打分（Mock） */
function analyzeEmotion(lyric: string): EmotionResult {
  const list: EmotionScore[] = (Object.keys(EMOTION_KEYWORDS) as EmotionKey[]).map((key) => {
    let score = 0
    for (const word of EMOTION_KEYWORDS[key]) {
      if (lyric.includes(word)) score += 1
    }
    return { key, label: EMOTION_LABEL[key], score }
  })
  const total = list.reduce((sum, item) => sum + item.score, 0)
  if (total === 0) {
    return {
      main: { key: 'joy', label: '喜悦', score: 0.4 },
      confidence: 58,
      secondary: [
        { key: 'tender', label: '温柔', score: 0.28 },
        { key: 'miss', label: '怀念', score: 0.22 },
      ],
    }
  }
  const sorted = [...list].sort((a, b) => b.score - a.score)
  const main = sorted[0]
  const confidence = Math.min(97, 62 + Math.round(33 * (main.score / total)))
  const secondary = sorted
    .filter((item) => item.score > 0 && item.key !== main.key)
    .slice(0, 2)
  return { main, confidence, secondary }
}

/** 语法点检测（Mock） */
function analyzeGrammar(lyric: string): GrammarItem[] {
  const found = GRAMMAR_RULES.filter((rule) => lyric.includes(rule.test)).slice(0, 4)
  if (found.length === 0) {
    return [
      {
        pattern: '（无典型句型匹配）',
        explanation: '当前 Mock 规则未在歌词中检测到典型语法点，正式版由句法分析模块提供。',
      },
    ]
  }
  return found.map((rule) => ({ pattern: rule.pattern, explanation: rule.explanation }))
}

/** 生成声调对比折线图数据（Mock，确定性伪随机） */
function buildPitchSeries(lyric: string): PitchSeries[] {
  const rng = makeRng(lyric || 'default')
  const count = Math.min(18, Math.max(8, Math.ceil(cleanLyric(lyric).length / 2)))
  const base: number[] = []
  const sung: number[] = []
  for (let i = 0; i < count; i++) {
    const wave = 0.5 + 0.28 * Math.sin((i / Math.max(count - 1, 1)) * Math.PI * 2)
    const d = Math.min(0.92, Math.max(0.12, wave + (rng() - 0.5) * 0.24))
    base.push(Number(d.toFixed(3)))
    const s = Math.min(0.92, Math.max(0.12, d + (rng() - 0.5) * 0.2))
    sung.push(Number(s.toFixed(3)))
  }
  const label = (i: number) => String(i + 1)
  return [
    { name: '词典调型（UniDic）', color: '#5aa7e0', points: base.map((v, i) => ({ label: label(i), value: v })) },
    { name: '演唱音高（示意）', color: '#ffc53d', points: sung.map((v, i) => ({ label: label(i), value: v })) },
  ]
}

/**
 * 歌词声调 · 情感分析（Mock）
 * @param request 歌词与可选音频
 */
export async function analyzeLyrics(request: LyricsAnalysisRequest): Promise<LyricsAnalysisResult> {
  const lyric = request.lyric.trim()
  const tokens = tokenize(lyric)
  const tokenAnalyses: TokenAnalysisItem[] = tokens.slice(0, 6).map((token) => ({
    surface: token.surface,
    reading: token.reading,
    pos: `${token.pos}（${token.posDetail}）`,
    meaning: token.meaning || '（待 UniDic 返回释义）',
    note: token.meaning
      ? `「${token.surface}」在歌词中为${token.pos}用法，示例释义：${token.meaning}。`
      : `「${token.surface}」暂未在 Mock 词库收录，正式版由 UniDic 解析。`,
  }))

  return {
    lyric,
    pitchSeries: buildPitchSeries(lyric),
    emotion: analyzeEmotion(lyric),
    tokens,
    tokenAnalyses,
    grammar: analyzeGrammar(lyric),
  }
}