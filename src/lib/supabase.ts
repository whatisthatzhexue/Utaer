import type { AnalysisTask, AnalysisTaskStatus } from '../types'

/**
 * Supabase 轻量客户端（不引入 @supabase/supabase-js，直接走 REST + Storage API）
 * 后端就绪后，只需在项目根目录 .env 中填入真实值即可：
 *   VITE_SUPABASE_URL
 *   VITE_SUPABASE_ANON_KEY
 */

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

export const supabaseConfig = {
  url: SUPABASE_URL ?? '',
  anonKey: SUPABASE_ANON_KEY ?? '',
  get isConfigured(): boolean {
    return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY && /^https?:\/\//.test(SUPABASE_URL))
  },
}

interface SupabaseOptions {
  signal?: AbortSignal
}

/** 通用 REST 请求（表/视图查询用） */
async function rest<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!supabaseConfig.isConfigured) {
    throw new Error('Supabase 未配置：请在 .env 中填写 VITE_SUPABASE_URL 与 VITE_SUPABASE_ANON_KEY')
  }
  const res = await fetch(`${supabaseConfig.url}/rest/v1/${path}`, {
    ...init,
    headers: {
      apikey: supabaseConfig.anonKey,
      Authorization: `Bearer ${supabaseConfig.anonKey}`,
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  if (!res.ok) {
    throw new Error(`Supabase REST 请求失败：${res.status} ${res.statusText}`)
  }
  return (await res.json()) as T
}

/** 查询分析任务（前端轮询用） */
export function fetchTask(taskId: string, options?: SupabaseOptions): Promise<AnalysisTask[]> {
  const url = `analysis_tasks?id=eq.${encodeURIComponent(taskId)}&select=*`
  return rest<AnalysisTask[]>(url, { signal: options?.signal })
}

/** 轮询任务直到离开 pending（completed / failed），或超时 */
export async function pollTask(
  taskId: string,
  options: { intervalMs?: number; timeoutMs?: number; onStatus?: (status: AnalysisTaskStatus) => void } = {},
): Promise<AnalysisTask> {
  const intervalMs = options.intervalMs ?? 1500
  const timeoutMs = options.timeoutMs ?? 120000
  const startedAt = Date.now()
  for (;;) {
    const tasks = await fetchTask(taskId)
    const task = tasks[0]
    if (!task) throw new Error(`未找到任务 ${taskId}`)
    options.onStatus?.(task.status)
    if (task.status !== 'pending') return task
    if (Date.now() - startedAt > timeoutMs) {
      throw new Error(`任务 ${taskId} 轮询超时`)
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}

/** 上传音频到 Supabase Storage（后端就绪后使用） */
export async function uploadAudio(bucket: string, storagePath: string, file: File | Blob): Promise<string> {
  if (!supabaseConfig.isConfigured) {
    throw new Error('Supabase 未配置')
  }
  const res = await fetch(
    `${supabaseConfig.url}/storage/v1/object/${encodeURIComponent(bucket)}/${encodeURIComponent(storagePath)}`,
    {
      method: 'POST',
      headers: {
        apikey: supabaseConfig.anonKey,
        Authorization: `Bearer ${supabaseConfig.anonKey}`,
        'Content-Type': file.type || 'application/octet-stream',
      },
      body: file,
    },
  )
  if (!res.ok) {
    throw new Error(`Storage 上传失败：${res.status} ${res.statusText}`)
  }
  return storagePath
}