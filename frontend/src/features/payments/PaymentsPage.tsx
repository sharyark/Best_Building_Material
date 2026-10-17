import { zodResolver } from '@hookform/resolvers/zod'
import { Col, Input, Radio, Row, Select, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useRef } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useSave } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Payment } from '@/api/types'
import { DateField } from '@/components/DateField'
import { MoneyInput } from '@/components/DecimalInput'
import { DocFormShell } from '@/components/DocFormShell'
import { DocPage, type DocFormProps } from '@/components/DocPage'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Field } from '@/components/Field'
import { Money } from '@/components/Money'
import { formatDate, today } from '@/lib/date'
import { paymentSchema, type PaymentForm } from '@/lib/schemas'

type Preset = { direction: 'in' | 'out' }

function PaymentFormView({ doc, preset, onDone }: DocFormProps<Payment, Preset>) {
  const lookups = useLookups()
  const clientRef = useRef(crypto.randomUUID())
  const direction = doc?.direction ?? preset?.direction ?? 'in'
  const { control, handleSubmit, setValue } = useForm<PaymentForm>({
    resolver: zodResolver(paymentSchema),
    defaultValues: {
      date: doc?.date ?? today(), direction, counterparty: doc?.staff_id ? 'staff' : 'party', party_id: doc?.party_id ?? null,
      staff_id: doc?.staff_id ?? null, money_account_id: doc?.money_account_id ?? lookups.moneyAccounts[0]?.id,
      mode: doc?.mode ?? 'cash', purpose: doc?.purpose ?? 'general', ref_no: doc?.ref_no ?? '', amount: doc ? String(doc.amount) : '', notes: doc?.notes ?? '',
    },
  })
  const counterparty = useWatch({ control, name: 'counterparty' })
  const save = useSave<object>(doc ? 'put' : 'post', doc ? `/payments/${doc.id}` : '/payments', {
    successMessage: direction === 'in' ? 'Receipt saved' : 'Payment saved', onSuccess: onDone,
  })
  const partyOptions = direction === 'in' ? lookups.customers : lookups.suppliers

  return (
    <DocFormShell
      saving={save.isPending}
      onSubmit={handleSubmit((v) => {
        const { counterparty: who, ...rest } = v
        save.mutate({
          ...rest,
          party_id: who === 'party' ? v.party_id : null,
          staff_id: who === 'staff' ? v.staff_id : null,
          purpose: who === 'staff' ? v.purpose : 'general',
          ref_no: v.ref_no || null, notes: v.notes || null, ...(doc ? {} : { client_ref: clientRef.current }),
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
          <Col xs={24}><Field control={control} name="party_id" label={direction === 'in' ? 'Customer' : 'Supplier'} required>{(f) => <EntitySelect id={f.id} options={optionsOf(partyOptions)} value={f.value} onChange={f.onChange} allowClear={false} autoFocus placeholder="Type name" />}</Field></Col>
        ) : (
          <>
            <Col xs={24} sm={14}><Field control={control} name="staff_id" label="Staff member" required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.staff)} value={f.value} onChange={f.onChange} allowClear={false} autoFocus />}</Field></Col>
            <Col xs={24} sm={10}>
              <Field control={control} name="purpose" label="Purpose">
                {(f) => <Select {...f} options={[{ value: 'advance', label: 'Advance (loan against wages)' }, { value: 'salary', label: 'Salary / wage payout' }, { value: 'general', label: 'Other' }]} />}
              </Field>
            </Col>
          </>
        )}
        <Col xs={24} sm={12}><Field control={control} name="amount" label="Amount" required>{(f) => <MoneyInput {...f} size="large" />}</Field></Col>
        <Col xs={24} sm={12}><Field control={control} name="money_account_id" label={direction === 'in' ? 'Deposited to' : 'Paid from'} required>{(f) => <EntitySelect id={f.id} options={optionsOf(lookups.moneyAccounts)} value={f.value} onChange={f.onChange} allowClear={false} />}</Field></Col>
        <Col xs={12}><Field control={control} name="mode" label="Mode">{(f) => <Select {...f} options={['cash', 'bank', 'cheque', 'online'].map((m) => ({ value: m, label: m }))} />}</Field></Col>
        <Col xs={12}><Field control={control} name="ref_no" label="Cheque / reference no.">{(f) => <Input {...f} value={f.value ?? ''} onChange={(e) => { f.onChange(e.target.value); if (e.target.value && !f.value) setValue('mode', 'bank') }} />}</Field></Col>
        <Col xs={24}><Field control={control} name="notes" label="Notes">{(f) => <Input {...f} value={f.value ?? ''} />}</Field></Col>
      </Row>
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
    { title: 'Purpose', dataIndex: 'purpose', render: (v: string) => (v === 'general' ? '' : v) },
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
    />
  )
}
