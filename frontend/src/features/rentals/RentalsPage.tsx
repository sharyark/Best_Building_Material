import { zodResolver } from '@hookform/resolvers/zod'
import { Col, Input, Row, Select, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useRef, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useSave } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Rental } from '@/api/types'
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
import { rentalSchema, type RentalForm } from '@/lib/schemas'

function RentalFormView({ doc, onDone }: DocFormProps<Rental, undefined>) {
  const lookups = useLookups()
  const clientRef = useRef(crypto.randomUUID())
  const canAdd = usePermission('masters.write')
  const [adding, setAdding] = useState<string | null>(null)
  const { control, handleSubmit, setValue } = useForm<RentalForm>({
    resolver: zodResolver(rentalSchema),
    defaultValues: {
      date: doc?.date ?? today(), customer_id: doc?.customer_id as number, site_id: doc?.site_id ?? null, vehicle_id: doc?.vehicle_id as number,
      operator_id: doc?.operator_id ?? null, basis: doc?.basis ?? 'hour', qty: doc ? String(doc.qty) : '', rate: doc ? String(doc.rate) : '', notes: doc?.notes ?? '',
    },
  })
  const [customerId, qty, rate, basis] = useWatch({ control, name: ['customer_id', 'qty', 'rate', 'basis'] })
  const sites = lookups.sites.filter((s) => s.party_id === customerId)
  const save = useSave<object>(doc ? 'put' : 'post', doc ? `/rentals/${doc.id}` : '/rentals', { successMessage: 'Rental saved', onSuccess: onDone })
  const machines = lookups.vehicles.filter((v) => v.type === 'loader' || v.type === 'dumper' || v.type === 'tractor_trolley')

  return (
    <DocFormShell
      saving={save.isPending}
      onSubmit={handleSubmit((v) => save.mutate({ ...v, site_id: v.site_id || null, operator_id: v.operator_id || null, notes: v.notes || null, ...(doc ? {} : { client_ref: clientRef.current }) }))}
      extra={<Typography.Text>Amount: <Typography.Text strong><Money value={toNumber(qty) * toNumber(rate)} /></Typography.Text></Typography.Text>}
    >
      <Row gutter={12}>
        <Col xs={24} sm={8}><Field control={control} name="date" label="Date" required>{(f) => <DateField id={f.id} value={f.value} onChange={f.onChange} />}</Field></Col>
        <Col xs={24} sm={16}><Field control={control} name="customer_id" label="Customer" required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.customers)} value={f.value} onChange={f.onChange} allowClear={false} autoFocus addLabel="New customer" onAdd={canAdd ? (n) => setAdding(n) : undefined} />}</Field></Col>
        <Col xs={24} sm={12}><Field control={control} name="site_id" label="Site">{(f) => <EntitySelect id={f.id} options={optionsOf(sites)} value={f.value} onChange={f.onChange} disabled={!customerId} />}</Field></Col>
        <Col xs={24} sm={12}><Field control={control} name="vehicle_id" label="Machine" required>{(f) => <EntitySelect id={f.id} options={optionsOf(machines)} value={f.value} onChange={f.onChange} allowClear={false} />}</Field></Col>
        <Col xs={24} sm={12}><Field control={control} name="operator_id" label="Operator">{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.drivers)} value={f.value} onChange={f.onChange} />}</Field></Col>
        <Col xs={24} sm={12}><Field control={control} name="basis" label="Charged per" required>{(f) => <Select {...f} options={[{ value: 'hour', label: 'Hour' }, { value: 'trip', label: 'Trip' }, { value: 'day', label: 'Day' }]} />}</Field></Col>
        <Col xs={12}><Field control={control} name="qty" label={`Quantity (${basis}s)`} required>{(f) => <QtyInput {...f} />}</Field></Col>
        <Col xs={12}><Field control={control} name="rate" label={`Rate per ${basis}`} required>{(f) => <MoneyInput {...f} />}</Field></Col>
        <Col xs={24}><Field control={control} name="notes" label="Notes">{(f) => <Input {...f} value={f.value ?? ''} />}</Field></Col>
      </Row>
      <QuickAddParty open={adding !== null} type="customer" initialName={adding ?? ''} onClose={() => setAdding(null)} onCreated={(p) => setValue('customer_id', p.id, { shouldValidate: true })} />
    </DocFormShell>
  )
}

export default function RentalsPage() {
  const lookups = useLookups()
  const columns: ColumnsType<Rental> = [
    { title: 'No.', dataIndex: 'rental_no' },
    { title: 'Date', dataIndex: 'date', render: formatDate },
    { title: 'Customer', dataIndex: 'customer_id', render: (id: number) => lookups.partyById.get(id)?.name },
    { title: 'Site', dataIndex: 'site_id', render: (id: number | null) => (id ? lookups.siteById.get(id)?.name : '') },
    { title: 'Machine', dataIndex: 'vehicle_id', render: (id: number) => lookups.vehicleById.get(id)?.name },
    { title: 'Qty', align: 'right', render: (_, r) => `${formatQty(r.qty)} ${r.basis}` },
    { title: 'Rate', dataIndex: 'rate', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Amount', dataIndex: 'amount', align: 'right', render: (v) => <Money value={v} bold /> },
  ]
  return (
    <DocPage<Rental>
      title="Equipment rental"
      subtitle="Loaders, dumper and tractors hired out per hour, trip or day"
      endpoint="/rentals"
      columns={columns}
      createPerm="rental.create"
      updatePerm="rental.update"
      voidPerm="rental.void"
      docLabel={(d) => `rental ${d.rental_no}`}
      Form={RentalFormView}
      newButtons={[{ label: 'New rental' }]}
      filters={[{ param: 'customer_id', placeholder: 'All customers', options: optionsOf(lookups.customers) }, { param: 'vehicle_id', placeholder: 'All machines', options: optionsOf(lookups.allVehicles) }]}
    />
  )
}
