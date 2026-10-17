import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { apiError } from '@/api/client'
import { useAuth } from '@/app/AuthContext'
import { Field } from '@/components/Field'
import { HeroArt } from '@/components/HeroArt'
import { loginSchema } from '@/lib/schemas'
import { t } from '@/i18n'

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { control, handleSubmit } = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema), defaultValues: { phone: '', password: '' } })
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (user) return <Navigate to={from} replace />

  return (
    <div style={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', background: '#f0f2f5' }} className="login-grid">
      <div className="login-art" style={{ position: 'relative', overflow: 'hidden', color: '#fff', padding: 40, background: 'linear-gradient(135deg, #17406a 0%, #1f4e79 50%, #2b7a8c 100%)', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <HeroArt style={{ maxWidth: '100%', width: '100%', height: 'auto', opacity: 0.95 }} />
        <Typography.Title style={{ color: '#fff', margin: '0 0 8px' }}>{t('app.name')}</Typography.Title>
        <Typography.Paragraph style={{ color: 'rgba(255,255,255,.85)', fontSize: 16, maxWidth: 380 }}>
          Sand, cement, blocks and gravel: every trip, payment and wage in one place, with balances that always match.
        </Typography.Paragraph>
      </div>
      <div style={{ display: 'grid', placeItems: 'center', padding: 16 }}>
      <Card style={{ width: '100%', maxWidth: 400, borderRadius: 12, boxShadow: '0 6px 24px rgba(16,38,59,.08)' }}>
        <Typography.Title level={3} style={{ textAlign: 'center', marginTop: 0 }}>Welcome back</Typography.Title>
        <Typography.Paragraph type="secondary" style={{ textAlign: 'center' }}>Sign in to your account</Typography.Paragraph>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} />}
        <Form
          layout="vertical"
          onFinish={handleSubmit(async (v) => {
            setBusy(true)
            setError(null)
            try {
              await login(v.phone, v.password)
              navigate(from, { replace: true })
            } catch (e) {
              setError(apiError(e).message)
            } finally {
              setBusy(false)
            }
          })}
        >
          <Field control={control} name="phone" label="Phone / username">{(f) => <Input {...f} prefix={<UserOutlined />} autoFocus autoComplete="username" size="large" />}</Field>
          <Field control={control} name="password" label="Password">{(f) => <Input.Password {...f} prefix={<LockOutlined />} autoComplete="current-password" size="large" />}</Field>
          <Button type="primary" htmlType="submit" block size="large" loading={busy}>Sign in</Button>
        </Form>
      </Card>
      </div>
    </div>
  )
}
