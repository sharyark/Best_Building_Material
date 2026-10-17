import { Alert, Card, Col, Row, Statistic, Table, Typography } from 'antd'
import { Link } from 'react-router-dom'
import { apiError } from '@/api/client'
import { useGet } from '@/api/hooks'
import type { Dashboard } from '@/api/types'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { CURRENCY } from '@/lib/config'
import { formatDate } from '@/lib/date'
import { formatMoney, formatQty, toNumber } from '@/lib/format'

function Stat({ title, value, money, to, color }: { title: string; value: string | number; money?: boolean; to?: string; color?: string }) {
  const card = (
    <Card size="small" hoverable={Boolean(to)}>
      <Statistic title={title} value={value} formatter={() => <span style={{ whiteSpace: 'nowrap' }}>{money ? `${CURRENCY} ${formatMoney(value)}` : value}</span>} valueStyle={{ color, fontSize: 20 }} />
    </Card>
  )
  return to ? <Link to={to}>{card}</Link> : card
}

export default function DashboardPage() {
  const { data, isLoading, error } = useGet<Dashboard>('/reports/dashboard', undefined, { staleTime: 10_000 })
  if (error) return <Alert type="error" showIcon message={apiError(error).message} />
  const d = data
  return (
    <>
      <PageHeader title="Dashboard" subtitle={d ? `Today, ${formatDate(d.date)}` : undefined} />
      <Row gutter={[12, 12]}>
        <Col xs={12} md={8} xl={4}><Stat title="Trips today" value={d?.trips_today ?? 0} to="/challans" /></Col>
        <Col xs={12} md={8} xl={4}><Stat title="Sales today" value={d?.sales_today ?? 0} money /></Col>
        <Col xs={12} md={8} xl={4}><Stat title="Sales this month" value={d?.sales_month ?? 0} money /></Col>
        <Col xs={12} md={8} xl={4}><Stat title="Cash in hand" value={d?.cash_in_hand ?? 0} money color={toNumber(d?.cash_in_hand) < 0 ? '#cf1322' : undefined} to="/reports/cash-book" /></Col>
        <Col xs={12} md={8} xl={4}><Stat title="Bank / wallet" value={d?.bank_balance ?? 0} money to="/reports/cash-book" /></Col>
        <Col xs={12} md={8} xl={4}><Stat title="Yard stock value" value={d?.stock_value ?? 0} money to="/stock" /></Col>
        <Col xs={12} md={8}><Stat title="Total receivable (customers owe us)" value={d?.total_receivable ?? 0} money color="#1f4e79" to="/reports/outstanding" /></Col>
        <Col xs={12} md={8}><Stat title="Total payable (we owe suppliers)" value={d?.total_payable ?? 0} money color="#b45309" /></Col>
        <Col xs={12} md={8}><Stat title="Staff wages payable" value={d?.staff_payable ?? 0} money to="/labour" /></Col>
      </Row>
      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        <Col xs={24} lg={12}>
          <Card size="small" title="Today's trips by material" loading={isLoading}>
            <Table size="small" rowKey="material" pagination={false} dataSource={d?.trips_by_material ?? []} locale={{ emptyText: 'No trips yet today' }}
              columns={[{ title: 'Material', dataIndex: 'material' }, { title: 'Trips', dataIndex: 'trips', align: 'right' }, { title: 'Quantity', align: 'right', render: (_, r) => `${formatQty(r.qty)} ${r.unit}` }]} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="Biggest outstanding balances" loading={isLoading}>
            <Table size="small" rowKey="party_id" pagination={false} dataSource={d?.top_debtors ?? []} locale={{ emptyText: 'Nobody owes anything' }}
              columns={[{ title: 'Customer', render: (_, r) => <Link to={`/reports/khata?party=${r.party_id}`}>{r.name}</Link> }, { title: 'Owes', dataIndex: 'balance', align: 'right', render: (v) => <Money value={v} bold /> }]} />
            {d && toNumber(d.staff_advances) > 0 && <Typography.Text type="secondary">Advances out to staff: <Money value={d.staff_advances} /></Typography.Text>}
          </Card>
        </Col>
      </Row>
    </>
  )
}
