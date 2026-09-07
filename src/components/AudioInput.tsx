import { useEffect, useRef, useState } from 'react'
import { Button, Space, Typography, Upload } from 'antd'
import { AudioOutlined, UploadOutlined } from '@ant-design/icons'
import { formatBytes, formatDuration, getAudioDuration, resampleTo16kWav } from '../utils/audio'

interface AudioInputProps {
  value?: File | null
  onChange?: (file: File | null) => void
}

/** 录音采集 + 文件上传 + 播放（纯前端；分析仍需后端/Mock） */
export default function AudioInput({ value, onChange }: AudioInputProps) {
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [notice, setNotice] = useState('')
  const [playUrl, setPlayUrl] = useState('')
  const [processing, setProcessing] = useState(false)

  const mediaRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    if (!value) {
      setPlayUrl('')
      setNotice('')
    }
  }, [value])

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  const startRecording = async () => {
    setNotice('')
    chunksRef.current = []
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const recorder = new MediaRecorder(stream)
      mediaRef.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = async () => {
        streamRef.current?.getTracks().forEach((track) => track.stop())
        if (timerRef.current) window.clearInterval(timerRef.current)
        setRecording(false)
        setProcessing(true)
        const original = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        const wav = await resampleTo16kWav(original)
        const file = new File([wav], 'recording.wav', { type: 'audio/wav' })
        const url = URL.createObjectURL(file)
        setPlayUrl(url)
        setNotice(`已处理：低通滤波 + 16kHz 降采样（${formatBytes(file.size)}）`)
        onChange?.(file)
        setProcessing(false)
      }
      recorder.start()
      setRecording(true)
      setElapsed(0)
      timerRef.current = window.setInterval(() => {
        setElapsed((prev) => {
          if (prev + 1 >= 180) {
            stopRecording()
            return prev
          }
          return prev + 1
        })
      }, 1000)
    } catch {
      setNotice('无法访问麦克风：请在浏览器中允许录音权限')
    }
  }

  const stopRecording = () => {
    if (mediaRef.current && mediaRef.current.state !== 'inactive') {
      mediaRef.current.stop()
    }
  }

  const onFile = async (file: File) => {
    setNotice('')
    if (file.size > 20 * 1024 * 1024) {
      setNotice('文件超过 20MB，已触发压缩提示（前端压缩将在接入转码后生效）')
      onChange?.(null)
      return
    }
    const duration = await getAudioDuration(file)
    if (duration > 180) {
      setNotice('音频超过 3 分钟，请更换音频')
      onChange?.(null)
      return
    }
    setPlayUrl(URL.createObjectURL(file))
    setNotice(`已选择：${file.name}（${formatBytes(file.size)} · ${formatDuration(duration)}）`)
    onChange?.(file)
  }

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Space wrap>
        {recording ? (
          <Button danger type="primary" onClick={stopRecording}>
            停止录音 {formatDuration(elapsed)}
          </Button>
        ) : (
          <Button type="primary" icon={<AudioOutlined />} onClick={startRecording} loading={processing}>
            开始录音
          </Button>
        )}
        <Upload
          accept="audio/*"
          maxCount={1}
          beforeUpload={() => false}
          showUploadList={false}
          onChange={(info) => {
            const file = info.fileList[0]?.originFileObj as File | undefined
            if (file) void onFile(file)
          }}
        >
          <Button icon={<UploadOutlined />}>选择音频文件</Button>
        </Upload>
      </Space>
      {playUrl ? <audio controls src={playUrl} style={{ width: '100%', height: 38 }} /> : null}
      {notice ? (
        <Typography.Text type={notice.includes('无法') || notice.includes('超过') ? 'warning' : 'secondary'} style={{ fontSize: 13 }}>
          {notice}
        </Typography.Text>
      ) : (
        <Typography.Text type="secondary" style={{ fontSize: 13 }}>
          支持录音或上传音频（mp3 优先）；录音自动低通滤波并降采样到 16kHz；时长上限 3 分钟，大小上限 20MB。
        </Typography.Text>
      )}
    </Space>
  )
}