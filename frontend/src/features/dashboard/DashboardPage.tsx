import {
  BankOutlined, CarOutlined, DatabaseOutlined, DollarOutlined, RiseOutlined, TeamOutlined, WalletOutlined, FallOutlined, LineChartOutlined,
} from '@ant-design/icons'
import { Alert, Card, Col, Row, Table, Typography } from 'antd'
import { Link } from 'react-router-dom'
import { apiError } from '@/api/client'
import { useGet } from '@/api/hooks'
import type { Dashboard } from '@/api/types'
import { HeroBanner } from '@/components/HeroBanner'
import { Money } from '@/components/Money'
import { StatCard } from '@/components/StatCard'
import { CURRENCY } from '@/lib/config'
import { formatMoney, formatQty, toNumber } from '@/lib/format'

const cur = (v: string | number | undefined) => `${CURRENCY} ${formatMoney(v ?? 0)}`
const cardStyle = { borderRadius: 12, borderColor: '#edf0f3', boxShadow: '0 1px 3px rgba(16,38,59,.06)' }

export default function DashboardPage() {
  const { data, isLoading, error } = useGet<Dashboard>('/reports/dashboard', undefined, { staleTime: 10_000 })
  if (error) return <Alert type="error" showIcon message={apiError(error).message} />
  const d = data
  return (
    <>
      <HeroBanner date={d?.date} trips={d?.trips_today} />
      <Row gutter={[12, 12]}>
        <Col xs={24} sm={12} lg={8}><StatCard title="Trips today" value={d?.trips_today ?? 0} icon={<CarOutlined />} tone="blue" to="/challans" /></Col>
        <Col xs={24} sm={12} lg={8}><StatCard title="Sales today" value={cur(d?.sales_today)} icon={<DollarOutlined />} tone="green" /></Col>
        <Col xs={24} sm={12} lg={8}><StatCard title="Sales this month" value={cur(d?.sales_month)} icon={<LineChartOutlined />} tone="green" /></Col>
        <Col xs={24} sm={12} lg={8}><StatCard title="Cash in hand" value={cur(d?.cash_in_hand)} icon={<WalletOutlined />} tone="amber" valueColor={toNumber(d?.cash_in_hand) < 0 ? '#cf1322' : undefined} to="/reports/cash-book" /></Col>
        <Col xs={24} sm={12} lg={8}><StatCard title="Bank / wallet" value={cur(d?.bank_balance)} icon={<BankOutlined />} tone="teal" to="/reports/cash-book" /></Col>
        <Col xs={24} sm={12} lg={8}><StatCard title="Yard stock value" value={cur(d?.stock_value)} icon={<DatabaseOutlined />} tone="purple" to="/stock" /></Col>
        <Col xs={24} sm={12} lg={8}><StatCard title="Receivable: customers owe us" value={cur(d?.total_receivable)} icon={<RiseOutlined />} tone="blue" to="/reports/outstanding" /></Col>
        <Col xs={24} sm={12} lg={8}><StatCard title="Payable: we owe suppliers" value={cur(d?.total_payable)} icon={<FallOutlined />} tone="amber" /></Col>
        <Col xs={24} sm={12} lg={8}><StatCard title="Staff wages payable" value={cur(d?.staff_payable)} icon={<TeamOutlined />} tone="slate" to="/labour" /></Col>
      </Row>
      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        <Col xs={24} lg={12}>
          <Card size="small" title="Today's trips by material" loading={isLoading} style={cardStyle}>
            <Table size="small" rowKey="material" pagination={false} dataSource={d?.trips_by_material ?? []} locale={{ emptyText: 'No trips yet today' }}
              columns={[{ title: 'Material', dataIndex: 'material' }, { title: 'Trips', dataIndex: 'trips', align: 'right' }, { title: 'Quantity', align: 'right', render: (_, r) => `${formatQty(r.qty)} ${r.unit}` }]} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="Biggest outstanding balances" loading={isLoading} style={cardStyle}>
            <Table size="small" rowKey="party_id" pagination={false} dataSource={d?.top_debtors ?? []} locale={{ emptyText: 'Nobody owes anything' }}
              columns={[{ title: 'Customer', render: (_, r) => <Link to={`/reports/khata?party=${r.party_id}`}>{r.name}</Link> }, { title: 'Owes', dataIndex: 'balance', align: 'right', render: (v) => <Money value={v} bold /> }]} />
            {d && toNumber(d.staff_advances) > 0 && <Typography.Text type="secondary">Advances out to staff: <Money value={d.staff_advances} /></Typography.Text>}
          </Card>
        </Col>
      </Row>
    </>
  )
}
