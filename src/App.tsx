import { useEffect, useRef, useState } from 'react'
import { analyzeLyrics } from './api/lyricsApi'
import { getCurrentUser, signIn, signUp, signOut as apiSignOut } from './api/authApi'
import { getAudioDuration, resampleTo16kWav } from './utils/audio'
import type { LyricsAnalysisResult, PitchSeries, UserInfo } from './types'

type Page = 'home' | 'lyrics' | 'about'

const CSS = `
  *{box-sizing:border-box}
  html,body,#root{margin:0;padding:0}
  #root{width:100%;max-width:100%;min-height:100vh;text-align:left;display:block;background:#fff}
  body{background:#fff;font-family:"PingFang SC","Microsoft YaHei","Segoe UI",sans-serif;color:#17181B;-webkit-font-smoothing:antialiased}
  .topbar{position:sticky;top:0;z-index:50;background:#fff;border-bottom:1px solid #E8E4DC}
  .in{max-width:1040px;margin:0 auto;padding:0 30px}
  .topbar .in{display:flex;align-items:center;justify-content:space-between;height:72px;gap:16px}
  .brand{display:flex;align-items:center;gap:12px;cursor:pointer;user-select:none}
  .brand img{height:26px;width:auto;display:block}
  .brand-name{font-size:22px;font-weight:900;letter-spacing:5px;text-transform:uppercase}
  .brand-name em{font-style:normal;color:#F47B20}
  .nav{display:flex}
  .nav a{position:relative;color:#7D7D78;font-size:15px;font-weight:700;letter-spacing:2px;padding:12px 14px;cursor:pointer;text-decoration:none}
  .nav a:hover{color:#17181B}
  .nav a.on{color:#F47B20}
  .nav a.on::after{content:"";position:absolute;left:14px;right:14px;bottom:5px;height:2px;background:#F47B20}
  .auth{display:flex;align-items:center;gap:16px}
  .btn-a{background:#F47B20;border:0;color:#fff;font-size:14px;font-weight:800;letter-spacing:2px;padding:10px 20px;cursor:pointer}
  .btn-a:hover{background:#17181B}
  .link{background:none;border:0;border-bottom:1px solid #E8E4DC;color:#7D7D78;font-size:14px;font-weight:800;letter-spacing:2px;padding:6px 0;cursor:pointer}
  .link:hover{color:#17181B;border-color:#17181B}
  .chip{display:flex;align-items:center;gap:10px;font-size:14px;font-weight:800}
  .chip i{width:26px;height:26px;border-radius:50%;background:#17181B;color:#fff;display:grid;place-items:center;font-size:12px;font-style:normal}
  .page{display:none}
  .page.on{display:block;animation:in .4s ease both}
  @keyframes in{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
  .hero{min-height:70vh;display:flex;flex-direction:column;justify-content:center;padding:96px 0 40px}
  .lock{display:flex;align-items:center;gap:clamp(12px,2vw,26px);flex-wrap:wrap}
  .hero-logo{width:clamp(110px,15vw,180px);height:auto;animation:li .9s cubic-bezier(.2,.8,.25,1) .2s both}
  @keyframes li{0%{opacity:0;transform:translateX(-24px) scale(.82) rotate(-6deg)}60%{opacity:1;transform:translateX(6px) scale(1.03)}100%{opacity:1;transform:none}}
  h1.big{font-size:clamp(58px,12vw,146px);font-weight:900;line-height:.98;letter-spacing:-.02em;margin:0;color:#17181B}
  h1.big .o{color:#F47B20}
  .hero p{margin-top:34px;font-size:clamp(17px,2.2vw,24px);color:#7D7D78;line-height:2;max-width:820px}
  .hero p b{color:#17181B}
  .start{background:none;border:0;color:#17181B;font-size:22px;font-weight:900;letter-spacing:3px;padding:6px 0;margin-top:60px;cursor:pointer;align-self:flex-start}
  .start:hover{color:#F47B20}
  @keyframes upIn{from{opacity:0;transform:translateY(-14px)}to{opacity:1;transform:none}}
  @keyframes dnIn{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
  .u-top{animation:upIn .7s cubic-bezier(.2,.8,.25,1) both}
  .u-bot{animation:dnIn .7s cubic-bezier(.2,.8,.25,1) both}
  .d1{animation-delay:.1s}.d2{animation-delay:.25s}.d3{animation-delay:.45s}
  section.block{padding:30px 0 140px}
  h2.pg{font-size:clamp(28px,4.4vw,48px);font-weight:900;margin:0 0 10px}
  .note{color:#7D7D78;font-size:15px;margin-bottom:54px}
  .card{display:grid;grid-template-columns:70px 1fr;gap:6px 22px;align-items:baseline;padding:22px 2px;border-bottom:1px solid #E8E4DC}
  .card .no{color:#F47B20;font-weight:900;font-size:14px}
  .card .t{font-size:18px;font-weight:900}
  .card .d{grid-column:2;font-size:14px;color:#7D7D78;line-height:1.8}
  .lyr{padding:70px 0 120px}
  .zone{display:flex;flex-direction:column;align-items:center;gap:18px;padding:40px 0 0}
  .rec{position:relative;width:128px;height:128px;border-radius:50%;border:0;background:#E8653A;color:#fff;font:900 13px/1.2 sans-serif;letter-spacing:2px;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px}
  .rec:hover{background:#CE5230}
  .rec .dot{width:16px;height:16px;border-radius:50%;background:#fff}
  .rec.on{background:#C62828}
  .rec.on .dot{border-radius:3px}
  .rec.pulse::after{content:"";position:absolute;inset:-12px;border:2px solid #F47B20;border-radius:50%;animation:ring 1.3s ease-out infinite}
  @keyframes ring{0%{transform:scale(.82);opacity:.85}100%{transform:scale(1.22);opacity:0}}
  .zone .tip{color:#7D7D78;font-size:14px;min-height:20px}
  .wave{display:flex;align-items:center;gap:2.5px;height:70px;width:100%;max-width:760px}
  .wave i{flex:1;background:#17181B;min-height:6px}
  .wave.play i{background:#F47B20}
  .row2{display:flex;gap:16px;flex-wrap:wrap;align-items:center;max-width:760px;width:100%}
  .seek{flex:1;min-width:200px;accent-color:#17181B}
  textarea{width:100%;border:0;border-bottom:1px solid #E8E4DC;background:transparent;font:17px/2.1 inherit;color:#17181B;padding:10px 2px;outline:none;resize:vertical;min-height:130px}
  textarea:focus{border-bottom:2px solid #F47B20}
  textarea::placeholder{color:#BCB4A7}
  .lbl{font-size:12px;font-weight:800;letter-spacing:3px;color:#7D7D78;text-transform:uppercase;display:block;margin-bottom:12px;margin-top:70px}
  .act{background:none;border:0;border-bottom:1px solid #E8E4DC;color:#7D7D78;font-size:14px;font-weight:800;letter-spacing:2px;padding:6px 0;cursor:pointer}
  .act:hover{color:#F47B20;border-color:#F47B20}
  .go{background:none;border:0;color:#17181B;font-size:20px;font-weight:900;letter-spacing:3px;padding:6px 0;margin-top:46px;cursor:pointer}
  .go:hover{color:#F47B20}
  .results{margin-top:90px}
  .res{padding:34px 0;border-bottom:1px solid #E8E4DC}
  .res h3{font-size:19px;font-weight:900;margin:0 0 8px}
  .res .rn{font-size:13px;color:#7D7D78;margin-bottom:28px}
  .emo{font-size:52px;font-weight:900;color:#F47B20}
  .emo2{font-size:16px;font-weight:800;margin-left:18px}
  .tok{display:inline-block;font-size:17px;font-weight:800;border-bottom:1px solid #F47B20;padding:2px 8px;margin:4px 8px 4px 0}
  .gr{list-style:none;margin:0;padding:0}
  .gr li{font-size:15px;line-height:2.3;color:#7D7D78}
  .gr li b{color:#17181B}
  footer{border-top:1px solid #E8E4DC;padding:28px 0;color:#7D7D78;font-size:13px}
  .mask{position:fixed;inset:0;background:rgba(20,20,24,.4);display:flex;align-items:center;justify-content:center;z-index:200}
  .box{background:#fff;width:min(400px,92vw);padding:30px;border-top:4px solid #F47B20}
  .box h3{margin:0 0 18px;font-size:22px;font-weight:900}
  .fld{display:block;margin-bottom:14px}
  .fld span{display:block;font-size:12px;font-weight:800;letter-spacing:2px;color:#7D7D78;margin-bottom:6px}
  .fld input{width:100%;border:0;border-bottom:1px solid #E8E4DC;padding:8px 2px;font-size:15px;outline:none;background:none}
  .fld input:focus{border-bottom:2px solid #F47B20}
  .err{color:#C62828;font-size:13px;min-height:16px}
  .submit{width:100%;background:#17181B;color:#fff;border:0;font-size:15px;font-weight:900;letter-spacing:3px;padding:14px;cursor:pointer}
  .submit:hover{background:#F47B20}
  .sw{text-align:center;margin-top:14px}
  @media (max-width:760px){.in{padding:0 18px}.nav a{font-size:14px;padding:8px 10px}.hero{padding:60px 0 30px}.card{grid-template-columns:1fr}.card .d{grid-column:1}}
`

const SAMPLE = '晴れた空の下で 君と笑い合う\n夢を追いかけて 走り出す今日\n幸せのメロディ 響け もっと高く\nこの歌が 君に届くまで'

function smoothPath(pts: Array<[number, number]>): string {
  if (pts.length < 2) return ''
  let d = 'M' + pts[0][0] + ',' + pts[0][1]
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(i - 1, 0)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(i + 2, pts.length - 1)]
    const c1x = p1[0] + (p2[0] - p0[0]) / 6
    const c1y = p1[1] + (p2[1] - p0[1]) / 6
    const c2x = p2[0] - (p3[0] - p1[0]) / 6
    const c2y = p2[1] - (p3[1] - p1[1]) / 6
    d += ' C' + c1x.toFixed(1) + ',' + c1y.toFixed(1) + ' ' + c2x.toFixed(1) + ',' + c2y.toFixed(1) + ' ' + p2[0] + ',' + p2[1]
  }
  return d
}

function fmt(s: number): string {
  if (!isFinite(s)) s = 0
  const m = Math.floor(s / 60)
  const x = Math.floor(s % 60)
  return (m < 10 ? '0' + m : m) + ':' + (x < 10 ? '0' + x : x)
}

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const [user, setUser] = useState<UserInfo | null>(null)
  const [auth, setAuth] = useState<null | 'login' | 'register'>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [pass, setPass] = useState('')
  const [err, setErr] = useState('')
  const [lyric, setLyric] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<LyricsAnalysisResult | null>(null)
  const [recording, setRecording] = useState(false)
  const [secs, setSecs] = useState(0)
  const [fileName, setFileName] = useState('')
  const [tip, setTip] = useState('录一段，听自己的声调')
  const [audioUrl, setAudioUrl] = useState('')
  const [playing, setPlaying] = useState(false)
  const [cur, setCur] = useState(0)
  const [dur, setDur] = useState(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const recRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)
  const waveRef = useRef<number | null>(null)
  const barsRef = useRef<HTMLDivElement | null>(null)
  const fileRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    void getCurrentUser().then(setUser).catch(() => setUser(null))
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
      if (waveRef.current) window.clearInterval(waveRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const go = (p: Page) => { setPage(p); window.scrollTo(0, 0) }

  const openAuth = (m: 'login' | 'register') => { setAuth(m); setErr('') }
  const submitAuth = () => {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setErr('请输入有效的邮箱地址'); return }
    if (pass.length < 6) { setErr('密码至少 6 位'); return }
    if (auth === 'register' && !name.trim()) { setErr('请输入昵称'); return }
    const p = auth === 'register' ? signUp({ name, email, password: pass }) : signIn({ email, password: pass })
    void p.then((u) => { setUser(u); setAuth(null); setName(''); setEmail(''); setPass('') }).catch((e) => setErr(e instanceof Error ? e.message : '失败'))
  }

  const stopWave = () => { if (waveRef.current) window.clearInterval(waveRef.current); waveRef.current = null; const w = barsRef.current; if (w) w.className = 'wave' }
  const startWave = () => {
    const w = barsRef.current
    if (w) w.className = 'wave play'
    if (waveRef.current) window.clearInterval(waveRef.current)
    waveRef.current = window.setInterval(() => {
      const t = audioRef.current && isFinite(audioRef.current.currentTime) ? audioRef.current.currentTime : 0
      const bars = barsRef.current
      if (!bars) return
      Array.from(bars.children).forEach((el, j) => {
        const h = 8 + Math.abs(Math.sin(j * 0.45 + t * 6)) * 58 + Math.random() * 8
        ;(el as HTMLElement).style.height = h.toFixed(0) + 'px'
      })
    }, 70)
  }

  const startRec = async () => {
    if (recording) { if (recRef.current && recRef.current.state !== 'inactive') recRef.current.stop(); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const rec = new MediaRecorder(stream)
      recRef.current = rec
      rec.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data) }
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        streamRef.current = null
        if (timerRef.current) { window.clearInterval(timerRef.current); timerRef.current = null }
        setRecording(false)
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
        void resampleTo16kWav(blob).then((wav) => {
          const file = new File([wav], 'recording.wav', { type: 'audio/wav' })
          setFileName('recording.wav')
          setTip('已录制 ' + fmt(secs) + ' · 已处理为 16kHz')
          const url = URL.createObjectURL(file)
          setAudioUrl(url)
          if (audioRef.current) {
            audioRef.current.src = url
            audioRef.current.load()
          }
        })
      }
      rec.start()
      setRecording(true)
      setSecs(0)
      setTip('录音中 00:00 · 3 分钟自动停止')
      timerRef.current = window.setInterval(() => {
        setSecs((s) => {
          const n = s + 1
          setTip('录音中 ' + fmt(n) + ' · 3 分钟自动停止')
          if (n >= 180 && recRef.current && recRef.current.state !== 'inactive') recRef.current.stop()
          return n
        })
      }, 1000)
    } catch {
      setTip('未获得麦克风权限')
    }
  }

  const onFile = async (file: File) => {
    if (file.size > 20 * 1024 * 1024) { setTip('文件超过 20MB，请压缩后上传'); return }
    const d = await getAudioDuration(file)
    if (d > 180) { setTip('音频超过 3 分钟'); return }
    const url = URL.createObjectURL(file)
    setFileName(file.name)
    setTip('已选择：' + file.name + ' · ' + (file.size / 1024 / 1024).toFixed(2) + ' MB')
    setAudioUrl(url)
    if (audioRef.current) { audioRef.current.src = url; audioRef.current.load() }
  }

  const togglePlay = () => {
    const a = audioRef.current
    if (!a || !a.getAttribute('src')) { setTip('请先录音或上传音频'); return }
    if (playing) { a.pause(); setPlaying(false); stopWave(); return }
    void a.play().then(() => { setPlaying(true); startWave() }).catch(() => setTip('播放失败'))
  }

  const analyze = async () => {
    setAnalyzing(true)
    try {
      const res = await analyzeLyrics({ lyric: lyric.trim() || SAMPLE })
      setResult(res)
    } finally {
      setAnalyzing(false)
    }
  }

  const waveBars = Array.from({ length: 60 }, (_, i) => i)
  const cards = [
    ['01', '录音 / 上传音频', '录下来，或直接上传；剩下的交给 Utaer。'],
    ['02', '声调曲线对照', '演唱音高与词典调型同屏对比，一目了然。'],
    ['03', '振假名 · 罗马音', '同一段歌词，三种读法。'],
    ['04', '情感标签', '识别歌唱情感，并说明判断的依据。'],
    ['05', '分词与解析', '逐词词性、读音与释义。'],
    ['06', '面向学习者', '初学者用得上，爱好者用得更顺。'],
  ]

  return (
    <div style={{ minHeight: '100vh' }}>
      <style>{CSS}</style>
      <header className="topbar">
        <div className="in" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 72, gap: 16 }}>
          <div className="brand" onClick={() => go('home')}>
            <img src="/logo.png" alt="Utaer" />
            <span className="brand-name">UTA<em>·</em>ER</span>
          </div>
          <nav className="nav">
            <a className={page === 'home' ? 'on' : ''} onClick={() => go('home')}>首页</a>
            <a className={page === 'lyrics' ? 'on' : ''} onClick={() => go('lyrics')}>歌词分析</a>
            <a className={page === 'about' ? 'on' : ''} onClick={() => go('about')}>关于</a>
          </nav>
          <div className="auth">
            {user ? (
              <>
                <span className="chip"><i>{user.name.slice(0, 1).toUpperCase()}</i>{user.name}</span>
                <button className="link" onClick={() => { void apiSignOut().then(() => setUser(null)) }}>退出</button>
              </>
            ) : (
              <>
                <button className="link" onClick={() => openAuth('login')}>登录</button>
                <button className="btn-a" onClick={() => openAuth('register')}>注册</button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="in">
        {page === 'home' && (
          <>
            <section className="hero">
              <div className="lock u-top d1">
                <img className="hero-logo" src="/logo.png" alt="Utaer" />
                <h1 className="big">UTA<span className="o">·</span>ER</h1>
              </div>
              <p className="u-top d2">一款面向日语学习者与歌曲爱好者的 Web 端轻量工具，聚焦日语演唱中的 <b>声调（アクセント）</b> 与 <b>情感表达</b>。</p>
              <button className="start u-bot d3" onClick={() => go('lyrics')}>开始使用 →</button>
            </section>
            <section className="block">
              <h2 className="pg">功能一览</h2>
              <p className="note">声调怎么读、唱得准不准——打开就能看到。</p>
              {cards.map((c) => (
                <div className="card" key={c[0]}><span className="no">{c[0]}</span><span className="t">{c[1]}</span><span className="d">{c[2]}</span></div>
              ))}
            </section>
          </>
        )}

        {page === 'lyrics' && (
          <section className="lyr">
            <div className="zone">
              <button className={'rec' + (recording ? ' on pulse' : '')} onClick={() => void startRec()}>
                <span className="dot" />
                {recording ? '停止录音' : '开始录音'}
              </button>
              <div className="tip">{tip}</div>
              <div className="row2">
                <button className="act" onClick={() => fileRef.current?.click()}>或 上传音频（mp3 优先）</button>
                <button className="act" onClick={() => setLyric(SAMPLE)}>填入示例歌词</button>
                <button className="act" onClick={togglePlay}>{playing ? '暂停' : '播放'}</button>
                <input ref={fileRef} type="file" accept="audio/*" hidden onChange={(e) => { const fl = e.target.files?.[0]; if (fl) void onFile(fl); e.target.value = '' }} />
              </div>
              {(audioUrl || fileName) && (
                <>
                  <div className="wave" ref={barsRef}>
                    {waveBars.map((i) => <i key={i} style={{ height: 12 }} />)}
                  </div>
                  <div className="row2">
                    <span>{fmt(cur)}</span>
                    <input className="seek" type="range" min={0} max={dur || 0} step={0.1} value={cur}
                      onChange={(e) => { const v = Number(e.target.value); setCur(v); const a = audioRef.current; if (a) a.currentTime = v }} />
                    <span>{fmt(dur)}</span>
                  </div>
                </>
              )}
              <audio ref={audioRef} hidden onLoadedMetadata={(e) => setDur(e.currentTarget.duration)} onTimeUpdate={(e) => setCur(e.currentTarget.currentTime)} onEnded={() => { setPlaying(false); stopWave() }} />
            </div>

            <span className="lbl">歌词（可选）</span>
            <textarea value={lyric} onChange={(e) => setLyric(e.target.value)} placeholder="输入歌词，查看声调、情感、分词与语法" />
            <button className="go" onClick={() => void analyze()} disabled={analyzing}>{analyzing ? '分析中…' : '开始分析 →'}</button>

            {result && (
              <div className="results">
                <div className="res">
                  <h3>声调对比</h3>
                  <p className="rn">黑线为用户演唱，橙线为词典调型（正确）</p>
                  <Chart result={result} />
                </div>
                <div className="res">
                  <h3>情感</h3>
                  <p className="rn">整体情感标签</p>
                  <span className="emo">{result.emotion.main.label}</span><span className="emo2">可信度 {result.emotion.confidence}%</span>
                </div>
                <div className="res">
                  <h3>分词</h3>
                  <p className="rn">逐词展示（振假名 · 罗马音后续可切换）</p>
                  {result.tokens.map((t, i) => <span className="tok" key={i}>{t.surface}</span>)}
                </div>
                <div className="res">
                  <h3>语法</h3>
                  <ul className="gr">{result.grammar.map((g, i) => <li key={i}><b>{g.pattern}</b> — {g.explanation}</li>)}</ul>
                </div>
              </div>
            )}
          </section>
        )}

        {page === 'about' && (
          <section className="block" style={{ maxWidth: 860 }}>
            <h2 className="pg">关于</h2>
            <p className="note">每一个读音与声调，都有依据。</p>
            <p style={{ color: '#7D7D78', lineHeight: 2.4, fontSize: 16 }}>Utaer 把“学术级”的日语语言与声学能力，放进一个轻量 Web 工具里。</p>
            <div>
              {[
                ['01', '语言引擎', '词性、读音与声调，来自权威词典 UniDic。'],
                ['02', '声学分析', '用 Praat 提取你的音高轨迹，与词典调型同屏对照。'],
                ['03', '情感识别', '识别歌唱情感，并说明判断的依据。'],
                ['04', '数据链路', 'Supabase 云端：分析任务与音频文件，安全存储与回传。'],
                ['05', '罗马音引擎', '内置罗马音引擎，处理好促音、长音与外来语。'],
                ['06', '声调规范', 'audio_accent.json：统一的声调数据结构。'],
              ].map((c) => <div className="card" key={c[0]}><span className="no">{c[0]}</span><span className="t">{c[1]}</span><span className="d">{c[2]}</span></div>)}
            </div>
          </section>
        )}
      </main>

      <footer>
        <div className="in">UTA·ER © 2026 · 开发中画面</div>
      </footer>

      {auth && (
        <div className="mask" onClick={() => setAuth(null)}>
          <div className="box" onClick={(e) => e.stopPropagation()}>
            <h3>{auth === 'register' ? '注册' : '登录'}</h3>
            {auth === 'register' && (
              <label className="fld"><span>昵称</span><input value={name} onChange={(e) => setName(e.target.value)} placeholder="你的昵称" /></label>
            )}
            <label className="fld"><span>邮箱</span><input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></label>
            <label className="fld"><span>密码</span><input type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="至少 6 位" /></label>
            <p className="err">{err}</p>
            <button className="submit" onClick={submitAuth}>{auth === 'register' ? '注册' : '登录'}</button>
            <div className="sw"><button className="link" onClick={() => setAuth(auth === 'register' ? 'login' : 'register')}>{auth === 'register' ? '已有账号？去登录' : '没有账号？注册一个'}</button></div>
          </div>
        </div>
      )}
    </div>
  )
}

function Chart({ result }: { result: LyricsAnalysisResult }) {
  const series: PitchSeries[] = result.pitchSeries
  const all = series.flatMap((s) => s.points.map((p) => p.value))
  const min = Math.min(...all)
  const max = Math.max(...all)
  const span = max - min || 1
  const pts = (s: PitchSeries): Array<[number, number]> =>
    s.points.map((p, i) => {
      const n = s.points.length
      const x = n <= 1 ? 480 : 60 + (i * 840) / (n - 1)
      const y = 210 - ((p.value - min) / span) * 150
      return [x, y]
    })
  return (
    <svg viewBox="0 0 960 260" style={{ width: '100%', height: 'auto' }} role="img" aria-label="声调对比折线图">
      {series.map((s) => <path key={s.name} d={smoothPath(pts(s))} fill="none" stroke={s.color} strokeWidth={3} strokeLinecap="round" />)}
    </svg>
  )
}
