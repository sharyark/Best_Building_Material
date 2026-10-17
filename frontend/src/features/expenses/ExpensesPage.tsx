import { zodResolver } from '@hookform/resolvers/zod'
import { Col, Input, Radio, Row, Select, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useRef } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useSave } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Expense } from '@/api/types'
import { DateField } from '@/components/DateField'
import { MoneyInput, QtyInput } from '@/components/DecimalInput'
import { DocFormShell } from '@/components/DocFormShell'
import { DocPage, type DocFormProps } from '@/components/DocPage'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Field } from '@/components/Field'
import { Money } from '@/components/Money'
import { formatDate, today } from '@/lib/date'
import { formatQty } from '@/lib/format'
import { expenseSchema, type ExpenseForm } from '@/lib/schemas'

const CATEGORIES = ['diesel', 'repair', 'tyre', 'insurance', 'toll', 'office', 'misc'].map((c) => ({ value: c, label: c }))
type Preset = { category: ExpenseForm['category'] }

function ExpenseFormView({ doc, preset, onDone }: DocFormProps<Expense, Preset>) {
  const lookups = useLookups()
  const clientRef = useRef(crypto.randomUUID())
  const { control, handleSubmit } = useForm<ExpenseForm>({
    resolver: zodResolver(expenseSchema),
    defaultValues: {
      date: doc?.date ?? today(), category: doc?.category ?? preset?.category ?? 'diesel', vehicle_id: doc?.vehicle_id ?? null,
      amount: doc ? String(doc.amount) : '', litres: doc?.litres ? String(doc.litres) : '', meter_reading: doc?.meter_reading ? String(doc.meter_reading) : '',
      paid_via: doc?.paid_via ?? 'money_account', money_account_id: doc?.money_account_id ?? lookups.moneyAccounts[0]?.id ?? null,
      party_id: doc?.party_id ?? null, notes: doc?.notes ?? '',
    },
  })
  const [category, paidVia] = useWatch({ control, name: ['category', 'paid_via'] })
  const save = useSave<object>(doc ? 'put' : 'post', doc ? `/expenses/${doc.id}` : '/expenses', { successMessage: 'Expense saved', onSuccess: onDone })

  return (
    <DocFormShell
      saving={save.isPending}
      onSubmit={handleSubmit((v) =>
        save.mutate({
          ...v,
          vehicle_id: v.vehicle_id || null,
          litres: v.category === 'diesel' && v.litres ? v.litres : null,
          meter_reading: v.meter_reading || null,
          money_account_id: v.paid_via === 'money_account' ? v.money_account_id : null,
          party_id: v.paid_via === 'party_credit' ? v.party_id : null,
          notes: v.notes || null,
          ...(doc ? {} : { client_ref: clientRef.current }),
        }),
      )}
    >
      <Row gutter={12}>
        <Col xs={24} sm={8}><Field control={control} name="date" label="Date" required>{(f) => <DateField id={f.id} value={f.value} onChange={f.onChange} />}</Field></Col>
        <Col xs={24} sm={8}><Field control={control} name="category" label="Category" required>{(f) => <Select {...f} options={CATEGORIES} />}</Field></Col>
        <Col xs={24} sm={8}><Field control={control} name="vehicle_id" label="Vehicle (cost centre)">{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.vehicles)} value={f.value} onChange={f.onChange} autoFocus placeholder="None / general" />}</Field></Col>
        <Col xs={24} sm={category === 'diesel' ? 8 : 24}><Field control={control} name="amount" label="Amount" required>{(f) => <MoneyInput {...f} size="large" />}</Field></Col>
        {category === 'diesel' && (
          <>
            <Col xs={12} sm={8}><Field control={control} name="litres" label="Litres">{(f) => <QtyInput {...f} value={f.value ?? ''} addonAfter="L" />}</Field></Col>
            <Col xs={12} sm={8}><Field control={control} name="meter_reading" label="Meter reading (km / hours)">{(f) => <QtyInput {...f} value={f.value ?? ''} />}</Field></Col>
          </>
        )}
        <Col xs={24}>
          <Field control={control} name="paid_via" label="Paid">
            {(f) => <Radio.Group {...f} optionType="button" buttonStyle="solid" onChange={(e) => f.onChange(e.target.value)} options={[{ value: 'money_account', label: 'Now: cash / bank' }, { value: 'party_credit', label: 'On credit (pump / workshop)' }]} />}
          </Field>
        </Col>
        <Col xs={24}>
          {paidVia === 'money_account' ? (
            <Field control={control} name="money_account_id" label="Paid from" required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.moneyAccounts)} value={f.value} onChange={f.onChange} allowClear={false} />}</Field>
          ) : (
            <Field control={control} name="party_id" label="Pump / workshop" required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.suppliers)} value={f.value} onChange={f.onChange} allowClear={false} />}</Field>
          )}
        </Col>
        <Col xs={24}><Field control={control} name="notes" label="Notes">{(f) => <Input {...f} value={f.value ?? ''} />}</Field></Col>
      </Row>
    </DocFormShell>
  )
}

export default function ExpensesPage() {
  const lookups = useLookups()
  const columns: ColumnsType<Expense> = [
    { title: 'Voucher', dataIndex: 'voucher_no' },
    { title: 'Date', dataIndex: 'date', render: formatDate },
    { title: 'Category', dataIndex: 'category', render: (c: string) => <Tag color={c === 'diesel' ? 'gold' : 'default'}>{c}</Tag> },
    { title: 'Vehicle', dataIndex: 'vehicle_id', render: (id: number | null) => (id ? lookups.vehicleById.get(id)?.name : '') },
    { title: 'Litres', dataIndex: 'litres', align: 'right', render: (v) => (v ? formatQty(v) : '') },
    { title: 'Paid via', render: (_, e) => (e.paid_via === 'party_credit' ? `Credit: ${lookups.partyById.get(e.party_id ?? 0)?.name ?? ''}` : lookups.moneyAccountById.get(e.money_account_id ?? 0)?.name) },
    { title: 'Amount', dataIndex: 'amount', align: 'right', render: (v) => <Money value={v} bold /> },
  ]
  return (
    <DocPage<Expense, Preset>
      title="Expenses & diesel"
      subtitle="Diesel, repair, tyre, insurance, toll, office and miscellaneous"
      endpoint="/expenses"
      columns={columns}
      createPerm="expense.create"
      updatePerm="expense.update"
      voidPerm="expense.void"
      docLabel={(d) => `expense ${d.voucher_no}`}
      Form={ExpenseFormView}
      newButtons={[{ label: 'Diesel entry', preset: { category: 'diesel' } }, { label: 'Other expense', preset: { category: 'repair' } }]}
      filters={[{ param: 'vehicle_id', placeholder: 'All vehicles', options: optionsOf(lookups.allVehicles) }]}
    />
  )
}
