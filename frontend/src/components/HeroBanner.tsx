import { Button, Space, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/app/AuthContext'
import { formatDate } from '@/lib/date'
import { HeroArt } from './HeroArt'

function greeting(): string {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export function HeroBanner({ date, trips }: { date?: string; trips?: number }) {
  const { user, can } = useAuth()
  const navigate = useNavigate()
  return (
    <div
      style={{
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 12,
        padding: '22px 24px',
        marginBottom: 16,
        color: '#fff',
        minHeight: 150,
        background: 'linear-gradient(120deg, #17406a 0%, #1f4e79 45%, #2b7a8c 100%)',
        boxShadow: '0 6px 18px rgba(31,78,121,.25)',
      }}
    >
      <HeroArt />
      <div style={{ position: 'relative', maxWidth: 560 }}>
        <Typography.Title level={3} style={{ color: '#fff', margin: 0 }}>
          {greeting()}, {user?.name}
        </Typography.Title>
        <Typography.Text style={{ color: 'rgba(255,255,255,.85)' }}>
          {date ? formatDate(date) : ''}
          {trips !== undefined && ` · ${trips} trip${trips === 1 ? '' : 's'} out of the yard today`}
        </Typography.Text>
        <div style={{ marginTop: 16 }}>
          <Space wrap>
            {can('challan.create') && (
              <Button type="primary" ghost style={{ background: '#fff', color: '#1f4e79', borderColor: '#fff', fontWeight: 600 }} onClick={() => navigate('/challans')}>
                New challan
              </Button>
            )}
            {can('payment.create') && (
              <Button ghost style={{ color: '#fff', borderColor: 'rgba(255,255,255,.7)' }} onClick={() => navigate('/payments')}>
                Receive payment
              </Button>
            )}
            {can('expense.create') && (
              <Button ghost style={{ color: '#fff', borderColor: 'rgba(255,255,255,.7)' }} onClick={() => navigate('/expenses')}>
                Diesel / expense
              </Button>
            )}
          </Space>
        </div>
      </div>
    </div>
  )
}
