import { Card, Col, Row, Typography } from 'antd'
import { Link, Navigate, useParams } from 'react-router-dom'
import { useAuth } from '@/app/AuthContext'
import { PageHeader } from '@/components/PageHeader'
import { RequirePerm } from '@/components/RequirePerm'
import ReportPage from './ReportPage'
import { REPORTS, reportByKey } from './reportConfigs'

export function ReportsHub() {
  const { can } = useAuth()
  return (
    <>
      <PageHeader title="Reports" subtitle="Everything is derived from the journal, so balances always agree. Every report exports to Excel and PDF." />
      <Row gutter={[12, 12]}>
        {REPORTS.filter((r) => can(r.perm)).map((r) => (
          <Col xs={24} md={12} xl={8} key={r.key}>
            <Link to={`/reports/${r.key}`}>
              <Card hoverable size="small" title={r.title} style={{ height: '100%' }}>
                <Typography.Text type="secondary">{r.description}</Typography.Text>
              </Card>
            </Link>
          </Col>
        ))}
      </Row>
    </>
  )
}

export function ReportRoute() {
  const { key = '' } = useParams()
  const config = reportByKey(key)
  if (!config) return <Navigate to="/reports" replace />
  return (
    <RequirePerm perm={config.perm}>
      <ReportPage key={config.key} config={config} />
    </RequirePerm>
  )
}
