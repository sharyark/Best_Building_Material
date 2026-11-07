import { EditOutlined } from '@ant-design/icons'
import { Button, Card, Grid, Modal, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { usePage } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Delivery } from '@/api/types'
import { DateRangeField, type DateRange } from '@/components/DateField'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { ExportCard } from '@/components/ExportCard'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { PrintButton } from '@/components/PrintButton'
import { StatusTag } from '@/components/StatusTag'
import { VoidButton } from '@/components/VoidButton'
import { usePermission } from '@/hooks/usePermission'
import { formatDate, rangeFromUrl, startOfMonth, today } from '@/lib/date'
import { formatQty } from '@/lib/format'
import { openFile } from '@/lib/download'
import { getPaper } from '@/lib/paper'
import ChallanForm from './ChallanForm'
import { DeliverButton } from './DeliverButton'
import { STICKY_HEADER } from '@/components/tableDefaults'

export default function ChallanPage() {
  const lookups = useLookups()
  const canEdit = usePermission('challan.update')
  // The munshi can change an order until it is delivered; after that only the owner can.
  const canEditDelivered = usePermission('challan.edit_delivered')
  const [search] = useSearchParams()
  // ?date= from the dashboard opens that day's challans
  const [range, setRange] = useState<DateRange>(() => rangeFromUrl(search) ?? [startOfMonth(), today()])
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [status, setStatus] = useState<string | undefined>()
  const [delivered, setDelivered] = useState<boolean | undefined>(() => (search.get('pending') ? false : undefined))
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<Delivery | null>(null)
  const { data, isLoading } = usePage<Delivery>('/deliveries', {
    // Pending orders are listed whatever their date, so an old one is not forgotten.
    ...(delivered === false ? {} : { from: range[0], to: range[1] }), customer_id: customerId, status, delivered, page, size: 25,
  })

  const wide = Grid.useBreakpoint().md ?? false
  const columns: ColumnsType<Delivery> = [
    { title: 'Challan', dataIndex: 'challan_no', width: 150 },
    { title: 'Date', dataIndex: 'date', render: formatDate },
    { title: 'Customer', dataIndex: 'customer_id', render: (id: number) => lookups.partyById.get(id)?.name },
    { title: 'Site', dataIndex: 'site_id', render: (id: number | null) => (id ? lookups.siteById.get(id)?.name : '') },
    {
      title: 'Material',
      render: (_, d) => (
        <>
          {lookups.materialById.get(d.material_id)?.name}
          {d.load_size === 'half' && <Tag style={{ marginLeft: 6 }}>Half</Tag>}
          {d.extra_material_id && (
            <Typography.Text type="secondary"> + {formatQty(d.extra_qty)} {d.extra_unit} {lookups.materialById.get(d.extra_material_id)?.name}</Typography.Text>
          )}
        </>
      ),
    },
    { title: 'Qty', align: 'right', render: (_, d) => `${formatQty(d.qty)} ${d.unit}` },
    { title: 'Rate', dataIndex: 'sale_rate', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Amount', align: 'right', render: (_, d) => <Money value={Number(d.sale_amount) + Number(d.freight_amount) + Number(d.extra_amount)} bold /> },
    { title: 'Vehicle', dataIndex: 'vehicle_id', render: (id: number | null) => (id ? lookups.vehicleById.get(id)?.name : '') },
    {
      title: 'Delivery',
      render: (_, d) =>
        d.status !== 'active' ? null : d.delivered ? <Tag color="green">Delivered</Tag> : <Tag color="orange">Pending</Tag>,
    },
    { title: 'Status', render: (_, d) => <StatusTag status={d.status} reason={d.void_reason} edit={d} /> },
    {
      title: '',
      key: 'actions',
      align: 'right',
      // Keep actions in view while scrolling wide tables; on a phone a pinned column would hide the data.
      fixed: wide ? 'right' : undefined,
      render: (_, d) => (
        <Space size={4}>
          {canEdit && d.status === 'active' && !d.delivered && <DeliverButton delivery={d} />}
          <PrintButton url={`/deliveries/${d.id}/pdf`} thermal />
          {canEdit && d.status === 'active' && (!d.delivered || canEditDelivered) && (
            <Button size="small" icon={<EditOutlined />} disabled={Boolean(d.invoice_id)} title={d.invoice_id ? 'On an invoice: void the invoice first' : 'Edit'} onClick={() => setEditing(d)} />
          )}
          {d.status === 'active' && (
            <VoidButton path={`/deliveries/${d.id}`} perm="challan.void" label={`challan ${d.challan_no}`} disabled={Boolean(d.invoice_id)} disabledReason="On an invoice: void the invoice first" />
          )}
        </Space>
      ),
    },
  ]

  return (
    <>
      <PageHeader title="Challans" subtitle="Trips out of the yard to customer sites" />
      <Card size="small" title="New challan" style={{ marginBottom: 16 }}>
        <ChallanForm onPrint={(d) => void openFile(`/deliveries/${d.id}/pdf`, { paper: getPaper() }).catch(() => undefined)} />
      </Card>
      <ExportCard endpoint="/deliveries" noun="challan" />
      <Space wrap style={{ marginBottom: 12 }}>
        <DateRangeField disabled={delivered === false} value={range} onChange={(r) => { setRange(r); setPage(1) }} />
        <div style={{ width: 220 }}><EntitySelect options={optionsOf(lookups.customers)} value={customerId} onChange={(v) => { setCustomerId(v); setPage(1) }} placeholder="All customers" /></div>
        <Select allowClear placeholder="Pending or delivered" style={{ width: 180 }} value={delivered} onChange={(v) => { setDelivered(v); setPage(1) }} options={[{ value: false, label: 'Pending orders' }, { value: true, label: 'Delivered' }]} />
        <Select allowClear placeholder="Any status" style={{ width: 130 }} value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[{ value: 'active', label: 'Active' }, { value: 'void', label: 'Void' }]} />
      </Space>
      <Table<Delivery>
        sticky={STICKY_HEADER}
        size="small"
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items ?? []}
        scroll={{ x: 'max-content' }}
        rowClassName={(d) => (d.status === 'void' ? 'row-void' : '')}
        pagination={{ current: page, pageSize: 25, total: data?.total ?? 0, onChange: setPage, showSizeChanger: false }}
      />
      <Modal open={editing !== null} title={`Edit ${editing?.challan_no ?? ''}`} footer={null} width={900} onCancel={() => setEditing(null)} destroyOnClose>
        {editing && <ChallanForm delivery={editing} onSaved={() => setEditing(null)} />}
      </Modal>
    </>
  )
}
