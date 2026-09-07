import type { UserInfo } from '../types'

/**
 * 用户登录 / 注册的 Mock 实现
 * - 数据仅保存在 localStorage（前端演示用，不校验真实密码）
 * - 后端（Supabase Auth）就绪后，替换内部实现为 supabase.auth 调用，签名不变
 */

const SESSION_KEY = 'utear_session'

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

function readSession(): UserInfo | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as UserInfo) : null
  } catch {
    return null
  }
}

function saveSession(user: UserInfo): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(user))
}

function validateEmail(email: string): void {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new Error('请输入有效的邮箱地址')
  }
}

function validatePassword(password: string): void {
  if (password.length < 6) {
    throw new Error('密码至少 6 位')
  }
}

export interface Credentials {
  name?: string
  email: string
  password: string
}

/** 注册 */
export async function signUp(input: Credentials): Promise<UserInfo> {
  await wait(400)
  const email = input.email.trim()
  const name = (input.name ?? '').trim()
  validateEmail(email)
  validatePassword(input.password)
  if (!name) throw new Error('请输入昵称')
  const user: UserInfo = {
    id: `u_${Date.now().toString(36)}`,
    name,
    email,
    createdAt: Date.now(),
  }
  saveSession(user)
  return { ...user }
}

/** 登录 */
export async function signIn(input: Credentials): Promise<UserInfo> {
  await wait(400)
  const email = input.email.trim()
  validateEmail(email)
  validatePassword(input.password)
  const current = readSession()
  const user: UserInfo = current ?? {
    id: `u_${Date.now().toString(36)}`,
    name: email.split('@')[0] || '用户',
    email,
    createdAt: Date.now(),
  }
  saveSession(user)
  return { ...user }
}

/** 退出登录 */
export async function signOut(): Promise<void> {
  await wait(120)
  localStorage.removeItem(SESSION_KEY)
}

/** 恢复会话（刷新后保持登录） */
export async function getCurrentUser(): Promise<UserInfo | null> {
  await wait(80)
  const user = readSession()
  return user ? { ...user } : null
}