import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Col, InputNumber, Row, Space, Switch, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useMemo, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { useGet, useSave } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Invoice, InvoiceDetail, Uninvoiced } from '@/api/types'
import { DateField, DateRangeField, type DateRange } from '@/components/DateField'
import { DocFormShell } from '@/components/DocFormShell'
import { DocPage, type DocFormProps } from '@/components/DocPage'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Field } from '@/components/Field'
import { Money } from '@/components/Money'
import { API_DATE, formatDate, today } from '@/lib/date'
import { formatQty, toNumber } from '@/lib/format'

const schema = z.object({ date: z.string().min(1), customer_id: z.number({ required_error: 'Required', invalid_type_error: 'Required' }), site_id: z.number().nullable().optional() })

function InvoiceCreate({ onDone }: DocFormProps<Invoice, undefined>) {
  const lookups = useLookups()
  const clientRef = useRef(crypto.randomUUID())
  const [range, setRange] = useState<DateRange>([dayjs().startOf('month').format(API_DATE), today()])
  const [picked, setPicked] = useState<Set<string> | null>(null) // "d:12" / "r:7"; null = everything selected
  const [tax, setTax] = useState(false)
  const [rate, setRate] = useState(5)
  const { control, handleSubmit, watch } = useForm<{ date: string; customer_id: number; site_id?: number | null }>({
    resolver: zodResolver(schema), defaultValues: { date: today(), site_id: null },
  })
  const customerId = watch('customer_id')
  const siteId = watch('site_id')
  const { data, isFetching } = useGet<Uninvoiced>('/invoices/uninvoiced', { customer_id: customerId, date_from: range[0], date_to: range[1], site_id: siteId }, { enabled: Boolean(customerId) })
  const sites = lookups.sites.filter((s) => s.party_id === customerId)
  const save = useSave<object, InvoiceDetail>('post', '/invoices', { successMessage: 'Bill created', onSuccess: onDone })

  const rows = useMemo(() => [
    ...(data?.deliveries ?? []).map((d) => ({ key: `d:${d.id}`, id: d.id, kind: 'challan', no: d.challan_no, date: d.date, what: `${lookups.materialById.get(d.material_id)?.name ?? ''} ${formatQty(d.qty)} ${d.unit}`, amount: toNumber(d.sale_amount) + toNumber(d.freight_amount) })),
    ...(data?.rentals ?? []).map((r) => ({ key: `r:${r.id}`, id: r.id, kind: 'rental', no: r.rental_no, date: r.date, what: `${lookups.vehicleById.get(r.vehicle_id)?.name ?? ''} ${formatQty(r.qty)} ${r.basis}`, amount: toNumber(r.amount) })),
  ], [data, lookups.materialById, lookups.vehicleById])
  const selected = rows.filter((r) => (picked ? picked.has(r.key) : true))
  const subtotal = selected.reduce((s, r) => s + r.amount, 0)
  const taxAmount = tax ? subtotal * rate / 100 : 0

  return (
    <DocFormShell
      saving={save.isPending}
      onSubmit={handleSubmit((v) => {
        save.mutate({
          date: v.date, customer_id: v.customer_id, site_id: v.site_id || null, period_from: range[0], period_to: range[1],
          delivery_ids: selected.filter((r) => r.kind === 'challan').map((r) => r.id),
          rental_ids: selected.filter((r) => r.kind === 'rental').map((r) => r.id),
          is_tax_invoice: tax, tax_rate: tax ? String(rate) : '0', client_ref: clientRef.current,
        })
      })}
      extra={<Typography.Text>Subtotal <Money value={subtotal} /> + tax <Money value={taxAmount} /> = <Typography.Text strong><Money value={subtotal + taxAmount} /></Typography.Text></Typography.Text>}
    >
      <Row gutter={12}>
        <Col xs={24} sm={8}><Field control={control} name="date" label="Bill date" required>{(f) => <DateField id={f.id} value={f.value} onChange={f.onChange} />}</Field></Col>
        <Col xs={24} sm={16}><Field control={control} name="customer_id" label="Customer" required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.customers)} value={f.value} onChange={(v) => { f.onChange(v); setPicked(null) }} allowClear={false} autoFocus />}</Field></Col>
        <Col xs={24} sm={12}><Field control={control} name="site_id" label="Site (optional)">{(f) => <EntitySelect id={f.id} options={optionsOf(sites)} value={f.value} onChange={(v) => { f.onChange(v); setPicked(null) }} disabled={!customerId} placeholder="All sites" />}</Field></Col>
        <Col xs={24} sm={12}><div style={{ marginBottom: 12 }}><div style={{ marginBottom: 8 }}>Period</div><DateRangeField value={range} onChange={(r) => { setRange(r); setPicked(null) }} /></div></Col>
      </Row>
      <Table size="small" rowKey="key" loading={isFetching} pagination={false} dataSource={rows} scroll={{ x: 'max-content', y: 280 }}
        locale={{ emptyText: customerId ? 'Nothing un-billed in this period' : 'Pick a customer to list their un-billed challans and rentals' }}
        rowSelection={{ selectedRowKeys: selected.map((r) => r.key), onChange: (keys) => setPicked(new Set(keys as string[])) }}
        columns={[
          { title: 'No.', dataIndex: 'no' },
          { title: 'Date', dataIndex: 'date', render: formatDate },
          { title: 'Type', dataIndex: 'kind', render: (k: string) => <Tag>{k}</Tag> },
          { title: 'Details', dataIndex: 'what' },
          { title: 'Amount', dataIndex: 'amount', align: 'right', render: (v) => <Money value={v} /> },
        ]}
      />
      <Space style={{ margin: '12px 0' }} wrap>
        <Switch checked={tax} onChange={setTax} /> Tax invoice
        {tax && <>Tax rate <InputNumber min={0.01} max={100} value={rate} onChange={(v) => setRate(v ?? 0)} addonAfter="%" /></>}
      </Space>
      {tax && <Alert type="info" showIcon message="Tax is posted to Output Tax Payable and added to the customer's khata. Which customers need a tax invoice, and the rate, are still open questions for the client." style={{ marginBottom: 12 }} />}
    </DocFormShell>
  )
}

function Lines({ inv }: { inv: Invoice }) {
  const { data, isLoading } = useGet<InvoiceDetail>(`/invoices/${inv.id}`)
  return (
    <Table size="small" rowKey={(l) => `${l.kind}${l.doc_id}`} loading={isLoading} pagination={false} dataSource={data?.lines ?? []}
      columns={[
        { title: 'Doc', dataIndex: 'doc_no' },
        { title: 'Date', dataIndex: 'date', render: formatDate },
        { title: 'Details', dataIndex: 'description' },
        { title: 'Qty', align: 'right', render: (_, l) => `${formatQty(l.qty)} ${l.unit}` },
        { title: 'Rate', dataIndex: 'rate', align: 'right', render: (v) => <Money value={v} /> },
        { title: 'Amount', dataIndex: 'amount', align: 'right', render: (v) => <Money value={v} /> },
      ]}
    />
  )
}

export default function InvoicesPage() {
  const lookups = useLookups()
  const columns: ColumnsType<Invoice> = [
    { title: 'Bill no.', dataIndex: 'invoice_no' },
    { title: 'Date', dataIndex: 'date', render: formatDate },
    { title: 'Customer', dataIndex: 'customer_id', render: (id: number) => lookups.partyById.get(id)?.name },
    { title: 'Period', render: (_, i) => `${formatDate(i.period_from)} – ${formatDate(i.period_to)}` },
    { title: 'Type', dataIndex: 'is_tax_invoice', render: (t: boolean) => (t ? <Tag color="blue">Tax invoice</Tag> : <Tag>Bill</Tag>) },
    { title: 'Subtotal', dataIndex: 'subtotal', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Tax', dataIndex: 'tax_amount', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Total', dataIndex: 'total', align: 'right', render: (v) => <Money value={v} bold /> },
  ]
  return (
    <DocPage<Invoice>
      title="Bills & invoices"
      subtitle="Group challans and rentals into a weekly / monthly bill, with optional tax"
      endpoint="/invoices"
      columns={columns}
      createPerm="invoice.create"
      updatePerm="invoice.create"
      voidPerm="invoice.void"
      docLabel={(d) => `invoice ${d.invoice_no}`}
      Form={InvoiceCreate}
      newButtons={[{ label: 'Create bill' }]}
      filters={[{ param: 'customer_id', placeholder: 'All customers', options: optionsOf(lookups.customers) }]}
      printUrl={(d) => `/invoices/${d.id}/pdf`}
      editable={false}
      expandedRender={(d) => <Lines inv={d} />}
      modalWidth={900}
    />
  )
}
