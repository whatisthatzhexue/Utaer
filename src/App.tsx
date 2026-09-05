import { useState } from 'react'
import {
  ConfigProvider,
  Menu,
  Button,
  Input,
  Upload,
  Card,
  Empty,
  Tag,
  Divider,
  Typography,
  Space,
  Flex,
} from 'antd'
import {
  HomeOutlined,
  LineChartOutlined,
  InfoCircleOutlined,
  UploadOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  SmileOutlined,
  TagsOutlined,
  BranchesOutlined,
  AudioOutlined,
  SoundOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { analyzeLyrics } from './api/lyricsApi'
import type { LyricsAnalysisResult, EmotionKey, PitchSeries } from './types'

type PageKey = 'home' | 'lyrics' | 'about'

const SLOGAN = '基于 UniDic 权威词典的日语音调可视化学习与歌唱分析工具'

const SAMPLE_LYRIC = `晴れた空の下で 君と笑い合う
夢を追いかけて 走り出す今日
幸せのメロディ 響け もっと高く
この歌が 君に届くまで`

const CSS = `
  :root { color-scheme: light; }
  html, body, #root { margin: 0; padding: 0; }
  body { background: #eef6fd; }
  #root {
    width: 100%;
    max-width: 100%;
    margin: 0;
    text-align: left;
    border: none;
    min-height: 100vh;
    display: block;
  }
  h1, h2, h3, p { margin: 0; }
  * { box-sizing: border-box; }

  .ute-app { min-height: 100vh; display: flex; flex-direction: column; background: #eef6fd; }
  .ute-bg {
    position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden;
    background:
      radial-gradient(700px 380px at 15% -5%, rgba(126, 185, 232, 0.35), transparent 60%),
      radial-gradient(760px 420px at 95% 0%, rgba(168, 208, 240, 0.30), transparent 60%),
      radial-gradient(560px 340px at 90% 105%, rgba(255, 205, 61, 0.16), transparent 60%),
      #eef6fd;
  }
  .ute-bg::after {
    content: ''; position: absolute; inset: 0;
    background-image:
      linear-gradient(rgba(96, 153, 200, 0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(96, 153, 200, 0.05) 1px, transparent 1px);
    background-size: 44px 44px;
  }

  /* ---- 顶部导航 ---- */
  .ute-header {
    position: relative; z-index: 10;
    display: flex; align-items: center; gap: 26px;
    padding: 0 30px; height: 64px;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid #dcebf8;
    box-shadow: 0 6px 20px -14px rgba(46, 112, 168, 0.5);
  }
  .ute-brand { display: flex; align-items: center; gap: 10px; cursor: pointer; user-select: none; }
  .ute-brand-logo {
    width: 34px; height: 34px; border-radius: 10px; color: #fff;
    display: grid; place-items: center; font-size: 19px;
    background: linear-gradient(135deg, #4e9cd9, #8ec6ea);
    box-shadow: 0 6px 14px -6px rgba(78, 156, 217, 0.6);
  }
  .ute-brand-name { font-size: 19px; font-weight: 700; color: #274b6d; letter-spacing: 0.5px; }
  .ute-brand-name em { font-style: normal; color: #ffc53d; }
  .ute-nav .ant-menu { background: transparent; border-bottom: none !important; min-width: 330px; }
  .ute-nav .ant-menu-item { font-size: 15px; }
  .ute-header-right { flex: 1; } /* 右侧暂时留白 */

  .ute-main { position: relative; z-index: 1; flex: 1; width: 100%; max-width: 1120px; margin: 0 auto; padding: 40px 26px 60px; }

  /* ---- 首页 ---- */
  .ute-home { position: relative; min-height: calc(100vh - 220px); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 30px 0; }
  .ute-home-badge {
    display: inline-flex; align-items: center; gap: 8px;
    color: #6b7f92; font-size: 13px; letter-spacing: 2px;
    background: rgba(255, 255, 255, 0.8); border: 1px solid #d9e9f7;
    padding: 7px 16px; border-radius: 999px;
  }
  .ute-home-badge .dot { width: 8px; height: 8px; border-radius: 50%; background: #ffc53d; box-shadow: 0 0 0 4px rgba(255, 197, 61, 0.25); }
  .ute-home-title {
    max-width: 900px; margin-top: 18px;
    font-size: clamp(48px, 8vw, 86px); font-weight: 800; line-height: 1.16; letter-spacing: 2px;
    background: linear-gradient(120deg, #1d4a78 10%, #3f92c9 60%, #6fb0e2);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  .ute-home-title .hl { color: #2e6fa8; }
  .ute-home-slogan {
    margin-top: 20px; color: #5f7186;
    font-size: clamp(17px, 2.6vw, 24px); font-weight: 500; line-height: 2.1;
    letter-spacing: 1px; max-width: 940px;
  }
  .ute-home-slogan .blue { color: #2e6fa8; font-weight: 700; }
  .ute-home-slogan .gold { color: #c98f16; font-weight: 700; position: relative; white-space: nowrap; }
  .ute-home-slogan .gold::after {
    content: ""; position: absolute; left: -2px; right: -2px; bottom: 2px; height: 9px; z-index: -1;
    background: rgba(255, 213, 79, 0.5); border-radius: 4px;
  }
  .ute-home-cta { margin-top: 30px; }
  .ute-home-hint { margin-top: 14px; color: #a6b6c7; font-size: 13px; }
  .ute-cta {
    height: 50px; padding: 0 34px; font-size: 17px; border-radius: 14px;
    background: linear-gradient(135deg, #4e9cd9, #7ab7e6) !important;
    box-shadow: 0 14px 26px -12px rgba(78, 156, 217, 0.85); border: none;
  }
  .ute-cta:hover { transform: translateY(-2px); box-shadow: 0 18px 34px -12px rgba(78, 156, 217, 0.95); }
  .ute-hero-deco { position: absolute; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
  .ute-home-badge, .ute-home-title, .ute-home-slogan, .ute-home-cta { position: relative; z-index: 1; }
  .ute-hero-deco .note { position: absolute; color: rgba(94, 160, 214, 0.18); animation: floatNote 6s ease-in-out infinite; }
  .ute-hero-deco .n1 { top: 10%; left: 15%; font-size: 34px; }
  .ute-hero-deco .n2 { top: 32%; right: 12%; font-size: 46px; animation-delay: 1.1s; }
  .ute-hero-deco .n3 { bottom: 22%; left: 10%; font-size: 26px; animation-delay: 2s; }
  .ute-hero-deco .n4 { bottom: 14%; right: 21%; font-size: 32px; animation-delay: 3s; }
  @keyframes floatNote {
    0%, 100% { transform: translateY(0) rotate(0deg); opacity: 0.45; }
    50% { transform: translateY(-16px) rotate(8deg); opacity: 1; }
  }
  .ute-home-hint { margin-top: 14px; color: #a6b6c7; font-size: 13px; }

  /* 首页入场动画：上方元素自上方淡入，下方元素自下方淡入 */
  @keyframes ufade-top { from { opacity: 0; transform: translateY(-26px); } to { opacity: 1; transform: none; } }
  @keyframes ufade-bottom { from { opacity: 0; transform: translateY(26px); } to { opacity: 1; transform: none; } }
  .u-anim-top { animation: ufade-top 0.75s cubic-bezier(0.22, 0.9, 0.3, 1) both; }
  .u-anim-bottom { animation: ufade-bottom 0.75s cubic-bezier(0.22, 0.9, 0.3, 1) both; }
  .u-d1 { animation-delay: 0.05s; }
  .u-d2 { animation-delay: 0.22s; }
  .u-d3 { animation-delay: 0.45s; }
  .u-d4 { animation-delay: 0.62s; }

  /* ---- 卡片区 ---- */
  .ute-card { border-radius: 16px; border: 1px solid #dcebf8; box-shadow: 0 14px 34px -22px rgba(46, 112, 168, 0.45); background: #fff; }
  .ute-sec-head { margin-bottom: 8px; }
  .ute-sec-desc { color: #7a8ca0; font-size: 14px; line-height: 1.8; margin-top: 6px; }
  .ute-panel { margin-bottom: 20px; }
  .ute-file-hint { margin-left: 10px; color: #5b7f9f; font-size: 13px; }

  .ute-analyze-action { text-align: center; margin-top: 4px; }

  /* 输出网格 */
  .ute-out-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 8px; }
  .ute-out-full { grid-column: 1 / -1; }
  .ute-out-card { height: 100%; }
  .ute-out-card .ant-card-head-title { font-weight: 700; color: #274b6d; }
  .ute-out-tip { color: #a8b8c8; font-size: 12.5px; margin-left: 8px; }
  .ute-lyric-text { white-space: pre-wrap; line-height: 2; color: #2c4259; font-size: 15px; }

  /* 折线图占位 */
  .ute-chart-wrap { width: 100%; }
  .ute-chart-svg { width: 100%; height: auto; display: block; }
  .ute-legend { display: flex; gap: 18px; justify-content: center; margin-top: 8px; font-size: 13px; color: #5f7186; }
  .ute-legend i { display: inline-block; width: 16px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }

  .ute-emotion-center { text-align: center; padding: 6px 0 2px; }
  .ute-emotion-label { font-size: 34px; font-weight: 800; color: #2e6fa8; margin-top: 6px; }
  .ute-bar { height: 10px; border-radius: 99px; background: #e8f1f9; overflow: hidden; margin: 10px 0; }
  .ute-bar i { display: block; height: 100%; border-radius: 99px; background: linear-gradient(90deg, #5aa7e0, #8ec6ea); }

  .ute-token { display: inline-flex; align-items: baseline; gap: 6px; margin: 4px 6px 4px 0; padding: 6px 12px; background: #f2f8fe; border: 1px solid #d6e8f8; border-radius: 8px; }
  .ute-token .jp { font-weight: 700; color: #274b6d; }
  .ute-token .meta { color: #7a8ca0; font-size: 12px; }

  .ute-grammar-line { display: flex; gap: 8px; align-items: flex-start; color: #3c5368; font-size: 14px; line-height: 1.9; padding: 6px 0; }
  .ute-grammar-line .idx { color: #ffc53d; font-weight: 700; }

  .ute-empty-tip { color: #9fb1c2; }

  /* 关于 */
  .ute-about-block { margin-bottom: 22px; }
  .ute-feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin-top: 8px; }
  .ute-feature { background: #f7fbfe; border: 1px solid #e2eef9; border-radius: 12px; padding: 14px 16px; }
  .ute-feature h4 { margin: 0 0 6px; font-size: 15px; color: #274b6d; }
  .ute-feature p { margin: 0; color: #708398; font-size: 13px; line-height: 1.8; }

  .ute-footer-note { text-align: center; color: #a3b4c5; font-size: 13px; padding: 18px 0 26px; position: relative; z-index: 1; }

  @media (max-width: 800px) {
    .ute-header { gap: 12px; padding: 0 14px; flex-wrap: wrap; height: auto; padding-top: 8px; }
    .ute-nav { order: 3; width: 100%; }
    .ute-nav .ant-menu { min-width: 0; }
    .ute-out-grid { grid-template-columns: 1fr; }
    .ute-main { padding: 22px 14px 40px; }
  }
`

const menuItems: MenuProps['items'] = [
  { key: 'home', icon: <HomeOutlined />, label: '首页' },
  { key: 'lyrics', icon: <LineChartOutlined />, label: '歌词声调分析' },
  { key: 'about', icon: <InfoCircleOutlined />, label: '关于' },
]

const EMO_COLOR: Record<EmotionKey, string> = {
  joy: '#38A169',
  sad: '#3182CE',
  miss: '#805AD5',
  fire: '#DD6B20',
  tender: '#D53F8C',
}

function renderChartCard(result: LyricsAnalysisResult) {
  const series = result.pitchSeries
  const all = series.flatMap((s) => s.points.map((p) => p.value))
  const min = Math.min(...all)
  const max = Math.max(...all)
  const span = max - min || 1
  const toPoints = (s: PitchSeries) => {
    const n = s.points.length
    return s.points
      .map((p, i) => {
        const x = n <= 1 ? 333 : 46 + (i * 574) / (n - 1)
        const y = 190 - ((p.value - min) / span) * 150
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }
  const first = series[0]
  const n0 = first ? first.points.length : 0
  const labelStep = Math.max(1, Math.ceil(n0 / 8))
  return (
    <Card
      className="ute-card ute-out-card ute-out-full"
      title={
        <span>
          声调对比折线图<Tag className="ute-out-tip" color="gold">Mock</Tag>
        </span>
      }
    >
      <svg className="ute-chart-svg" viewBox="0 0 640 230" role="img" aria-label="声调对比折线图（Mock）">
        {[0, 1, 2, 3].map((i) => (
          <line key={i} x1="46" y1={190 - i * 45} x2="620" y2={190 - i * 45} stroke="#e3eef8" strokeWidth="1" />
        ))}
        {series.map((s) => (
          <polyline
            key={s.name}
            points={toPoints(s)}
            fill="none"
            stroke={s.color}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
        {first
          ? first.points.map((p, i) => {
              if (i % labelStep !== 0 && i !== n0 - 1) return null
              const x = n0 <= 1 ? 333 : 46 + (i * 574) / (n0 - 1)
              return (
                <text
                  key={p.label}
                  x={x}
                  y="208"
                  fontSize="10"
                  fill="#9fb1c2"
                  textAnchor={i === 0 ? 'start' : i === n0 - 1 ? 'end' : 'middle'}
                >
                  {p.label}
                </text>
              )
            })
          : null}
      </svg>
      <div className="ute-legend">
        {series.map((s) => (
          <span key={s.name}>
            <i style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
    </Card>
  )
}

function renderEmotionCard(result: LyricsAnalysisResult) {
  const { main, confidence, secondary } = result.emotion
  const othersTotal = secondary.reduce((sum, item) => sum + item.score, 0)
  const allScore = main.score + othersTotal
  return (
    <Card
      className="ute-card ute-out-card"
      title={
        <span>
          情感分析<Tag className="ute-out-tip" color="gold">Mock</Tag>
        </span>
      }
    >
      <div className="ute-emotion-center">
        <SmileOutlined style={{ fontSize: 40, color: EMO_COLOR[main.key] }} />
        <div className="ute-emotion-label" style={{ color: EMO_COLOR[main.key] }}>
          {main.label}
        </div>
        <div style={{ color: '#7a8ca0', fontSize: 13 }}>整体情感倾向 · 可信度 {confidence}%</div>
        <div style={{ maxWidth: 320, margin: '14px auto 0' }}>
          <div style={{ fontSize: 13, color: '#5f7186', marginBottom: 4 }}>
            主情感 {main.label} · {confidence}%
          </div>
          <div className="ute-bar">
            <i style={{ width: `${confidence}%`, background: EMO_COLOR[main.key] }} />
          </div>
          {secondary.map((item) => {
            const pct = allScore > 0 ? Math.max(4, Math.round((item.score / allScore) * 100)) : 0
            return (
              <div key={item.key} style={{ fontSize: 12.5, color: '#7a8ca0', marginTop: 8 }}>
                <div style={{ marginBottom: 4 }}>
                  {item.label} {pct}%
                </div>
                <div className="ute-bar">
                  <i style={{ width: `${pct}%`, background: EMO_COLOR[item.key] }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </Card>
  )
}

function renderTokensCard(result: LyricsAnalysisResult) {
  return (
    <Card
      className="ute-card ute-out-card"
      title={
        <span>
          歌词分词结果<Tag className="ute-out-tip" color="gold">Mock</Tag>
        </span>
      }
    >
      {result.tokens.length > 0 ? (
        <div style={{ lineHeight: 2 }}>
          {result.tokens.map((token) => (
            <span key={`${token.surface}-${token.reading}`} className="ute-token">
              <span className="jp">{token.surface}</span>
              <span className="meta">
                {token.reading} · {token.pos}
              </span>
            </span>
          ))}
        </div>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<span className="ute-empty-tip">暂无分词结果</span>} />
      )}
    </Card>
  )
}

function renderTokenDetailCard(result: LyricsAnalysisResult) {
  return (
    <Card
      className="ute-card ute-out-card"
      title={
        <span>
          对分词的解析<Tag className="ute-out-tip" color="gold">Mock</Tag>
        </span>
      }
    >
      {result.tokenAnalyses.length > 0 ? (
        result.tokenAnalyses.map((item) => (
          <div key={`${item.surface}-${item.reading}`} style={{ marginBottom: 10 }}>
            <div className="ute-grammar-line">
              <span className="idx">·</span>
              <span>
                <b>{item.surface}</b>（{item.reading}）：{item.pos} · {item.meaning}
              </span>
            </div>
            <div style={{ color: '#8fa3b8', fontSize: 12.5, lineHeight: 1.7, paddingLeft: 16 }}>{item.note}</div>
          </div>
        ))
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<span className="ute-empty-tip">暂无解析结果</span>} />
      )}
    </Card>
  )
}

function renderGrammarCard(result: LyricsAnalysisResult) {
  return (
    <Card
      className="ute-card ute-out-card"
      title={
        <span>
          歌词语法解析<Tag className="ute-out-tip" color="gold">Mock</Tag>
        </span>
      }
    >
      {result.grammar.map((item, index) => (
        <div key={`${item.pattern}-${index}`} className="ute-grammar-line">
          <span className="idx">{index + 1}.</span>
          <span>
            <b>{item.pattern}</b> {item.explanation}
          </span>
        </div>
      ))}
    </Card>
  )
}

export default function App() {
  const [page, setPage] = useState<PageKey>('home')
  const [lyrics, setLyrics] = useState('')
  const [audioName, setAudioName] = useState('')
  const [result, setResult] = useState<LyricsAnalysisResult | null>(null)
  const [analyzing, setAnalyzing] = useState(false)

  const go = (key: PageKey) => {
    setPage(key)
  }

  const handleAnalyze = async () => {
    if (analyzing) return
    if (!lyrics.trim()) {
      setResult(null)
      return
    }
    setAnalyzing(true)
    try {
      const res = await analyzeLyrics({ lyric: lyrics, audio: audioName || null })
      setResult(res)
    } catch {
      setResult(null)
    } finally {
      setAnalyzing(false)
    }
  }

  const renderHome = () => (
    <div className="ute-home">
      <div className="ute-hero-deco" aria-hidden="true">
        <span className="note n1">♪</span>
        <span className="note n2">♬</span>
        <span className="note n3">♩</span>
        <span className="note n4">♫</span>
      </div>
      <div className="ute-home-badge u-anim-top u-d1">
        <span className="dot" />
        Utaer · 日语音调分析
      </div>
      <h1 className="ute-home-title u-anim-top u-d2">Utaer</h1>
      <div className="ute-home-slogan u-anim-top u-d3">
        基于 <span className="blue">UniDic 权威词典</span> 的
        <br />
        <span className="gold">日语音调可视化</span>学习与歌唱分析工具
      </div>
      <div className="ute-home-cta u-anim-bottom u-d4">
        <Button className="ute-cta" type="primary" size="large" icon={<PlayCircleOutlined />} onClick={() => go('lyrics')}>
          开始使用
        </Button>
        <div className="ute-home-hint">进入歌词声调分析 · 其余功能当前为占位演示</div>
      </div>
    </div>
  )
    const renderLyrics = () => {
    return (
      <div>
        <div className="ute-sec-head u-anim-top u-d1">
          <Typography.Title level={2} style={{ marginBottom: 0, color: '#274b6d' }}>
            歌词声调分析
          </Typography.Title>
          <div className="ute-sec-desc">
            输入日语歌词并选择演唱音频（可选），点击「开始分析」后由 Mock 服务输出：歌词、声调对比折线图、情感分析、歌词分词结果、分词解析与歌词语法解析。
          </div>
        </div>

        <Card className="ute-card ute-panel">
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <div>
              <Flex justify="space-between" align="center" style={{ marginBottom: 8 }}>
                <Typography.Text strong style={{ color: '#3c5368' }}>
                  <FileTextOutlined style={{ color: '#4e9cd9', marginRight: 8 }} />
                  歌词文本（日语）
                </Typography.Text>
                <Button
                  type="link"
                  size="small"
                  onClick={() => {
                    setLyrics(SAMPLE_LYRIC)
                    setResult(null)
                  }}
                >
                  填入示例歌词
                </Button>
              </Flex>
              <Input.TextArea
                rows={6}
                value={lyrics}
                onChange={(e) => {
                  setLyrics(e.target.value)
                  setResult(null)
                }}
                placeholder={'在此粘贴日语歌词…\n例如：晴れた空の下で 君と笑い合う'}
              />
            </div>

            <div>
              <Typography.Text strong style={{ color: '#3c5368' }}>
                <AudioOutlined style={{ color: '#4e9cd9', marginRight: 8 }} />
                演唱音频（可选）
              </Typography.Text>
              <div style={{ marginTop: 8 }}>
                <Upload
                  accept="audio/*"
                  maxCount={1}
                  beforeUpload={() => false}
                  showUploadList={false}
                  onChange={(info) => {
                    const name = info.fileList[0]?.name
                    setAudioName(name ?? '')
                    setResult(null)
                  }}
                >
                  <Button icon={<UploadOutlined />}>选择音频文件</Button>
                </Upload>
                {audioName ? (
                  <span className="ute-file-hint">已选择：{audioName}（Mock：暂不处理音频内容）</span>
                ) : (
                  <span className="ute-file-hint">音频可选；Mock 分析仅依据歌词文本生成</span>
                )}
              </div>
            </div>

            <div className="ute-analyze-action">
              <Button
                className="ute-cta"
                type="primary"
                size="large"
                icon={<PlayCircleOutlined />}
                loading={analyzing}
                onClick={handleAnalyze}
              >
                {analyzing ? '分析中…' : '开始分析（Mock）'}
              </Button>
            </div>
          </Space>
        </Card>

        {result ? (
          <div className="ute-out-grid u-anim-top u-d1">
            <Card className="ute-card ute-out-card ute-out-full" title="歌词输出">
              {result.lyric ? (
                <div className="ute-lyric-text">{result.lyric}</div>
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<span className="ute-empty-tip">尚未输入歌词</span>} />
              )}
            </Card>
            {renderChartCard(result)}
            {renderEmotionCard(result)}
            {renderTokensCard(result)}
            {renderTokenDetailCard(result)}
            {renderGrammarCard(result)}
          </div>
        ) : (
          <Card className="ute-card ute-panel">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span className="ute-empty-tip">
                  输入歌词（可选音频）后点击「开始分析（Mock）」，此处将展示 Mock 生成的六类输出结果
                </span>
              }
            />
          </Card>
        )}
      </div>
    )
  }

  const renderAbout = () => (
    <div>
      <div className="ute-sec-head u-anim-top u-d1">
        <Typography.Title level={2} style={{ marginBottom: 0, color: '#274b6d' }}>
          关于 Utaer
        </Typography.Title>
        <div className="ute-sec-desc">{SLOGAN}。当前页面为前端演示阶段，除页面跳转外的其余功能均为占位。</div>
      </div>

      <Card className="ute-card">
        <div className="ute-about-block">
          <Typography.Title level={4} style={{ color: '#274b6d' }}>
            项目定位
          </Typography.Title>
          <Typography.Paragraph style={{ color: '#4a5f72', lineHeight: 2, marginBottom: 0 }}>
            本项目是一个面向日语歌曲爱好者的“声调 + 情感”分析工具：以 UniDic 的词性、声调标注为权威事实底座，
            通过歌词分词、声调对比与情感分析，帮助用户理解日语歌词的高低声调与情感表达。
          </Typography.Paragraph>
        </div>

        <div className="ute-about-block">
          <Typography.Title level={4} style={{ color: '#274b6d' }}>
            功能规划（当前均为占位）
          </Typography.Title>
          <div className="ute-feature-grid">
            {[
              { icon: <TagsOutlined />, title: '歌词分词', text: '基于 UniDic 的形态素解析，展示逐词词性与读音。' },
              { icon: <LineChartOutlined />, title: '声调对比折线图', text: '将词典调型与演唱音高的走势放在一起对照。' },
              { icon: <SmileOutlined />, title: '情感分析', text: '识别歌声与歌词传达的整体情感倾向。' },
              { icon: <BranchesOutlined />, title: '语法解析', text: '对歌词中的句式与语法点给出通俗解释。' },
            ].map((f) => (
              <div key={f.title} className="ute-feature">
                <h4>
                  {f.icon} {f.title}
                </h4>
                <p>{f.text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="ute-about-block">
          <Typography.Title level={4} style={{ color: '#274b6d' }}>
            开发状态
          </Typography.Title>
          <Typography.Paragraph style={{ color: '#4a5f72', lineHeight: 2, marginBottom: 0 }}>
            前端演示版本：已搭建首页、歌词声调分析与关于三个页面，并完成页面间的导航跳转；
            歌词分析、音频上传、图表与情感分析等功能将在后续接入真实算法与接口。
          </Typography.Paragraph>
        </div>
      </Card>
    </div>
  )

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#4e9cd9',
          colorInfo: '#4e9cd9',
          colorLink: '#2e6fa8',
          colorText: '#2c4259',
          colorTextSecondary: '#7a8ca0',
          colorBorder: '#d4e7f6',
          colorBorderSecondary: '#e6f1fa',
          colorBgLayout: '#eef6fd',
          borderRadius: 10,
          fontFamily: "'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif",
        },
      }}
    >
      <style>{CSS}</style>
      <div className="ute-app">
        <div className="ute-bg" />
        <header className="ute-header">
          <div className="ute-brand" onClick={() => go('home')}>
            <span className="ute-brand-logo">
              <SoundOutlined />
            </span>
            <span className="ute-brand-name">
              Utaer
            </span>
          </div>
          <div className="ute-nav">
            <Menu
              mode="horizontal"
              selectedKeys={[page]}
              items={menuItems}
              onClick={({ key }) => go(key as PageKey)}
              style={{ minWidth: 330, fontSize: 15 }}
            />
          </div>
          <div className="ute-header-right" />
        </header>

        <main className="ute-main">
          {page === 'home' ? renderHome() : page === 'lyrics' ? renderLyrics() : renderAbout()}
        </main>

        <Divider style={{ margin: '0 auto', maxWidth: 1120 }} />
        <div className="ute-footer-note">
          Utaer· UniDic 日语音调可视化学习与歌唱分析 · 前端占位演示
        </div>
      </div>
    </ConfigProvider>
  )
}