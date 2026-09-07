import { useState } from 'react'
import { Button, Form, Input, Modal, Typography } from 'antd'
import { LockOutlined, MailOutlined, UserOutlined } from '@ant-design/icons'
import { signIn, signUp } from '../api/authApi'
import type { UserInfo } from '../types'

interface AuthModalProps {
  open: boolean
  onClose: () => void
  onSuccess: (user: UserInfo) => void
}

interface FormValues {
  name?: string
  email: string
  password: string
}

/** 登录 / 注册（Mock） */
export default function AuthModal({ open, onClose, onSuccess }: AuthModalProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [form] = Form.useForm<FormValues>()

  const reset = () => {
    setError('')
    form.resetFields()
  }

  const submit = async (values: FormValues) => {
    setLoading(true)
    setError('')
    try {
      const user = mode === 'login' ? await signIn(values) : await signUp(values)
      onSuccess(user)
      reset()
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title={mode === 'login' ? '登录' : '注册'}
      open={open}
      onCancel={() => {
        reset()
        onClose()
      }}
      footer={null}
      width={400}
      centered
      destroyOnHidden
    >
      <Form<FormValues> form={form} layout="vertical" requiredMark={false} onFinish={submit} style={{ marginTop: 8 }}>
        {mode === 'register' ? (
          <Form.Item name="name" label="昵称" rules={[{ required: true, message: '请输入昵称' }]}>
            <Input prefix={<UserOutlined />} placeholder="你的昵称" autoComplete="nickname" />
          </Form.Item>
        ) : null}
        <Form.Item name="email" label="邮箱" rules={[{ required: true, message: '请输入邮箱' }]}>
          <Input prefix={<MailOutlined />} placeholder="you@example.com" autoComplete="email" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
          <Input.Password prefix={<LockOutlined />} placeholder="至少 6 位" autoComplete="current-password" />
        </Form.Item>

        {error ? (
          <Typography.Paragraph type="danger" style={{ marginBottom: 8 }}>
            {error}
          </Typography.Paragraph>
        ) : null}

        <Button type="primary" htmlType="submit" block loading={loading} style={{ marginTop: 4 }}>
          {mode === 'login' ? '登录' : '注册'}
        </Button>
      </Form>

      <div style={{ textAlign: 'center', marginTop: 14 }}>
        {mode === 'login' ? (
          <Button type="link" onClick={() => setMode('register')}>
            没有账号？注册一个
          </Button>
        ) : (
          <Button type="link" onClick={() => setMode('login')}>
            已有账号？去登录
          </Button>
        )}
      </div>
    </Modal>
  )
}