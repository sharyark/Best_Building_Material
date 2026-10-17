import { App, Button, Card, Descriptions, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, apiError } from '@/api/client'
import { useGet, useSave } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Settlement, SettlementPreview } from '@/api/types'
import { DateRangeField, type DateRange } from '@/components/DateField'
import { MoneyInput } from '@/components/DecimalInput'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Money } from '@/components/Money'
import { StatusTag } from '@/components/StatusTag'
import { VoidButton } from '@/components/VoidButton'
import { usePermission } from '@/hooks/usePermission'
import { API_DATE, formatDate, today } from '@/lib/date'
import { formatQty } from '@/lib/format'

export default function Settlements() {
  const { message } = App.useApp()
  const lookups = useLookups()
  const canSettle = usePermission('wages.settle')
  const [staffId, setStaffId] = useState<number | null>(null)
  const [range, setRange] = useState<DateRange>([dayjs().startOf('month').format(API_DATE), today()])
  const [preview, setPreview] = useState<SettlementPreview | null>(null)
  const [deductions, setDeductions] = useState('0')
  const [advances, setAdvances] = useState('')
  const [loading, setLoading] = useState(false)
  const list = useGet<Settlement[]>('/labour/settlements', { staff_id: staffId })
  const save = useSave<object>('post', '/labour/settlements', {
    successMessage: 'Settlement saved and posted to the books',
    onSuccess: () => { setPreview(null); setDeductions('0'); setAdvances('') },
  })

  async function load() {
    if (!staffId) return
    setLoading(true)
    try {
      const { data } = await api.get<SettlementPreview>('/labour/settlements/preview', { params: { staff_id: staffId, period_from: range[0], period_to: range[1] } })
      setPreview(data)
      setAdvances(data.advances_in_period)
    } catch (e) {
      message.error(apiError(e).message)
    } finally {
      setLoading(false)
    }
  }

  const net = preview ? Number(preview.gross) - Number(advances || 0) - Number(deductions || 0) : 0
  const columns: ColumnsType<Settlement> = [
    { title: 'Worker', dataIndex: 'staff_id', render: (id: number) => lookups.staffById.get(id)?.name },
    { title: 'Period', render: (_, s) => `${formatDate(s.period_from)} – ${formatDate(s.period_to)}` },
    { title: 'Days', dataIndex: 'days', align: 'right', render: formatQty },
    { title: 'Trips', dataIndex: 'trips', align: 'right' },
    { title: 'Gross', dataIndex: 'gross', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Advances', dataIndex: 'advances_adjusted', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Deductions', dataIndex: 'deductions', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Net', dataIndex: 'net_payable', align: 'right', render: (v) => <Money value={v} bold /> },
    { title: 'Status', render: (_, s) => <StatusTag status={s.status} reason={s.void_reason} /> },
    { title: '', render: (_, s) => s.status === 'active' && <VoidButton path={`/labour/settlements/${s.id}`} perm="settlement.void" label="settlement" /> },
  ]

  return (
    <>
      <Card size="small" title="Settle wages for a period" style={{ marginBottom: 16 }}>
        <Space wrap align="start">
          <div style={{ width: 240 }}><EntitySelect options={optionsOf(lookups.staff)} value={staffId} onChange={(v) => { setStaffId(v); setPreview(null) }} placeholder="Choose worker" /></div>
          <DateRangeField value={range} onChange={(r) => { setRange(r); setPreview(null) }} />
          <Button onClick={load} loading={loading} disabled={!staffId}>Calculate</Button>
          {staffId && <Link to={`/reports/staff-khata?staff=${staffId}`}><Button type="link">Open khata</Button></Link>}
        </Space>
        {preview && (
          <div style={{ marginTop: 16 }}>
            <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 4 }} bordered>
              <Descriptions.Item label="Pay type">{preview.wage_type.replace('_', ' ')}</Descriptions.Item>
              <Descriptions.Item label="Days present">{formatQty(preview.days)}</Descriptions.Item>
              <Descriptions.Item label="Trips">{preview.trips}</Descriptions.Item>
              <Descriptions.Item label="Gross wages"><Money value={preview.gross} bold /></Descriptions.Item>
              <Descriptions.Item label="Advances in period"><Money value={preview.advances_in_period} /></Descriptions.Item>
              <Descriptions.Item label="Current balance"><Money value={preview.current_balance} drcr /></Descriptions.Item>
            </Descriptions>
            {!preview.accrues_on_settlement && <p style={{ margin: '8px 0 0', color: '#8c8c8c' }}>Daily-wage workers already earned these wages day by day when attendance was saved. Settling records the period and any deduction.</p>}
            {canSettle && (
              <Space wrap align="end" style={{ marginTop: 12 }}>
                <label>Advances adjusted<div style={{ width: 170 }}><MoneyInput value={advances} onChange={setAdvances} /></div></label>
                <label>Deductions (fines / absences)<div style={{ width: 170 }}><MoneyInput value={deductions} onChange={setDeductions} /></div></label>
                <b>Net payable: <Money value={net} bold /></b>
                <Button type="primary" loading={save.isPending} onClick={() => save.mutate({ staff_id: staffId, period_from: range[0], period_to: range[1], deductions: deductions || '0', advances_adjusted: advances || '0' })}>Save settlement</Button>
              </Space>
            )}
          </div>
        )}
      </Card>
      <Table<Settlement> size="small" rowKey="id" loading={list.isLoading} columns={columns} dataSource={list.data ?? []} scroll={{ x: 'max-content' }} pagination={{ pageSize: 15, hideOnSinglePage: true }} rowClassName={(s) => (s.status === 'void' ? 'row-void' : '')} />
    </>
  )
}
