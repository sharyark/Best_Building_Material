import { Alert, App, Button, Space, Table, Tabs, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { api, apiError } from '@/api/client'
import { useGet } from '@/api/hooks'
import type { StockCount, StockItem } from '@/api/types'
import { DateField } from '@/components/DateField'
import { QtyInput } from '@/components/DecimalInput'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { usePermission } from '@/hooks/usePermission'
import { formatDate, today } from '@/lib/date'
import { formatQty, toNumber } from '@/lib/format'
import ReportPage from '@/features/reports/ReportPage'
import { reportByKey } from '@/features/reports/reportConfigs'
import { useLookups } from '@/api/lookups'
import { useQueryClient } from '@tanstack/react-query'

function LiveStock() {
  const { data = [], isLoading } = useGet<StockItem[]>('/stock', undefined, { staleTime: 5_000 })
  const columns: ColumnsType<StockItem> = [
    { title: 'Material', dataIndex: 'material_name' },
    { title: 'On hand', align: 'right', render: (_, s) => <span style={{ color: toNumber(s.qty_on_hand) < 0 ? '#cf1322' : undefined }}>{formatQty(s.qty_on_hand)} {s.unit}</span> },
    { title: 'Avg cost (weighted)', dataIndex: 'avg_cost', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Stock value', dataIndex: 'value', align: 'right', render: (v) => <Money value={v} bold /> },
  ]
  return (
    <Table<StockItem>
      size="small" rowKey="material_id" loading={isLoading} columns={columns} dataSource={data} pagination={false} scroll={{ x: 'max-content' }}
      summary={(rows) => (
        <Table.Summary.Row>
          <Table.Summary.Cell index={0} colSpan={3}><Typography.Text strong>Total yard value</Typography.Text></Table.Summary.Cell>
          <Table.Summary.Cell index={3} align="right"><Money value={rows.reduce((s, r) => s + toNumber(r.value), 0)} bold /></Table.Summary.Cell>
        </Table.Summary.Row>
      )}
    />
  )
}

function PhysicalCount() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const canCount = usePermission('stock.count')
  const lookups = useLookups()
  const { data = [] } = useGet<StockItem[]>('/stock', undefined, { staleTime: 5_000 })
  const history = useGet<StockCount[]>('/stock/counts')
  const [date, setDate] = useState(today())
  const [physical, setPhysical] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState<number | null>(null)

  async function post(item: StockItem) {
    setBusy(item.material_id)
    try {
      const { data: c } = await api.post<StockCount>('/stock/counts', { date, material_id: item.material_id, physical_qty: physical[item.material_id] })
      message.success(Number(c.diff) === 0 ? 'Count matches the system' : `Adjusted by ${formatQty(c.diff)} ${item.unit} (posted to Stock Loss)`)
      setPhysical((p) => ({ ...p, [item.material_id]: '' }))
      await qc.invalidateQueries()
    } catch (e) {
      message.error(apiError(e).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Sand and crush lose volume to wind, rain and measuring differences. Measure the heap, enter the physical quantity and post: the difference goes to Stock Loss at the average cost." />
      <Space style={{ marginBottom: 12 }}><span>Count date</span><div style={{ width: 160 }}><DateField value={date} onChange={setDate} /></div></Space>
      <Table<StockItem>
        size="small" rowKey="material_id" pagination={false} dataSource={data} scroll={{ x: 'max-content' }}
        columns={[
          { title: 'Material', dataIndex: 'material_name' },
          { title: 'System qty', align: 'right', render: (_, s) => `${formatQty(s.qty_on_hand)} ${s.unit}` },
          { title: 'Physical qty', render: (_, s) => <div style={{ width: 150 }}><QtyInput value={physical[s.material_id] ?? ''} onChange={(v) => setPhysical((p) => ({ ...p, [s.material_id]: v }))} addonAfter={s.unit} disabled={!canCount} /></div> },
          { title: 'Difference', align: 'right', render: (_, s) => { const raw = physical[s.material_id]; if (!raw) return ''; const d = toNumber(raw) - toNumber(s.qty_on_hand); return <span style={{ color: d < 0 ? '#cf1322' : d > 0 ? '#389e0d' : undefined }}>{d > 0 ? '+' : ''}{formatQty(d)}</span> } },
          { title: '', render: (_, s) => canCount && <Button size="small" type="primary" loading={busy === s.material_id} disabled={!physical[s.material_id]} onClick={() => post(s)}>Post count</Button> },
        ]}
      />
      <Typography.Title level={5} style={{ marginTop: 20 }}>Count history</Typography.Title>
      <Table<StockCount>
        size="small" rowKey="id" loading={history.isLoading} dataSource={history.data ?? []} pagination={{ pageSize: 10, hideOnSinglePage: true }}
        columns={[
          { title: 'Date', dataIndex: 'date', render: formatDate },
          { title: 'Material', dataIndex: 'material_id', render: (id: number) => lookups.materialById.get(id)?.name },
          { title: 'System', dataIndex: 'system_qty', align: 'right', render: formatQty },
          { title: 'Physical', dataIndex: 'physical_qty', align: 'right', render: formatQty },
          { title: 'Difference', dataIndex: 'diff', align: 'right', render: (v) => <span style={{ color: toNumber(v) < 0 ? '#cf1322' : undefined }}>{formatQty(v)}</span> },
        ]}
      />
    </>
  )
}

export default function StockPage() {
  const report = reportByKey('yard-stock')!
  return (
    <>
      <PageHeader title="Yard stock" subtitle="Live balance with moving weighted-average cost" />
      <Tabs
        destroyInactiveTabPane
        items={[
          { key: 'live', label: 'Live stock', children: <LiveStock /> },
          { key: 'count', label: 'Physical count', children: <PhysicalCount /> },
          { key: 'report', label: 'Movement report', children: <ReportPage config={report} embedded /> },
        ]}
      />
    </>
  )
}
