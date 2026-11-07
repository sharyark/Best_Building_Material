import { zodResolver } from '@hookform/resolvers/zod'
import { Col, Input, Radio, Row, Select, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useRef, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useGet, useSave } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Payment, StaffDues } from '@/api/types'
import { DateField } from '@/components/DateField'
import { MoneyInput } from '@/components/DecimalInput'
import { DocFormShell } from '@/components/DocFormShell'
import { DocPage, type DocFormProps } from '@/components/DocPage'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Field } from '@/components/Field'
import { Money } from '@/components/Money'
import { QuickAddParty } from '@/components/QuickAdd'
import { usePermission } from '@/hooks/usePermission'
import { formatDate, today } from '@/lib/date'
import { toNumber } from '@/lib/format'
import { paymentSchema, type PaymentForm } from '@/lib/schemas'

type Preset = { direction: 'in' | 'out' }

function PaymentFormView({ doc, preset, onDone }: DocFormProps<Payment, Preset>) {
  const lookups = useLookups()
  const clientRef = useRef(crypto.randomUUID())
  const [editReason, setEditReason] = useState('')
  const canAdd = usePermission('masters.write')
  const [adding, setAdding] = useState<string | null>(null)
  const direction = doc?.direction ?? preset?.direction ?? 'in'
  const { control, handleSubmit, setValue } = useForm<PaymentForm>({
    resolver: zodResolver(paymentSchema),
    defaultValues: {
      date: doc?.date ?? today(), direction, counterparty: doc?.staff_id ? 'staff' : 'party', party_id: doc?.party_id ?? null,
      staff_id: doc?.staff_id ?? null, money_account_id: doc?.money_account_id ?? lookups.moneyAccounts[0]?.id,
      mode: doc?.mode ?? 'cash', purpose: doc?.purpose ?? 'general', ref_no: doc?.ref_no ?? '', amount: doc ? String(doc.amount) : '', notes: doc?.notes ?? '',
      trip_amount: doc?.purpose === 'sal_trip' ? String(doc.trip_amount) : '',
    },
  })
  const [counterparty, staffId, purpose, amount, tripAmount] = useWatch({ control, name: ['counterparty', 'staff_id', 'purpose', 'amount', 'trip_amount'] })
  const staffPay = counterparty === 'staff' && direction === 'out' && Boolean(staffId)
  const dues = useGet<StaffDues>(`/labour/dues/${staffId}`, undefined, { enabled: staffPay })
  const owed = dues.data?.staff_id === staffId ? dues.data : undefined
  // "Salary + trip" on a new payment: fill in everything owed, split into its two parts (once per worker).
  const filledFor = useRef<number | null>(null)
  useEffect(() => {
    if (doc || purpose !== 'sal_trip' || !owed || filledFor.current === owed.staff_id) return
    filledFor.current = owed.staff_id
    const total = toNumber(owed.total_owed)
    if (total > 0) setValue('amount', String(owed.total_owed), { shouldValidate: true })
    // An advance still owed back lowers the total, so the trip part can't be more than what is paid.
    const trip = Math.max(0, Math.min(toNumber(owed.trip_owed), total > 0 ? total : toNumber(owed.trip_owed)))
    setValue('trip_amount', trip.toFixed(2), { shouldValidate: true })
  }, [doc, purpose, owed, setValue])
  const salaryPart = toNumber(amount) - toNumber(tripAmount)
  const save = useSave<object>(doc ? 'put' : 'post', doc ? `/payments/${doc.id}` : '/payments', {
    successMessage: direction === 'in' ? 'Receipt saved' : 'Payment saved', onSuccess: onDone,
  })
  const partyOptions = direction === 'in' ? lookups.customers : lookups.suppliers

  return (
    <DocFormShell
      editReason={doc ? { value: editReason, onChange: setEditReason } : undefined}
      saving={save.isPending}
      onSubmit={handleSubmit((v) => {
        const { counterparty: who, ...rest } = v
        save.mutate({
          ...rest,
          party_id: who === 'party' ? v.party_id : null,
          staff_id: who === 'staff' ? v.staff_id : null,
          purpose: who === 'staff' ? v.purpose : 'general',
          trip_amount: who === 'staff' && v.purpose === 'sal_trip' ? v.trip_amount : null,
          ref_no: v.ref_no || null, notes: v.notes || null, ...(doc ? { edit_reason: editReason.trim() } : { client_ref: clientRef.current }),
        })
      })}
    >
      <Row gutter={12}>
        <Col xs={24} sm={8}><Field control={control} name="date" label="Date" required>{(f) => <DateField id={f.id} value={f.value} onChange={f.onChange} />}</Field></Col>
        <Col xs={24} sm={16}>
          <Field control={control} name="counterparty" label={direction === 'in' ? 'Received from' : 'Paid to'}>
            {(f) => <Radio.Group {...f} optionType="button" buttonStyle="solid" onChange={(e) => f.onChange(e.target.value)}
              options={[{ value: 'party', label: direction === 'in' ? 'Customer / party' : 'Supplier / party' }, { value: 'staff', label: 'Staff / labour' }]} />}
          </Field>
        </Col>
        {counterparty === 'party' ? (
          <Col xs={24}><Field control={control} name="party_id" label={direction === 'in' ? 'Customer' : 'Supplier'} required>{(f) => <EntitySelect id={f.id} options={optionsOf(partyOptions)} value={f.value} onChange={f.onChange} allowClear={false} autoFocus placeholder="Type name" addLabel={direction === 'in' ? 'New customer' : 'New supplier'} onAdd={canAdd ? (n) => setAdding(n) : undefined} />}</Field></Col>
        ) : (
          <>
            <Col xs={24} sm={14}><Field control={control} name="staff_id" label="Staff member" required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.staff)} value={f.value} onChange={f.onChange} allowClear={false} autoFocus />}</Field></Col>
            <Col xs={24} sm={10}>
              <Field control={control} name="purpose" label="Purpose">
                {(f) => <Select {...f} options={[{ value: 'advance', label: 'Advance (loan against wages)' }, { value: 'salary', label: 'Salary / wage payout' }, { value: 'trip', label: 'Trip money (weekly trips)' }, { value: 'sal_trip', label: 'Salary + trip money (both)' }, { value: 'general', label: 'Other' }]} />}
              </Field>
            </Col>
            {staffPay && owed && (
              <Col xs={24}>
                <Typography.Text type="secondary" style={{ display: 'block', marginTop: -6, marginBottom: 10 }}>
                  Owed now: salary {toNumber(owed.salary_owed) >= 0 ? <Money value={owed.salary_owed} /> : <>none (advance <Money value={-toNumber(owed.salary_owed)} /> to recover)</>} · trip money <Money value={owed.trip_owed} />
                </Typography.Text>
              </Col>
            )}
          </>
        )}
        <Col xs={24} sm={12}><Field control={control} name="amount" label={counterparty === 'staff' && purpose === 'sal_trip' ? 'Total amount' : 'Amount'} required>{(f) => <MoneyInput {...f} size="large" />}</Field></Col>
        {counterparty === 'staff' && purpose === 'sal_trip' && (
          <Col xs={24} sm={12}>
            <Field control={control} name="trip_amount" label="Of which trip money" required
              extra={<>Salary part: <Money value={salaryPart > 0 ? salaryPart : 0} bold /></>}>
              {(f) => <MoneyInput {...f} size="large" />}
            </Field>
          </Col>
        )}
        <Col xs={24} sm={12}><Field control={control} name="money_account_id" label={direction === 'in' ? 'Deposited to' : 'Paid from'} required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.moneyAccounts)} value={f.value} onChange={f.onChange} allowClear={false} />}</Field></Col>
        <Col xs={12}><Field control={control} name="mode" label="Mode">{(f) => <Select {...f} options={['cash', 'bank', 'cheque', 'online'].map((m) => ({ value: m, label: m }))} />}</Field></Col>
        <Col xs={12}><Field control={control} name="ref_no" label="Cheque / reference no.">{(f) => <Input {...f} value={f.value ?? ''} onChange={(e) => { f.onChange(e.target.value); if (e.target.value && !f.value) setValue('mode', 'bank') }} />}</Field></Col>
        <Col xs={24}><Field control={control} name="notes" label="Notes">{(f) => <Input {...f} value={f.value ?? ''} />}</Field></Col>
      </Row>
      <QuickAddParty open={adding !== null} type={direction === 'in' ? 'customer' : 'supplier'} initialName={adding ?? ''} onClose={() => setAdding(null)} onCreated={(p) => setValue('party_id', p.id, { shouldValidate: true })} />
    </DocFormShell>
  )
}

export default function PaymentsPage() {
  const lookups = useLookups()
  const columns: ColumnsType<Payment> = [
    { title: 'Voucher', dataIndex: 'voucher_no' },
    { title: 'Date', dataIndex: 'date', render: formatDate },
    { title: 'Type', dataIndex: 'direction', render: (d: string) => <Tag color={d === 'in' ? 'green' : 'volcano'}>{d === 'in' ? 'Receipt' : 'Payment'}</Tag> },
    { title: 'Party / staff', render: (_, p) => (p.party_id ? lookups.partyById.get(p.party_id)?.name : lookups.staffById.get(p.staff_id ?? 0)?.name) },
    { title: 'Purpose', dataIndex: 'purpose', render: (v: string) => (v === 'general' ? '' : v === 'sal_trip' ? 'salary + trip' : v) },
    { title: 'Account', dataIndex: 'money_account_id', render: (id: number) => lookups.moneyAccountById.get(id)?.name },
    { title: 'Mode', dataIndex: 'mode' },
    { title: 'Ref', dataIndex: 'ref_no' },
    { title: 'Amount', dataIndex: 'amount', align: 'right', render: (v) => <Money value={v} bold /> },
  ]
  return (
    <DocPage<Payment, Preset>
      title="Payments & receipts"
      subtitle="Money in from customers, money out to suppliers and staff"
      endpoint="/payments"
      columns={columns}
      createPerm="payment.create"
      updatePerm="payment.update"
      voidPerm="payment.void"
      docLabel={(d) => `voucher ${d.voucher_no}`}
      Form={PaymentFormView}
      newButtons={[{ label: 'New receipt (money in)', preset: { direction: 'in' } }, { label: 'New payment (money out)', preset: { direction: 'out' } }]}
      filters={[{ param: 'party_id', placeholder: 'Any party', options: optionsOf(lookups.parties) }, { param: 'staff_id', placeholder: 'Any staff', options: optionsOf(lookups.allStaff) }]}
      printUrl={(d) => `/payments/${d.id}/pdf`}
      thermalPrint
    />
  )
}
