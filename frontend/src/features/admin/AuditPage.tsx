import { Descriptions, Input, Select, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useState } from 'react'
import { usePage } from '@/api/hooks'
import type { AuditLog, User } from '@/api/types'
import { useGet } from '@/api/hooks'
import { DateRangeField, type DateRange } from '@/components/DateField'
import { PageHeader } from '@/components/PageHeader'
import { API_DATE, today } from '@/lib/date'

const ENTITIES = ['deliveries', 'purchases', 'payments', 'expenses', 'rentals', 'invoices', 'wage_settlements', 'attendance', 'stock_counts', 'parties', 'staff', 'materials', 'vehicles', 'money_accounts', 'rate_cards', 'users', 'period_locks']
const COLORS: Record<string, string> = { create: 'green', update: 'blue', void: 'red', delete: 'volcano' }

function Diff({ log }: { log: AuditLog }) {
  const keys = Array.from(new Set([...Object.keys(log.before ?? {}), ...Object.keys(log.after ?? {})]))
  return (
    <Descriptions size="small" bordered column={1}>
      {keys.map((k) => (
        <Descriptions.Item key={k} label={k}>
          {log.action === 'create' ? <code>{JSON.stringify(log.after?.[k])}</code> : (
            <>
              <code style={{ color: '#cf1322' }}>{JSON.stringify(log.before?.[k])}</code> → <code style={{ color: '#389e0d' }}>{JSON.stringify(log.after?.[k])}</code>
            </>
          )}
        </Descriptions.Item>
      ))}
    </Descriptions>
  )
}

export default function AuditPage() {
  const [range, setRange] = useState<DateRange>([dayjs().subtract(6, 'day').format(API_DATE), today()])
  const [entity, setEntity] = useState<string | undefined>()
  const [entityId, setEntityId] = useState('')
  const [action, setAction] = useState<string | undefined>()
  const [page, setPage] = useState(1)
  const users = useGet<User[]>('/users')
  const { data, isLoading } = usePage<AuditLog>('/audit-logs', { from: range[0], to: range[1], entity, entity_id: entityId || undefined, action, page, size: 30 })
  const userName = (id: number | null) => users.data?.find((u) => u.id === id)?.name ?? (id ? `#${id}` : 'system')

  const columns: ColumnsType<AuditLog> = [
    { title: 'When', dataIndex: 'at', render: (v: string) => dayjs(v).format('DD-MM-YYYY HH:mm:ss') },
    { title: 'Who', dataIndex: 'user_id', render: userName },
    { title: 'Action', dataIndex: 'action', render: (a: string) => <Tag color={COLORS[a]}>{a}</Tag> },
    { title: 'What', dataIndex: 'entity' },
    { title: 'ID', dataIndex: 'entity_id' },
    { title: 'IP', dataIndex: 'ip' },
  ]
  return (
    <>
      <PageHeader title="Audit log" subtitle="Who changed what, when, with before / after values" />
      <Space wrap style={{ marginBottom: 12 }}>
        <DateRangeField value={range} onChange={(r) => { setRange(r); setPage(1) }} />
        <Select allowClear showSearch placeholder="Any record type" style={{ width: 190 }} value={entity} onChange={(v) => { setEntity(v); setPage(1) }} options={ENTITIES.map((e) => ({ value: e, label: e }))} />
        <Input allowClear placeholder="Record ID" style={{ width: 110 }} value={entityId} onChange={(e) => { setEntityId(e.target.value.replace(/\D/g, '')); setPage(1) }} />
        <Select allowClear placeholder="Any action" style={{ width: 130 }} value={action} onChange={(v) => { setAction(v); setPage(1) }} options={['create', 'update', 'void', 'delete'].map((a) => ({ value: a, label: a }))} />
      </Space>
      <Table<AuditLog> size="small" rowKey="id" loading={isLoading} columns={columns} dataSource={data?.items ?? []} scroll={{ x: 'max-content' }}
        expandable={{ expandedRowRender: (l) => <Diff log={l} /> }}
        pagination={{ current: page, pageSize: 30, total: data?.total ?? 0, onChange: setPage, showSizeChanger: false }} />
    </>
  )
}
