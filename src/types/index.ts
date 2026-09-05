/**
 * Utaer（歌er）领域类型定义
 * 说明：当前阶段为占位/示意，后续接入 UniDic 与 LLM 服务后，各接口字段与返回结构
 * 可直接对应后端响应，前端仅需将实际数据填充进这些结构。
 */

/** 日语声调音拍的高低：H = 高拍，L = 低拍 */
export type PitchLevel = 'H' | 'L'

/** 整体情感标签的可选取值 */
export type EmotionKey = 'joy' | 'sad' | 'miss' | 'fire' | 'tender'

/** 词条释义的例句（日文 + 中文） */
export interface AccentExample {
  /** 日文例句 */
  jp: string
  /** 中文翻译 */
  zh: string
}

/**
 * UniDic 词条查询结果（词性 + 声调）
 * 对应页面中的“词性·声调查询”卡片与歌词逐词词卡。
 */
export interface AccentWord {
  /** 表记（输入的书写形式，如：食べる） */
  surface: string
  /** 读音（假名，如：たべる） */
  reading: string
  /** 词性（如：动词、名词、形容动词） */
  pos: string
  /** 词性细类 / 活用类型（如：一段活用） */
  posDetail: string
  /** 声调调型序号：0 平板型、1 头高型、2 中高型…… */
  accentNumber: number
  /** 声调调型名称（如：平板型 / 头高型 / 中高型） */
  accentName: string
  /** 各音拍的高低，与 moras 一一对应 */
  accentPattern: PitchLevel[]
  /** 按音拍切分的读音（如：['た', 'べ', 'る']） */
  moras: string[]
  /** 释义 */
  meaning: string
  /** 例句 */
  example: AccentExample
}

/** 折线图中的单个数据点 */
export interface PitchPoint {
  /** X 轴标签（音拍/小节序号或时间点） */
  label: string
  /** Y 轴数值（音高，Hz 或归一化值） */
  value: number
}

/** 折线图中的一条序列（如：词典调型、演唱音高） */
export interface PitchSeries {
  /** 序列名称 */
  name: string
  /** 序列颜色 */
  color: string
  /** 数据点 */
  points: PitchPoint[]
}

/** 单个情感倾向及其得分 */
export interface EmotionScore {
  /** 情感键值 */
  key: EmotionKey
  /** 情感名称（如：喜悦） */
  label: string
  /** 得分 0-1 */
  score: number
}

/** 情感分析结果 */
export interface EmotionResult {
  /** 主情感 */
  main: EmotionScore
  /** 主情感可信度百分比 0-100 */
  confidence: number
  /** 次要情感倾向（降序） */
  secondary: EmotionScore[]
}

/** 歌词分词结果中的单个词 */
export interface TokenItem {
  /** 词形（表记） */
  surface: string
  /** 读音 */
  reading: string
  /** 词性 */
  pos: string
  /** 词性细类 */
  posDetail: string
  /** 原形 */
  lemma?: string
  /** 中文释义（可选） */
  meaning?: string
}

/** 分词解析中的单条说明 */
export interface TokenAnalysisItem {
  /** 词形 */
  surface: string
  /** 读音 */
  reading: string
  /** 词性（含细类） */
  pos: string
  /** 中文释义 */
  meaning: string
  /** 面向用户的解释文字 */
  note: string
}

/** 语法解析中的单条说明 */
export interface GrammarItem {
  /** 语法点或句型（如：～ている） */
  pattern: string
  /** 通俗解释 */
  explanation: string
  /** 示例（可选） */
  example?: string
}

/**
 * 歌词声调 · 情感分析请求
 */
export interface LyricsAnalysisRequest {
  /** 日语歌词文本 */
  lyric: string
  /** 演唱音频：尚未接入真实处理时传 null；后续可传 File 或 URL */
  audio?: File | string | null
  /** 是否需要对分词做逐词展开（默认 true） */
  withDetail?: boolean
}

/**
 * 歌词声调 · 情感分析结果
 * 对应页面“歌词声调分析”的六类输出。
 */
export interface LyricsAnalysisResult {
  /** 输出歌词（原文，可回显/整理） */
  lyric: string
  /** 声调对比折线图数据 */
  pitchSeries: PitchSeries[]
  /** 情感分析 */
  emotion: EmotionResult
  /** 歌词分词结果 */
  tokens: TokenItem[]
  /** 对分词的解析 */
  tokenAnalyses: TokenAnalysisItem[]
  /** 歌词语法解析 */
  grammar: GrammarItem[]
}

/**
 * 前端调用后端服务的接口约定。
 * 当前为占位阶段：可在后续实现中对接 UniDic 解析与 LLM 分析接口。
 */
export interface UtaerService {
  /** UniDic 词性 + 声调查询 */
  lookupWord(word: string): Promise<AccentWord>
  /** 歌词声调 + 情感分析 */
  analyzeLyrics(request: LyricsAnalysisRequest): Promise<LyricsAnalysisResult>
}