import { EditOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Modal, Select, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState, type ComponentType } from 'react'
import { usePage } from '@/api/hooks'
import { usePermission } from '@/hooks/usePermission'
import { startOfMonth, today } from '@/lib/date'
import { DateRangeField, type DateRange } from './DateField'
import { EntitySelect, type Option } from './EntitySelect'
import { PageHeader } from './PageHeader'
import { PrintButton } from './PrintButton'
import { StatusTag } from './StatusTag'
import { VoidButton } from './VoidButton'

interface Doc {
  id: number
  status: 'active' | 'void'
  void_reason: string | null
  invoice_id?: number | null
}

export interface DocFormProps<T, P> {
  doc?: T
  preset?: P
  onDone: () => void
}

interface Props<T extends Doc, P> {
  title: string
  subtitle?: string
  endpoint: string
  columns: ColumnsType<T>
  createPerm: string
  updatePerm: string
  voidPerm: string
  docLabel: (d: T) => string
  Form: ComponentType<DocFormProps<T, P>>
  /** One "New …" button per entry; `preset` is handed to the form (e.g. direction in/out). */
  newButtons: { label: string; preset?: P }[]
  filters?: { param: string; placeholder: string; options: Option[] }[]
  printUrl?: (d: T) => string
  modalWidth?: number
  /** Documents without an edit flow (e.g. invoices are voided and re-issued). */
  editable?: boolean
  expandedRender?: (d: T) => React.ReactNode
}

/** Date-range filtered list with create / edit / void / print, used by every non-challan document. */
export function DocPage<T extends Doc, P = undefined>({
  title, subtitle, endpoint, columns, createPerm, updatePerm, voidPerm, docLabel, Form, newButtons, filters = [], printUrl, modalWidth = 720, editable = true, expandedRender,
}: Props<T, P>) {
  const canCreate = usePermission(createPerm)
  const canUpdate = usePermission(updatePerm)
  const [range, setRange] = useState<DateRange>([startOfMonth(), today()])
  const [extra, setExtra] = useState<Record<string, number | null>>({})
  const [status, setStatus] = useState<string | undefined>()
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState<{ doc?: T; preset?: P } | null>(null)
  const { data, isLoading } = usePage<T>(endpoint, { from: range[0], to: range[1], status, page, size: 25, ...extra })

  const cols: ColumnsType<T> = [
    ...columns,
    { title: 'Status', key: 'status', render: (_, d) => <StatusTag status={d.status} reason={d.void_reason} /> },
    {
      title: '',
      key: 'actions',
      align: 'right',
      render: (_, d) => (
        <Space size={4}>
          {printUrl && <PrintButton url={printUrl(d)} />}
          {editable && canUpdate && d.status === 'active' && (
            <Button size="small" icon={<EditOutlined />} disabled={Boolean(d.invoice_id)} title={d.invoice_id ? 'On an invoice: void the invoice first' : 'Edit'} onClick={() => setModal({ doc: d })} />
          )}
          {d.status === 'active' && (
            <VoidButton path={`${endpoint}/${d.id}`} perm={voidPerm} label={docLabel(d)} disabled={Boolean(d.invoice_id)} disabledReason="On an invoice: void the invoice first" />
          )}
        </Space>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title={title}
        subtitle={subtitle}
        extra={canCreate && newButtons.map((b, i) => (
          <Button key={b.label} type={i === 0 ? 'primary' : 'default'} icon={<PlusOutlined />} onClick={() => setModal({ preset: b.preset })}>{b.label}</Button>
        ))}
      />
      <Space wrap style={{ marginBottom: 12 }}>
        <DateRangeField value={range} onChange={(r) => { setRange(r); setPage(1) }} />
        {filters.map((f) => (
          <div key={f.param} style={{ width: 210 }}>
            <EntitySelect options={f.options} value={extra[f.param]} placeholder={f.placeholder} onChange={(v) => { setExtra((e) => ({ ...e, [f.param]: v })); setPage(1) }} />
          </div>
        ))}
        <Select allowClear placeholder="Any status" style={{ width: 130 }} value={status} onChange={(v) => { setStatus(v); setPage(1) }} options={[{ value: 'active', label: 'Active' }, { value: 'void', label: 'Void' }]} />
      </Space>
      <Table<T>
        size="small"
        rowKey="id"
        loading={isLoading}
        columns={cols}
        dataSource={data?.items ?? []}
        scroll={{ x: 'max-content' }}
        rowClassName={(d) => (d.status === 'void' ? 'row-void' : '')}
        expandable={expandedRender ? { expandedRowRender: expandedRender, rowExpandable: (d) => d.status === 'active' } : undefined}
        pagination={{ current: page, pageSize: 25, total: data?.total ?? 0, onChange: setPage, showSizeChanger: false, hideOnSinglePage: true }}
      />
      <Modal open={modal !== null} title={modal?.doc ? `Edit ${docLabel(modal.doc)}` : title} footer={null} width={modalWidth} onCancel={() => setModal(null)} destroyOnClose>
        {modal && <Form doc={modal.doc} preset={modal.preset} onDone={() => setModal(null)} />}
      </Modal>
    </>
  )
}
