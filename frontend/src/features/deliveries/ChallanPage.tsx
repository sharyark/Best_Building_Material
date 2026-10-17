import { EditOutlined } from '@ant-design/icons'
import { Button, Card, Modal, Select, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { usePage } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Delivery } from '@/api/types'
import { DateRangeField, type DateRange } from '@/components/DateField'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { PrintButton } from '@/components/PrintButton'
import { StatusTag } from '@/components/StatusTag'
import { VoidButton } from '@/components/VoidButton'
import { usePermission } from '@/hooks/usePermission'
import { formatDate, startOfMonth, today } from '@/lib/date'
import { formatQty } from '@/lib/format'
import { openFile } from '@/lib/download'
import ChallanForm from './ChallanForm'

export default function ChallanPage() {
  const lookups = useLookups()
  const canEdit = usePermission('challan.update')
  const [range, setRange] = useState<DateRange>([startOfMonth(), today()])
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [status, setStatus] = useState<string | undefined>()
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<Delivery | null>(null)
  const { data, isLoading } = usePage<Delivery>('/deliveries', {
    from: range[0], to: range[1], customer_id: customerId, status, page, size: 25,
  })

  const columns: ColumnsType<Delivery> = [
    { title: 'Challan', dataIndex: 'challan_no', width: 150 },
    { title: 'Date', dataIndex: 'date', render: formatDate },
    { title: 'Customer', dataIndex: 'customer_id', render: (id: number) => lookups.partyById.get(id)?.name },
    { title: 'Site', dataIndex: 'site_id', render: (id: number | null) => (id ? lookups.siteById.get(id)?.name : '') },
    { title: 'Material', dataIndex: 'material_id', render: (id: number) => lookups.materialById.get(id)?.name },
    { title: 'Qty', align: 'right', render: (_, d) => `${formatQty(d.qty)} ${d.unit}` },
    { title: 'Rate', dataIndex: 'sale_rate', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Amount', align: 'right', render: (_, d) => <Money value={Number(d.sale_amount) + Number(d.freight_amount)} bold /> },
    { title: 'Vehicle', dataIndex: 'vehicle_id', render: (id: number | null) => (id ? lookups.vehicleById.get(id)?.name : '') },
    { title: 'Status', render: (_, d) => <StatusTag status={d.status} reason={d.void_reason} /> },
    {
      title: '',
      align: 'right',
      render: (_, d) => (
        <Space size={4}>
          <PrintButton url={`/deliveries/${d.id}/pdf`} />
          {canEdit && d.status === 'active' && (
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
        <ChallanForm onPrint={(d) => void openFile(`/deliveries/${d.id}/pdf`).catch(() => undefined)} />
      </Card>
      <Space wrap style={{ marginBottom: 12 }}>
        <DateRangeField value={range} onChange={(r) => { setRange(r); setPage(1) }} />
        <div style={{ width: 220 }}><EntitySelect options={optionsOf(lookups.customers)} value={customerId} onChange={(v) => { setCustomerId(v); setPage(1) }} placeholder="All customers" /></div>
        <Select allowClear placeholder="Any status" style={{ width: 130 }} value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[{ value: 'active', label: 'Active' }, { value: 'void', label: 'Void' }]} />
      </Space>
      <Table<Delivery>
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
