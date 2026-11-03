import { CarOutlined, WalletOutlined } from '@ant-design/icons'
import { Card, Col, Row, Typography } from 'antd'
import type { ReactNode } from 'react'
import { formatCurrency } from '@/lib/format'

type Meta = Record<string, unknown>

const num = (v: unknown) => Number(v ?? 0)

/** Positive = we owe the worker; negative = they owe us (advance more than earned). */
function Due({ value }: { value: unknown }) {
  const n = num(value)
  if (n === 0) return <span>{formatCurrency(0)}</span>
  return n > 0
    ? <span style={{ color: '#2f8f4e' }}>{formatCurrency(n)} <small>to give</small></span>
    : <span style={{ color: '#c0392b' }}>{formatCurrency(-n)} <small>owes us</small></span>
}

function Line({ label, value, strong }: { label: string; value: ReactNode; strong?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '3px 0', fontWeight: strong ? 600 : 400, fontVariantNumeric: 'tabular-nums' }}>
      <Typography.Text type={strong ? undefined : 'secondary'}>{label}</Typography.Text>
      <span>{value}</span>
    </div>
  )
}

function Panel({ title, icon, tint, children }: { title: string; icon: ReactNode; tint: string; children: ReactNode }) {
  return (
    <Card size="small" style={{ borderRadius: 12, borderColor: '#edf0f3', height: '100%' }} title={<span><span style={{ color: tint, marginRight: 8 }}>{icon}</span>{title}</span>}>
      {children}
    </Card>
  )
}

/** Staff khata summary: salary side and trip money side kept apart, as the owner pays trips weekly. */
export function StaffKhataSummary({ meta }: { meta: Meta }) {
  const monthly = meta.basic_pay !== null && meta.basic_pay !== undefined
  const hasTrips = num(meta.trips) > 0 || num(meta.trip_balance) !== 0 || num(meta.trip_paid) > 0
  return (
    <div style={{ margin: '4px 0 16px' }}>
      <Row gutter={[12, 12]}>
        <Col xs={24} md={hasTrips ? 12 : 24}>
          <Panel title="Salary" icon={<WalletOutlined />} tint="#1f4e79">
            {monthly && <Line label="Basic pay (month)" value={formatCurrency(num(meta.basic_pay))} />}
            {!monthly && <Line label="Wages earned" value={formatCurrency(num(meta.wages_earned))} />}
            <Line label="Advances given" value={formatCurrency(num(meta.advances_paid))} />
            {num(meta.salary_paid) > 0 && <Line label="Salary paid" value={formatCurrency(num(meta.salary_paid))} />}
            <Line label={monthly ? 'Salary left' : 'Wages due'} value={<Due value={monthly ? meta.salary_left : meta.salary_balance} />} strong />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Present {String(meta.days_present)} · half {String(meta.half_days)} · absent {String(meta.days_absent)}
            </Typography.Text>
          </Panel>
        </Col>
        {hasTrips && (
          <Col xs={24} md={12}>
            <Panel title="Trip money" icon={<CarOutlined />} tint="#b7791f">
              <Line label={`Trips (${String(meta.trips)})`} value={formatCurrency(num(meta.trip_earned))} />
              <Line label="Trip money paid" value={formatCurrency(num(meta.trip_paid))} />
              <Line label="Trip money due" value={<Due value={meta.trip_balance} />} strong />
            </Panel>
          </Col>
        )}
      </Row>
      <div style={{ marginTop: 10, fontWeight: 600 }}>Total khata balance: <Due value={meta.balance_payable} /></div>
    </div>
  )
}
