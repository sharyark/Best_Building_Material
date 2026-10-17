import { Card, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export type Tone = 'blue' | 'green' | 'amber' | 'teal' | 'purple' | 'red' | 'slate'

const TONES: Record<Tone, { bg: string; fg: string }> = {
  blue: { bg: '#e6f0fa', fg: '#1f4e79' },
  green: { bg: '#e6f6ec', fg: '#2f8f4e' },
  amber: { bg: '#fdf1dd', fg: '#b7791f' },
  teal: { bg: '#e0f4f5', fg: '#23858f' },
  purple: { bg: '#efe9fa', fg: '#6b4fb3' },
  red: { bg: '#fdeaea', fg: '#c0392b' },
  slate: { bg: '#eef1f4', fg: '#56606b' },
}

/** Dashboard tile: tinted icon badge, small label, one big number. Moderate colour on purpose. */
export function StatCard({ title, value, icon, tone = 'blue', to, valueColor }: { title: string; value: ReactNode; icon: ReactNode; tone?: Tone; to?: string; valueColor?: string }) {
  const t = TONES[tone]
  const card = (
    <Card
      size="small"
      hoverable={Boolean(to)}
      style={{ borderRadius: 12, borderColor: '#edf0f3', boxShadow: '0 1px 3px rgba(16,38,59,.06)', height: '100%' }}
      styles={{ body: { display: 'flex', gap: 12, alignItems: 'center', padding: 14 } }}
    >
      <div style={{ width: 42, height: 42, borderRadius: 10, background: t.bg, color: t.fg, display: 'grid', placeItems: 'center', fontSize: 20, flex: 'none' }}>
        {icon}
      </div>
      <div style={{ minWidth: 0 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12.5, display: 'block', lineHeight: 1.3 }}>
          {title}
        </Typography.Text>
        <div style={{ fontSize: 19, fontWeight: 600, color: valueColor ?? '#17283a', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      </div>
    </Card>
  )
  return to ? <Link to={to}>{card}</Link> : card
}
