import { CrownOutlined, LockOutlined, SolutionOutlined, UserOutlined } from '@ant-design/icons'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { apiError } from '@/api/client'
import { useAuth } from '@/app/AuthContext'
import { Field } from '@/components/Field'
import { HeroArt } from '@/components/HeroArt'
import { t } from '@/i18n'
import { loginSchema } from '@/lib/schemas'

export type Portal = 'admin' | 'accountant'
export const PORTAL_KEY = 'hisaab.portal'

export function lastPortal(): Portal | null {
  try {
    const v = localStorage.getItem(PORTAL_KEY)
    return v === 'admin' || v === 'accountant' ? v : null
  } catch {
    return null
  }
}

const COPY: Record<Portal, { title: string; subtitle: string; accent: string; other: { to: string; label: string }; icon: React.ReactNode }> = {
  admin: {
    title: 'Owner sign-in',
    subtitle: 'Reports, profit, corrections and settings',
    accent: '#8a1f2d',
    other: { to: '/accountant/login', label: 'Munshi / accountant? Sign in here' },
    icon: <CrownOutlined />,
  },
  accountant: {
    title: 'Munshi sign-in',
    subtitle: 'Daily entries: challans, payments, diesel, wages',
    accent: '#1f4e79',
    other: { to: '/admin/login', label: 'Owner? Sign in here' },
    icon: <SolutionOutlined />,
  },
}

const shell = { minHeight: '100vh', display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', background: '#f0f2f5' } as const

function ArtPanel() {
  return (
    <div className="login-art" style={{ position: 'relative', overflow: 'hidden', color: '#fff', padding: 40, background: 'linear-gradient(135deg, #17406a 0%, #1f4e79 50%, #2b7a8c 100%)', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      <HeroArt style={{ maxWidth: '100%', width: '100%', height: 'auto', opacity: 0.95 }} />
      <Typography.Title style={{ color: '#fff', margin: '0 0 8px' }}>{t('app.name')}</Typography.Title>
      <Typography.Paragraph style={{ color: 'rgba(255,255,255,.85)', fontSize: 16, maxWidth: 380 }}>
        Sand, cement, blocks and gravel: every trip, payment and wage in one place, with balances that always match.
      </Typography.Paragraph>
    </div>
  )
}

/** /login: pick which door to use. */
export function LoginChooser() {
  const { user } = useAuth()
  if (user) return <Navigate to="/" replace />
  return (
    <div style={shell} className="login-grid">
      <ArtPanel />
      <div style={{ display: 'grid', placeItems: 'center', padding: 16 }}>
        <div style={{ width: '100%', maxWidth: 400 }}>
          <Typography.Title level={3} style={{ textAlign: 'center' }}>Who is signing in?</Typography.Title>
          {(['admin', 'accountant'] as Portal[]).map((p) => (
            <Link key={p} to={`/${p}/login`}>
              <Card hoverable style={{ marginBottom: 12, borderRadius: 12, borderLeft: `5px solid ${COPY[p].accent}` }}>
                <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                  <div style={{ fontSize: 26, color: COPY[p].accent }}>{COPY[p].icon}</div>
                  <div>
                    <Typography.Text strong style={{ fontSize: 16 }}>{p === 'admin' ? 'Owner (admin)' : 'Munshi (accountant)'}</Typography.Text>
                    <br />
                    <Typography.Text type="secondary">{COPY[p].subtitle}</Typography.Text>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

/** /admin/login and /accountant/login. The server also refuses an account on the wrong page. */
export default function LoginPage({ portal }: { portal: Portal }) {
  const { user, login, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { control, handleSubmit } = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema), defaultValues: { phone: '', password: '' } })
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const copy = COPY[portal]

  // Already signed in as the other role on this page: don't silently bounce them.
  if (user && user.role === portal) return <Navigate to={from} replace />

  return (
    <div style={shell} className="login-grid">
      <ArtPanel />
      <div style={{ display: 'grid', placeItems: 'center', padding: 16 }}>
        <Card style={{ width: '100%', maxWidth: 400, borderRadius: 12, borderTop: `5px solid ${copy.accent}`, boxShadow: '0 6px 24px rgba(16,38,59,.08)' }}>
          <div style={{ textAlign: 'center', fontSize: 30, color: copy.accent }}>{copy.icon}</div>
          <Typography.Title level={3} style={{ textAlign: 'center', margin: '4px 0' }}>{copy.title}</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ textAlign: 'center' }}>{copy.subtitle}</Typography.Paragraph>
          {user && user.role !== portal && (
            <Alert type="info" showIcon style={{ marginBottom: 12 }} message={`You are signed in as ${user.name} (${user.role}).`} action={<Button size="small" onClick={() => void logout()}>Sign out</Button>} />
          )}
          {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} />}
          <Form
            layout="vertical"
            onFinish={handleSubmit(async (v) => {
              setBusy(true)
              setError(null)
              try {
                await login(v.phone, v.password, portal)
                try {
                  localStorage.setItem(PORTAL_KEY, portal)
                } catch {
                  /* private mode: the redirect just won't remember */
                }
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
            <Button type="primary" htmlType="submit" block size="large" loading={busy} style={{ background: copy.accent, borderColor: copy.accent }}>Sign in</Button>
          </Form>
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Link to={copy.other.to}>{copy.other.label}</Link>
          </div>
        </Card>
      </div>
    </div>
  )
}
