import type { AccentWord, PitchLevel } from '../types'

/**
 * UniDic 词性 · 声调查询的 Mock 实现
 *
 * 当前阶段不依赖真实后端：lookupWord 会先查询内置示例词库，
 * 未收录的词则返回一个带“未收录”标记的示意结果。
 *
 * 后续接入真实服务时，将本文件中 MOCK_DICT 相关逻辑替换为：
 *   const res = await fetch(`/api/unidic/word?q=${encodeURIComponent(word)}`)
 *   return (await res.json()) as AccentWord
 * 函数签名保持不变即可，调用方无需改动。
 */

const MOCK_DICT: Record<string, AccentWord> = {
  食べる: {
    surface: '食べる',
    reading: 'たべる',
    pos: '动词',
    posDetail: '一段活用',
    accentNumber: 0,
    accentName: '平板型',
    accentPattern: ['L', 'H', 'H'],
    moras: ['た', 'べ', 'る'],
    meaning: '吃',
    example: { jp: '毎朝ご飯を食べる。', zh: '每天早上吃饭。' },
  },
  見る: {
    surface: '見る',
    reading: 'みる',
    pos: '动词',
    posDetail: '一段活用',
    accentNumber: 1,
    accentName: '头高型',
    accentPattern: ['H', 'L'],
    moras: ['み', 'る'],
    meaning: '看',
    example: { jp: '空を見る。', zh: '看天空。' },
  },
  猫: {
    surface: '猫',
    reading: 'ねこ',
    pos: '名词',
    posDetail: '普通名词',
    accentNumber: 1,
    accentName: '头高型',
    accentPattern: ['H', 'L'],
    moras: ['ね', 'こ'],
    meaning: '猫',
    example: { jp: '猫が好きです。', zh: '我喜欢猫。' },
  },
  空: {
    surface: '空',
    reading: 'そら',
    pos: '名词',
    posDetail: '普通名词',
    accentNumber: 1,
    accentName: '头高型',
    accentPattern: ['H', 'L'],
    moras: ['そ', 'ら'],
    meaning: '天空',
    example: { jp: '青い空を見上げる。', zh: '仰望蓝天。' },
  },
  心: {
    surface: '心',
    reading: 'こころ',
    pos: '名词',
    posDetail: '普通名词',
    accentNumber: 2,
    accentName: '中高型',
    accentPattern: ['L', 'H', 'L'],
    moras: ['こ', 'こ', 'ろ'],
    meaning: '心',
    example: { jp: '心に残る歌。', zh: '留在心中的歌。' },
  },
  綺麗: {
    surface: '綺麗',
    reading: 'きれい',
    pos: '形容动词',
    posDetail: 'ナ形容词',
    accentNumber: 1,
    accentName: '头高型',
    accentPattern: ['H', 'L', 'L'],
    moras: ['き', 'れ', 'い'],
    meaning: '漂亮；干净',
    example: { jp: 'とても綺麗な景色。', zh: '非常漂亮的景色。' },
  },
  幸せ: {
    surface: '幸せ',
    reading: 'しあわせ',
    pos: '名词',
    posDetail: '名词·形容动词',
    accentNumber: 0,
    accentName: '平板型',
    accentPattern: ['L', 'H', 'H', 'H'],
    moras: ['し', 'あ', 'わ', 'せ'],
    meaning: '幸福',
    example: { jp: '君の幸せを願う。', zh: '祝愿你幸福。' },
  },
}

/** 模拟网络延迟 */
function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

/** 深拷贝，避免调用方修改共享的 Mock 数据 */
function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

/** 词库未收录时生成一个带标记的示意结果 */
function buildFallback(surface: string): AccentWord {
  const chars = Array.from(surface).slice(0, 6)
  const moras = chars.length > 0 ? chars : ['—']
  const pattern: PitchLevel[] = moras.map((_, index) => (index === 0 ? 'L' : 'H'))
  return {
    surface,
    reading: '（待 UniDic 返回）',
    pos: '名词',
    posDetail: '词库未收录',
    accentNumber: 0,
    accentName: '平板型（示意）',
    accentPattern: pattern,
    moras,
    meaning: '（该词尚未收录，正式释义将由 UniDic 返回）',
    example: {
      jp: surface,
      zh: '内置 Mock 词库未收录该词，正式解析将由 UniDic 提供。',
    },
  }
}

/**
 * UniDic 词性 · 声调查询（Mock）
 * @param word 日语单词，如「食べる」
 */
export async function lookupWord(word: string): Promise<AccentWord> {
  const key = word.trim()
  if (!key) {
    throw new Error('请输入要查询的日语单词')
  }
  await wait(260) // 模拟请求耗时
  const hit = MOCK_DICT[key]
  return hit ? clone(hit) : buildFallback(key)
}

/** 可测试用：同步返回 Mock 词库是否收录 */
export function hasWord(word: string): boolean {
  return Object.prototype.hasOwnProperty.call(MOCK_DICT, word.trim())
}