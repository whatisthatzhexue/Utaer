import type {
  AudioFeatureResponse,
  RubyPair,
  RubyPairTuple,
  UtaerAccentDoc,
  UtaerMorph,
} from '../types'

/**
 * 3.3.1 声调信息传输规范（Mock 实现）
 *
 * audio_accent.json / audio_feature.json 严格遵循后端约定：
 * - accent_analysis 任务结果 -> audio_accent.json（下方 getAudioAccent 的返回结构）
 * - feature_analysis 任务结果 -> audio_feature.json（下方 getAudioFeature 的返回结构）
 * 后端就绪后，将函数内部替换为「轮询 Supabase 任务并读取结果文件」即可，
 * 函数签名保持不变。
 */

const MOCK_ACCENT: UtaerAccentDoc = {
  id: 0,
  title: '【示例】晴れた空の下で（歌词开头）',
  input: '晴れた空の下で 君と笑い合う',
  description: '名詞のアクセントと助詞の結合、複合動詞のアクセントを確認できる例文。',
  source: {},
  topics: ['アクセントの種類（例：頭高型・平板型）', '助詞の結合規則', '複合語のアクセント'],
  notes: [
    '「空の下」の「空」は頭高型①で、助詞「の」が付いても「そ↓らの」のまま下がる。',
    '「笑い合う」のような複合動詞は後部要素「合う」に依存し、平板に読まれることが多い。',
  ],
  is_paragraph: false,
  json_data: [
    { idx: 0, morph: '晴れ', lemma: '晴れ', morph_reading: 'はれ', lemma_reading: 'はれ', pos: '名詞*普通名詞*一般', drop: 0, drops: [0], devoice_locations: [], ruby_pairs: [['晴', 'はれ']], applied_rules: ['平板型：第2拍以降高い'] },
    { idx: 1, morph: 'た', lemma: 'た', morph_reading: 'た', lemma_reading: 'た', pos: '助動詞', drop: 0, drops: [0], devoice_locations: [], ruby_pairs: [], applied_rules: ['「た」は連用形に付く過去・完了の助動詞'] },
    { idx: 2, morph: '空', lemma: '空', morph_reading: 'そら', lemma_reading: 'そら', pos: '名詞*普通名詞*一般', drop: 1, drops: [1], devoice_locations: [], ruby_pairs: [['空', 'そら']], applied_rules: ['頭高型：第1拍の後で下降'] },
    { idx: 3, morph: 'の', lemma: 'の', morph_reading: 'の', lemma_reading: 'の', pos: '助詞*格助詞', drop: 0, drops: [0], devoice_locations: [], ruby_pairs: [], applied_rules: ['格助詞「の」は平板を保って続く'] },
    { idx: 4, morph: '下', lemma: '下', morph_reading: 'した', lemma_reading: 'した', pos: '名詞*普通名詞*一般', drop: 1, drops: [1], devoice_locations: [], ruby_pairs: [['下', 'した']], applied_rules: ['頭高型：第1拍の後で下降'] },
    { idx: 5, morph: 'で', lemma: 'で', morph_reading: 'で', lemma_reading: 'で', pos: '助詞*格助詞', drop: 0, drops: [0], devoice_locations: [], ruby_pairs: [], applied_rules: ['格助詞「で」は平板を保って続く'] },
    { idx: 6, morph: '君', lemma: '君', morph_reading: 'きみ', lemma_reading: 'きみ', pos: '名詞*普通名詞*一般', drop: 1, drops: [1], devoice_locations: [], ruby_pairs: [['君', 'きみ']], applied_rules: ['頭高型：第1拍の後で下降'] },
    { idx: 7, morph: 'と', lemma: 'と', morph_reading: 'と', lemma_reading: 'と', pos: '助詞*格助詞', drop: 0, drops: [0], devoice_locations: [], ruby_pairs: [], applied_rules: ['格助詞「と」は平板を保って続く'] },
    { idx: 8, morph: '笑い', lemma: '笑う', morph_reading: 'わらい', lemma_reading: 'わらう', pos: '動詞*一般', drop: 2, drops: [2], devoice_locations: [], ruby_pairs: [['笑', 'わら'], [null, 'い']], applied_rules: ['中高型：第2拍の後で下降'] },
    { idx: 9, morph: '合う', lemma: '合う', morph_reading: 'あう', lemma_reading: 'あう', pos: '動詞*一般', drop: 0, drops: [0], devoice_locations: [], ruby_pairs: [['合', 'あ'], [null, 'う']], applied_rules: ['複合動詞の後部：平板に読まれることが多い'] },
  ],
}

/** 模拟网络延迟 */
function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

/** 获取声调分析结果（audio_accent.json，按规范） */
export async function getAudioAccent(docId = 0): Promise<UtaerAccentDoc> {
  await wait(240)
  const doc = clone(MOCK_ACCENT)
  doc.id = docId
  return doc
}

/** 获取音频特征结果（audio_feature.json，占位结构） */
export async function getAudioFeature(): Promise<AudioFeatureResponse> {
  await wait(240)
  return clone<AudioFeatureResponse>({
    energy: [0.1, 0.24, 0.6, 0.9, 0.7, 0.45, 0.2, 0.15],
    f0_stats: { mean: 210, min: 150, max: 330, range: 180, std: 42 },
    spectral: { bandEnergy: [0.8, 0.6, 0.4, 0.2], centroid: [820, 900, 760, 640] },
    emotion: { label: '喜悦', confidence: 82 },
  })
}

/* ============ 供前端展示层使用的转换工具 ============ */

/** drop 数值 -> 调型中文名 */
export function dropLabel(drop: number): string {
  if (drop === 0) return '平板型'
  if (drop === 1) return '头高型'
  return `中高/尾高型（${drop}）`
}

/** 该形态素是否平板型 */
export function isHeiban(morph: UtaerMorph): boolean {
  return morph.drop === 0
}

/** 把规范 ruby_pairs（二元组）转为页面 ruby 展示对象 */
export function morphToRubyPairs(morph: UtaerMorph): RubyPair[] {
  const pairs: RubyPair[] = morph.ruby_pairs
    .filter((tuple: RubyPairTuple) => tuple[0] !== null)
    .map((tuple: RubyPairTuple) => ({ surface: tuple[0] as string, reading: tuple[1] }))
  if (pairs.length === 0 && morph.morph_reading) {
    pairs.push({ surface: morph.morph, reading: morph.morph_reading })
  }
  return pairs
}