import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { zodResolver } from '@hookform/resolvers/zod'
import { Button, Col, Input, Radio, Row, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useRef, useState } from 'react'
import { useFieldArray, useForm, useWatch } from 'react-hook-form'
import { useLookups } from '@/api/lookups'
import { useSave } from '@/api/hooks'
import type { Purchase } from '@/api/types'
import { DateField } from '@/components/DateField'
import { MoneyInput, QtyInput } from '@/components/DecimalInput'
import { DocFormShell } from '@/components/DocFormShell'
import { DocPage, type DocFormProps } from '@/components/DocPage'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Field } from '@/components/Field'
import { Money } from '@/components/Money'
import { QuickAddParty } from '@/components/QuickAdd'
import { usePermission } from '@/hooks/usePermission'
import { formatDate, today } from '@/lib/date'
import { formatQty, toNumber } from '@/lib/format'
import { purchaseSchema, type PurchaseForm } from '@/lib/schemas'

function PurchaseFormView({ doc, onDone }: DocFormProps<Purchase, undefined>) {
  const lookups = useLookups()
  const clientRef = useRef(crypto.randomUUID())
  const canAdd = usePermission('masters.write')
  const [adding, setAdding] = useState<string | null>(null)
  const { control, handleSubmit, setValue, getValues } = useForm<PurchaseForm>({
    resolver: zodResolver(purchaseSchema),
    defaultValues: doc
      ? {
          date: doc.date, supplier_id: doc.supplier_id, supplier_slip_no: doc.supplier_slip_no ?? '', transport_by: doc.transport_by,
          vehicle_id: doc.vehicle_id, driver_id: doc.driver_id, notes: doc.notes ?? '',
          lines: doc.lines.map((l) => ({ material_id: l.material_id, qty: String(l.qty), rate: String(l.rate) })),
        }
      : { date: today(), transport_by: 'supplier', supplier_slip_no: '', notes: '', lines: [{ material_id: undefined as unknown as number, qty: '', rate: '' }] },
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' })
  const lines = useWatch({ control, name: 'lines' })
  const transportBy = useWatch({ control, name: 'transport_by' })
  const total = lines.reduce((s, l) => s + toNumber(l?.qty) * toNumber(l?.rate), 0)
  const save = useSave<object>(doc ? 'put' : 'post', doc ? `/purchases/${doc.id}` : '/purchases', { successMessage: 'Purchase saved', onSuccess: onDone })

  return (
    <DocFormShell
      saving={save.isPending}
      onSubmit={handleSubmit((v) =>
        save.mutate({ ...v, supplier_slip_no: v.supplier_slip_no || null, notes: v.notes || null, vehicle_id: transportBy === 'own' ? v.vehicle_id || null : null, driver_id: transportBy === 'own' ? v.driver_id || null : null, ...(doc ? {} : { client_ref: clientRef.current }) }),
      )}
      extra={<Typography.Text>Total: <Typography.Text strong><Money value={total} /></Typography.Text></Typography.Text>}
    >
      <Row gutter={12}>
        <Col xs={24} sm={8}><Field control={control} name="date" label="Date" required>{(f) => <DateField id={f.id} value={f.value} onChange={f.onChange} />}</Field></Col>
        <Col xs={24} sm={16}><Field control={control} name="supplier_id" label="Supplier" required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.suppliers)} value={f.value} onChange={f.onChange} allowClear={false} autoFocus addLabel="New supplier" onAdd={canAdd ? (n) => setAdding(n) : undefined} />}</Field></Col>
        <Col xs={24} sm={8}><Field control={control} name="supplier_slip_no" label="Supplier slip no.">{(f) => <Input {...f} value={f.value ?? ''} />}</Field></Col>
        <Col xs={24} sm={16}>
          <Field control={control} name="transport_by" label="Brought by">
            {(f) => <Radio.Group {...f} onChange={(e) => { f.onChange(e.target.value); if (e.target.value === 'supplier') { setValue('vehicle_id', null); setValue('driver_id', null) } }} options={[{ value: 'supplier', label: 'Supplier delivered' }, { value: 'own', label: 'Our own vehicle' }]} />}
          </Field>
        </Col>
        {transportBy === 'own' && (
          <>
            <Col xs={24} sm={12}><Field control={control} name="vehicle_id" label="Vehicle">{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.vehicles)} value={f.value} onChange={f.onChange} />}</Field></Col>
            <Col xs={24} sm={12}><Field control={control} name="driver_id" label="Driver">{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.drivers)} value={f.value} onChange={f.onChange} />}</Field></Col>
          </>
        )}
      </Row>
      <Typography.Text strong>Materials</Typography.Text>
      {fields.map((field, i) => (
        <Row gutter={8} key={field.id} align="top" style={{ marginTop: 8 }}>
          <Col xs={24} sm={10}>
            <Field control={control} name={`lines.${i}.material_id`}>
              {(f) => <EntitySelect id={f.id} options={optionsOf(lookups.materials, (m) => `${m.name} (${m.unit})`)} value={f.value as number} allowClear={false} placeholder="Material"
                onChange={(v) => { f.onChange(v); const m = lookups.materialById.get(v as number); if (m && !getValues(`lines.${i}.rate`)) setValue(`lines.${i}.rate`, String(m.default_purchase_rate)) }} />}
            </Field>
          </Col>
          <Col xs={10} sm={6}><Field control={control} name={`lines.${i}.qty`}>{(f) => <QtyInput {...f} value={f.value as string} placeholder="Qty" />}</Field></Col>
          <Col xs={10} sm={6}><Field control={control} name={`lines.${i}.rate`}>{(f) => <MoneyInput {...f} value={f.value as string} placeholder="Rate" />}</Field></Col>
          <Col xs={4} sm={2}><Button danger type="text" icon={<DeleteOutlined />} aria-label="Remove line" disabled={fields.length === 1} onClick={() => remove(i)} /></Col>
        </Row>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} style={{ margin: '4px 0 16px' }} onClick={() => append({ material_id: undefined as unknown as number, qty: '', rate: '' })}>Add material</Button>
      <QuickAddParty open={adding !== null} type="supplier" initialName={adding ?? ''} onClose={() => setAdding(null)} onCreated={(p) => setValue('supplier_id', p.id, { shouldValidate: true })} />
    </DocFormShell>
  )
}

export default function PurchasesPage() {
  const lookups = useLookups()
  const columns: ColumnsType<Purchase> = [
    { title: 'Bill', dataIndex: 'bill_no' },
    { title: 'Date', dataIndex: 'date', render: formatDate },
    { title: 'Supplier', dataIndex: 'supplier_id', render: (id: number) => lookups.partyById.get(id)?.name },
    { title: 'Slip', dataIndex: 'supplier_slip_no' },
    { title: 'Materials', render: (_, p) => <Table size="small" pagination={false} showHeader={false} rowKey="id" dataSource={p.lines} columns={[{ render: (_, l) => `${lookups.materialById.get(l.material_id)?.name ?? ''}: ${formatQty(l.qty)} × ${l.rate}` }]} /> },
    { title: 'Brought by', dataIndex: 'transport_by' },
    { title: 'Total', dataIndex: 'total', align: 'right', render: (v) => <Money value={v} bold /> },
  ]
  return (
    <DocPage<Purchase>
      title="Purchases into yard"
      subtitle="Material bought from crusher / bhatta / dealer and stocked in the yard"
      endpoint="/purchases"
      columns={columns}
      createPerm="purchase.create"
      updatePerm="purchase.update"
      voidPerm="purchase.void"
      docLabel={(d) => `purchase ${d.bill_no}`}
      Form={PurchaseFormView}
      newButtons={[{ label: 'New purchase' }]}
      filters={[{ param: 'supplier_id', placeholder: 'All suppliers', options: optionsOf(lookups.suppliers) }]}
      modalWidth={860}
    />
  )
}
