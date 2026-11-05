import { App, Button, Card, Descriptions, Input, Select, Space, Table, Typography } from 'antd'
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
import { formatCurrency, formatQty } from '@/lib/format'
import { STICKY_HEADER } from '@/components/tableDefaults'

/** Why pay is cut; the text goes to the worker's khata as "katoti 1,000: Chutti: 2 din". */
const REASONS = [
  { value: 'Chutti', label: 'Chutti (absent din)' },
  { value: 'Jurmana', label: 'Jurmana (fine)' },
  { value: 'Nuqsan', label: 'Nuqsan (damage)' },
  { value: 'Other', label: 'Other' },
]

export default function Settlements() {
  const { message } = App.useApp()
  const lookups = useLookups()
  const canSettle = usePermission('wages.settle')
  const [staffId, setStaffId] = useState<number | null>(null)
  const [range, setRange] = useState<DateRange>([dayjs().startOf('month').format(API_DATE), today()])
  const [preview, setPreview] = useState<SettlementPreview | null>(null)
  const [deductions, setDeductions] = useState('0')
  const [reason, setReason] = useState<string | undefined>()
  const [detail, setDetail] = useState('')
  const [loading, setLoading] = useState(false)
  const list = useGet<Settlement[]>('/labour/settlements', { staff_id: staffId })
  const save = useSave<object>('post', '/labour/settlements', {
    successMessage: 'Settlement saved and posted to the books',
    onSuccess: () => { setPreview(null); setDeductions('0'); setReason(undefined); setDetail('') },
  })

  async function load() {
    if (!staffId) return
    setLoading(true)
    try {
      const { data } = await api.get<SettlementPreview>('/labour/settlements/preview', { params: { staff_id: staffId, period_from: range[0], period_to: range[1] } })
      setPreview(data)
    } catch (e) {
      message.error(apiError(e).message)
    } finally {
      setLoading(false)
    }
  }

  // From the khata: advances from any month (entered in Payments) and pay still owed from before both count.
  const net = preview ? Number(preview.net_before_deductions) - Number(deductions || 0) : 0
  const absent = Number(preview?.absent_days ?? 0)
  const reasonText = [reason === 'Other' ? '' : reason, detail.trim()].filter(Boolean).join(': ')
  function pickReason(r: string) {
    setReason(r)
    // Chutti on a monthly salary: absent days x one day's pay, which the munshi can still change
    if (r === 'Chutti' && preview?.day_rate && absent > 0) {
      setDeductions(String(Math.round(absent * Number(preview.day_rate))))
      setDetail(`${formatQty(absent)} din`)
    }
  }
  const columns: ColumnsType<Settlement> = [
    { title: 'Worker', dataIndex: 'staff_id', render: (id: number) => lookups.staffById.get(id)?.name },
    { title: 'Period', render: (_, s) => `${formatDate(s.period_from)} – ${formatDate(s.period_to)}` },
    { title: 'Days', dataIndex: 'days', align: 'right', render: formatQty },
    { title: 'Trips', dataIndex: 'trips', align: 'right' },
    { title: 'Gross', dataIndex: 'gross', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Advances', dataIndex: 'advances_adjusted', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Deductions', dataIndex: 'deductions', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Katoti ki wajah', dataIndex: 'deduction_reason', render: (v: string | null) => v ?? '' },
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
              <Descriptions.Item label="Chutti (absent)">{absent > 0 ? `${formatQty(absent)} din` : 'None'}</Descriptions.Item>
              <Descriptions.Item label="Trips">{preview.trips}</Descriptions.Item>
              {Number(preview.trip_pay) > 0 && <Descriptions.Item label="Trip pay (already in khata)"><Money value={preview.trip_pay} /></Descriptions.Item>}
              <Descriptions.Item label="Gross wages"><Money value={preview.gross} bold /></Descriptions.Item>
              <Descriptions.Item label="Advances in period"><Money value={preview.advances_in_period} /></Descriptions.Item>
              <Descriptions.Item label="Baqaya"><Money value={preview.current_balance} drcr /></Descriptions.Item>
            </Descriptions>
            {!preview.accrues_on_settlement && <p style={{ margin: '8px 0 0', color: '#8c8c8c' }}>Daily-wage workers already earned these wages day by day when attendance was saved. Settling records the period and any deduction.</p>}
            {canSettle && (
              <>
              <Space wrap align="end" style={{ marginTop: 12 }}>
                <div>
                  <div>Advance / pichla baqaya</div>
                  <div className="settle-advance"><Money value={preview.carried_forward} drcr bold /></div>
                </div>
                <label htmlFor="cut-amount">Katoti (deduction)<div style={{ width: 170 }}><MoneyInput id="cut-amount" value={deductions} onChange={setDeductions} /></div></label>
                <label htmlFor="cut-reason">Katoti ki wajah<div style={{ width: 200 }}><Select id="cut-reason" style={{ width: '100%' }} placeholder="Choose reason" value={reason} onChange={pickReason} options={REASONS} allowClear onClear={() => setReason(undefined)} /></div></label>
                <label htmlFor="cut-detail">Detail<div style={{ width: 220 }}><Input id="cut-detail" value={detail} onChange={(e) => setDetail(e.target.value)} maxLength={80} placeholder="e.g. 2 din, tyre phata" /></div></label>
                <b>{net >= 0 ? <>Net payable: <Money value={net} bold /></> : <>Dena: 0 · <span style={{ color: '#b45309' }}><Money value={-net} /> us ne wapas karna hai (agle mahine kategi)</span></>}</b>
                <Button type="primary" loading={save.isPending}
                  onClick={() => {
                    if (Number(deductions) > 0 && !reasonText) { message.warning('Choose why the pay is cut (Chutti, Jurmana...) so it shows in the khata.'); return }
                    save.mutate({ staff_id: staffId, period_from: range[0], period_to: range[1], deductions: deductions || '0', deduction_reason: Number(deductions) > 0 ? reasonText : null })
                  }}>Save settlement</Button>
              </Space>
              <Typography.Text type="secondary" style={{ display: 'block', marginTop: 6 }}>
                "Advance / pichla baqaya" khata se aata hai: har mahine ka advance (Payments &gt; Purpose "Advance") aur pichle mahine ka bacha hua hisaab. Is mein "lena" = us ne wapas karna hai, "dena" = hum ne pichla dena hai.
              </Typography.Text>
              {reason === 'Chutti' && preview.day_rate && (
                <Typography.Text type="secondary" style={{ display: 'block', marginTop: 6 }}>
                  {formatQty(absent)} din × {formatCurrency(preview.day_rate)} (tankhwah ÷ 30). Badal sakte hain.
                </Typography.Text>
              )}
              </>
            )}
          </div>
        )}
      </Card>
      <Table<Settlement> sticky={STICKY_HEADER} size="small" rowKey="id" loading={list.isLoading} columns={columns} dataSource={list.data ?? []} scroll={{ x: 'max-content' }} pagination={{ pageSize: 15, hideOnSinglePage: true }} rowClassName={(s) => (s.status === 'void' ? 'row-void' : '')} />
    </>
  )
}
