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
  /** 歌词振假名（逐词 surface -> reading） */
  rubyPairs: RubyPair[]
  /** 整段歌词罗马音（保留词内促音/长音上下文） */
  romaji: string
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

/** 振假名：汉字/词的表记与读音 */
export interface RubyPair {
  /** 表记（汉字/词形，如 空） */
  surface: string
  /** 读音（假名，如 そら） */
  reading: string
}

/** 声调曲线中的单个采样点 */
export interface AudioAccentPoint {
  /** 时间（秒） */
  time: number
  /** 基频 F0（Hz），浊音段有值、清音/停顿为 0 或 null */
  f0: number | null
  /** 所属音拍（mora）序号 */
  moraIndex?: number
}

/** 后端 accent_analysis 任务结果（audio_accent.json） */
export interface AudioAccentData {
  /** 用户音频的声调曲线 */
  points: AudioAccentPoint[]
  /** 标准/正确音调曲线（用于前端对比匹配） */
  canonical: AudioAccentPoint[]
  /** mora 边界时间点 */
  moraBoundaries: number[]
  /** 歌词振假名 */
  rubyPairs: RubyPair[]
}

/** F0 统计 */
export interface F0Stats {
  mean: number
  min: number
  max: number
  range: number
  std: number
}

/** 后端 feature_analysis 任务结果（audio_feature.json） */
export interface AudioFeatureData {
  /** 能量包络（归一化 0-1 序列） */
  energy: number[]
  /** F0 统计 */
  f0Stats: F0Stats
  /** 频谱图（每个时间帧一个频点数组，可先 mock） */
  spectrum: number[][]
  /** 情感分析（可选） */
  emotion?: {
    label: string
    confidence: number
  }
}

/** Supabase 分析任务状态 */
export type AnalysisTaskStatus = 'pending' | 'completed' | 'failed'

/** Supabase 分析任务类型 */
export type AnalysisTaskType = 'accent_analysis' | 'feature_analysis'

/** Supabase 分析任务记录 */
export interface AnalysisTask {
  id: string
  type: AnalysisTaskType
  status: AnalysisTaskStatus
  resultPath?: string
  error?: string
}

/* ============================================================
 * 3.3.1 Utaer 声调信息传输规范（audio_accent.json / audio_feature.json）
 * 前端与后端以此为准对接；下方为“显示层”的旧类型，保留兼容。
 * ============================================================ */

/** ruby_pairs 元素： [汉字|null, 假名] */
export type RubyPairTuple = [string | null, string]

/** json_data 中的单个形态素（顺序与 input 一致） */
export interface UtaerMorph {
  /** 在 input 中的整体索引（从 0 开始） */
  idx: number
  /** 表面形（原文书写形式，可含汉字/假名/符号） */
  morph: string
  /** 辞书形（原形） */
  lemma: string
  /** 表面形的读音（全假名） */
  morph_reading: string
  /** 辞书形的读音（全假名） */
  lemma_reading: string
  /** UniDic 词性标签（三级，以 * 分隔，如 名詞*普通名詞*一般） */
  pos: string
  /** 声调核位置：0 平板 / 1 头高 / ≥2 中高或尾高；句中变调取最终值 */
  drop: number
  /** 该词所有可能的声调核位置（第一个为推荐读音） */
  drops: number[]
  /** 无声化（母音脱落）位置索引 */
  devoice_locations: number[]
  /** 注音对，用于生成 <ruby>；[null, 假名] 表示上一字符的余部（送假名） */
  ruby_pairs: RubyPairTuple[]
  /** 应用到的声调规则（人类可读） */
  applied_rules: string[]
}

/** source 来源元数据（无则传空对象） */
export interface UtaerSource {
  title?: string
  artist?: string
  album?: string
  [key: string]: unknown
}

/** audio_accent.json 顶层结构 */
export interface UtaerAccentDoc {
  /** 句子/练习唯一数字标识 */
  id: number
  /** 显示标题（歌曲名/例句场景名） */
  title: string
  /** 原始日语文本（未分词），前端作原文展示 */
  input: string
  /** 语法结构与声调特点的友好说明 */
  description: string
  /** 来源元数据 */
  source: UtaerSource
  /** 知识点标签 */
  topics: string[]
  /** 详细声调笔记（可含 HTML） */
  notes: string[]
  /** true = 多句段落，false = 单句 */
  is_paragraph: boolean
  /** 核心声调数据（形态素级，与 input 顺序一致） */
  json_data: UtaerMorph[]
}

/** audio_feature.json（建议结构，占位） */
export interface AudioFeatureResponse {
  /** 能量包络，时间轴与音频帧对齐 */
  energy: number[]
  f0_stats: {
    mean: number
    min: number
    max: number
    range: number
    std: number
  }
  spectral: {
    bandEnergy?: number[]
    centroid?: number[]
    [key: string]: unknown
  }
  emotion: {
    label: string
    confidence: number
  }
}

/** 登录用户信息（Mock 会话） */
export interface UserInfo {
  id: string
  name: string
  email: string
  createdAt: number
}