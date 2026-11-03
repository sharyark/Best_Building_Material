import { zodResolver } from '@hookform/resolvers/zod'
import { Col, Input, Radio, Row, Select, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useForm, useWatch } from 'react-hook-form'
import { useGet, useSave } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Expense, MoneyAccount } from '@/api/types'
import { DateField } from '@/components/DateField'
import { MoneyInput, QtyInput } from '@/components/DecimalInput'
import { DocFormShell } from '@/components/DocFormShell'
import { DocPage, type DocFormProps } from '@/components/DocPage'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Field } from '@/components/Field'
import { Money } from '@/components/Money'
import { formatDate, today } from '@/lib/date'
import { formatCurrency, formatQty, toNumber } from '@/lib/format'
import { expenseSchema, type ExpenseForm } from '@/lib/schemas'

const LABEL: Record<string, string> = { diesel: 'Fuel (diesel)', food: 'Food (khana)' }
const CATEGORIES = ['diesel', 'food', 'repair', 'tyre', 'insurance', 'toll', 'office', 'misc'].map((c) => ({ value: c, label: LABEL[c] ?? c }))
/** litres x rate, rounded to paisa like the server. */
const fuelAmount = (litres: unknown, rate: unknown) => Math.round(toNumber(litres as string) * toNumber(rate as string) * 100) / 100
type Preset = { category: ExpenseForm['category'] }
/** Day-to-day spending (khana, diesel) comes out of the galla, so cash is the default, not the bank. */
const cashFirst = (accounts: MoneyAccount[]) => (accounts.find((a) => a.kind === 'cash') ?? accounts[0])?.id

function ExpenseFormView({ doc, preset, onDone }: DocFormProps<Expense, Preset>) {
  const lookups = useLookups()
  const clientRef = useRef(crypto.randomUUID())
  const [editReason, setEditReason] = useState('')
  const { control, handleSubmit, setValue } = useForm<ExpenseForm>({
    resolver: zodResolver(expenseSchema),
    defaultValues: {
      date: doc?.date ?? today(), category: doc?.category ?? preset?.category ?? 'diesel', vehicle_id: doc?.vehicle_id ?? null,
      amount: doc ? String(doc.amount) : '', litres: doc?.litres ? String(doc.litres) : '', rate_per_litre: doc?.rate_per_litre ? String(doc.rate_per_litre) : '', meter_reading: doc?.meter_reading ? String(doc.meter_reading) : '',
      paid_via: doc?.paid_via ?? 'money_account', money_account_id: doc?.money_account_id ?? cashFirst(lookups.moneyAccounts) ?? null,
      party_id: doc?.party_id ?? null, notes: doc?.notes ?? '',
    },
  })
  const [category, paidVia, partyId, litres, rate] = useWatch({ control, name: ['category', 'paid_via', 'party_id', 'litres', 'rate_per_litre'] })
  // Opened from a shortcut before the cash/bank list loaded: fill the cash account once it arrives.
  const [moneyAccountId] = useWatch({ control, name: ['money_account_id'] })
  const firstAccount = cashFirst(lookups.moneyAccounts)
  useEffect(() => {
    if (!doc && !moneyAccountId && firstAccount) setValue('money_account_id', firstAccount)
  }, [doc, moneyAccountId, firstAccount, setValue])
  const fuel = category === 'diesel'
  // Old fuel entries saved before rates were kept have only an amount; they stay editable that way.
  const byRate = fuel && (!doc || doc.rate_per_litre !== null)
  // The pump's last price per litre, so the munshi usually only types the litres.
  const rateTyped = useRef(Boolean(doc))
  const { data: lastRate } = useGet<{ rate_per_litre: string | null }>('/expenses/fuel-rate', { party_id: paidVia === 'party_credit' ? partyId ?? undefined : undefined }, { enabled: byRate && !doc })
  useEffect(() => {
    if (!rateTyped.current && lastRate?.rate_per_litre) setValue('rate_per_litre', String(lastRate.rate_per_litre))
  }, [lastRate, setValue])
  const computed = fuelAmount(litres, rate)
  const save = useSave<object>(doc ? 'put' : 'post', doc ? `/expenses/${doc.id}` : '/expenses', { successMessage: 'Expense saved', onSuccess: onDone })

  return (
    <DocFormShell
      editReason={doc ? { value: editReason, onChange: setEditReason } : undefined}
      saving={save.isPending}
      onSubmit={handleSubmit((v) =>
        save.mutate({
          ...v,
          vehicle_id: v.vehicle_id || null,
          // fuel by rate: the server works out litres x rate
          amount: byRate && Number(v.rate_per_litre) > 0 ? null : v.amount,
          rate_per_litre: byRate && Number(v.rate_per_litre) > 0 ? v.rate_per_litre : null,
          litres: v.category === 'diesel' && v.litres ? v.litres : null,
          meter_reading: v.meter_reading || null,
          money_account_id: v.paid_via === 'money_account' ? v.money_account_id : null,
          party_id: v.paid_via === 'party_credit' ? v.party_id : null,
          notes: v.notes || null,
          ...(doc ? { edit_reason: editReason.trim() } : { client_ref: clientRef.current }),
        }),
      )}
    >
      <Row gutter={12}>
        <Col xs={24} sm={8}><Field control={control} name="date" label="Date" required>{(f) => <DateField id={f.id} value={f.value} onChange={f.onChange} />}</Field></Col>
        <Col xs={24} sm={8}><Field control={control} name="category" label="Category" required>{(f) => <Select {...f} options={CATEGORIES} />}</Field></Col>
        <Col xs={24} sm={8}><Field control={control} name="vehicle_id" label="Vehicle (cost centre)">{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.vehicles)} value={f.value} onChange={f.onChange} autoFocus placeholder="None / general" />}</Field></Col>
        {byRate ? (
          <>
            <Col xs={12} sm={8}><Field control={control} name="litres" label="Litres" required>{(f) => <QtyInput {...f} value={f.value ?? ''} addonAfter="L" size="large" />}</Field></Col>
            <Col xs={12} sm={8}>
              <Field control={control} name="rate_per_litre" label="Rate per litre" required extra={!doc && lastRate?.rate_per_litre ? (paidVia === 'party_credit' && partyId ? 'Last rate from this pump' : 'Last rate entered') : undefined}>
                {(f) => <MoneyInput {...f} value={f.value ?? ''} size="large" onChange={(v) => { rateTyped.current = true; f.onChange(v) }} />}
              </Field>
            </Col>
            <Col xs={24} sm={8}>
              <div className="fuel-total" aria-live="polite">
                <Typography.Text type="secondary">Amount</Typography.Text>
                <div className="fuel-total-value">{computed > 0 ? formatCurrency(computed) : '-'}</div>
                {computed > 0 && <Typography.Text type="secondary" style={{ fontSize: 12 }}>{formatQty(litres ?? '')} L × {formatCurrency(rate ?? '')}</Typography.Text>}
              </div>
            </Col>
            <Col xs={24} sm={8}><Field control={control} name="meter_reading" label="Meter reading (km / hours)">{(f) => <QtyInput {...f} value={f.value ?? ''} />}</Field></Col>
          </>
        ) : (
          <>
            <Col xs={24} sm={fuel ? 8 : 24}><Field control={control} name="amount" label="Amount" required>{(f) => <MoneyInput {...f} value={f.value ?? ''} size="large" />}</Field></Col>
            {fuel && (
              <>
                <Col xs={12} sm={8}><Field control={control} name="litres" label="Litres">{(f) => <QtyInput {...f} value={f.value ?? ''} addonAfter="L" />}</Field></Col>
                <Col xs={12} sm={8}><Field control={control} name="meter_reading" label="Meter reading (km / hours)">{(f) => <QtyInput {...f} value={f.value ?? ''} />}</Field></Col>
              </>
            )}
          </>
        )}
        <Col xs={24}>
          <Field control={control} name="paid_via" label="Paid">
            {(f) => <Radio.Group {...f} optionType="button" buttonStyle="solid" onChange={(e) => f.onChange(e.target.value)} options={[{ value: 'money_account', label: 'Now: cash / bank' }, { value: 'party_credit', label: 'Udhaar (pump / workshop)' }]} />}
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
  // /expenses?new=food (dashboard shortcut) opens the khana entry straight away
  const [search] = useSearchParams()
  const shortcut = search.get('new')
  const autoOpen = shortcut === 'food' || shortcut === 'diesel' ? { preset: { category: shortcut } as Preset } : undefined
  const columns: ColumnsType<Expense> = [
    { title: 'Voucher', dataIndex: 'voucher_no' },
    { title: 'Date', dataIndex: 'date', render: formatDate },
    { title: 'Category', dataIndex: 'category', render: (c: string) => <Tag color={c === 'diesel' ? 'gold' : c === 'food' ? 'green' : 'default'}>{c === 'diesel' ? 'fuel' : c === 'food' ? 'khana' : c}</Tag> },
    { title: 'Vehicle', dataIndex: 'vehicle_id', render: (id: number | null) => (id ? lookups.vehicleById.get(id)?.name : '') },
    { title: 'Litres', dataIndex: 'litres', align: 'right', render: (v) => (v ? formatQty(v) : '') },
    { title: 'Rate / L', dataIndex: 'rate_per_litre', align: 'right', render: (v) => (v ? <Money value={v} /> : '') },
    { title: 'Paid via', render: (_, e) => (e.paid_via === 'party_credit' ? `Udhaar: ${lookups.partyById.get(e.party_id ?? 0)?.name ?? ''}` : lookups.moneyAccountById.get(e.money_account_id ?? 0)?.name) },
    { title: 'Amount', dataIndex: 'amount', align: 'right', render: (v) => <Money value={v} bold /> },
  ]
  return (
    <DocPage<Expense, Preset>
      title="Expenses & diesel"
      subtitle="Fuel for each vehicle (litres x rate, cash or pump udhaar), nightly khana, repair, tyre, toll and other expenses"
      endpoint="/expenses"
      columns={columns}
      createPerm="expense.create"
      updatePerm="expense.update"
      voidPerm="expense.void"
      docLabel={(d) => `expense ${d.voucher_no}`}
      Form={ExpenseFormView}
      autoOpen={autoOpen}
      newButtons={[{ label: 'Fuel entry', preset: { category: 'diesel' } }, { label: 'Khana (food)', preset: { category: 'food' } }, { label: 'Other expense', preset: { category: 'repair' } }]}
      filters={[{ param: 'vehicle_id', placeholder: 'All vehicles', options: optionsOf(lookups.allVehicles) }]}
    />
  )
}
