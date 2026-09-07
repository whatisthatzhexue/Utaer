/**
 * 前端音频处理工具：
 * - 低通滤波 + 降采样到 16kHz，编码为 16bit PCM WAV（录音采集链路的纯前端实现）
 * - 音频时长 / 大小 / 格式化辅助
 */

/** 生成 16bit PCM 的 WAV 文件头 + 数据 */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const writeString = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i))
  }
  writeString(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    let s = Math.max(-1, Math.min(1, samples[i]))
    s = s < 0 ? s * 0x8000 : s * 0x7fff
    view.setInt16(offset, s, true)
    offset += 2
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

/** 解码 AudioContext 的兼容创建 */
function getAudioContextCtor(): typeof AudioContext {
  return globalThis.AudioContext ?? (globalThis as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
}

/**
 * 把一段音频 Blob（浏览器可解码格式）低通滤波 + 降采样为 16kHz 的 WAV。
 * 若解码失败（如个别浏览器不支持该容器），返回原始 Blob。
 */
export async function resampleTo16kWav(source: Blob): Promise<Blob> {
  const Ctor = getAudioContextCtor()
  if (!Ctor) return source
  try {
    const arrayBuffer = await source.arrayBuffer()
    const ctx = new Ctor({ sampleRate: 16000 })
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0))
    const length = audioBuffer.length
    const offline = new OfflineAudioContext(1, length, 16000)
    const filter = offline.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.value = 7000 // 16kHz 采样率下保留语音主要频段
    const src = offline.createBufferSource()
    src.buffer = audioBuffer
    src.connect(filter)
    filter.connect(offline.destination)
    src.start()
    const rendered = await offline.startRendering()
    await ctx.close()
    return encodeWav(rendered.getChannelData(0), 16000)
  } catch {
    return source
  }
}

/** 读取音频文件时长（秒） */
export function getAudioDuration(file: File | Blob): Promise<number> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const audio = new Audio()
    audio.preload = 'metadata'
    audio.onloadedmetadata = () => {
      const d = Number.isFinite(audio.duration) ? audio.duration : 0
      URL.revokeObjectURL(url)
      resolve(d)
    }
    audio.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(0)
    }
    audio.src = url
  })
}

/** 格式化字节大小 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

/** 格式化时长 mm:ss */
export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}