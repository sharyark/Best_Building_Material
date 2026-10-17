import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, App, Button, Col, Form, Input, Row, Space, Tag, Typography } from 'antd'
import type { RefSelectProps } from 'antd/es/select'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '@/api/client'
import { useGet } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Delivery, StockItem } from '@/api/types'
import { DateField } from '@/components/DateField'
import { MoneyInput, QtyInput } from '@/components/DecimalInput'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Field } from '@/components/Field'
import { Money } from '@/components/Money'
import { formatQty, toNumber } from '@/lib/format'
import { today } from '@/lib/date'
import { deliverySchema, type DeliveryForm } from '@/lib/schemas'

const LAST_KEY = 'hisaab.challan.last'

function readLast(): Partial<DeliveryForm> {
  try {
    return JSON.parse(localStorage.getItem(LAST_KEY) ?? '{}')
  } catch {
    return {}
  }
}

const blank = (last: Partial<DeliveryForm>): DeliveryForm => ({
  date: last.date ?? today(),
  customer_id: undefined as unknown as number,
  site_id: null,
  material_id: undefined as unknown as number,
  qty: '',
  sale_rate: '',
  freight_amount: '0',
  vehicle_id: last.vehicle_id ?? null,
  driver_id: last.driver_id ?? null,
  notes: '',
})

interface Props {
  /** Edit mode when given; otherwise the fast "save and reset" entry mode. */
  delivery?: Delivery
  onSaved?: (d: Delivery) => void
  onPrint?: (d: Delivery) => void
}

export default function ChallanForm({ delivery, onSaved, onPrint }: Props) {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const lookups = useLookups()
  const editing = Boolean(delivery)
  const clientRef = useRef(crypto.randomUUID())
  const customerRef = useRef<RefSelectProps>(null)
  const rateTouched = useRef(editing)
  const [rateSource, setRateSource] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const { control, handleSubmit, reset, setValue, getValues } = useForm<DeliveryForm>({
    resolver: zodResolver(deliverySchema),
    defaultValues: delivery
      ? {
          date: delivery.date, customer_id: delivery.customer_id, site_id: delivery.site_id, material_id: delivery.material_id,
          qty: String(delivery.qty), sale_rate: String(delivery.sale_rate), freight_amount: String(delivery.freight_amount),
          vehicle_id: delivery.vehicle_id, driver_id: delivery.driver_id, notes: delivery.notes ?? '',
        }
      : blank(readLast()),
  })
  const [date, customerId, materialId, qty, rate, freight] = useWatch({
    control,
    name: ["date", "customer_id", "material_id", "qty", "sale_rate", "freight_amount"],
  })

  const stock = useGet<StockItem[]>('/stock', undefined, { staleTime: 5_000 })
  const material = lookups.materialById.get(materialId)
  const available = stock.data?.find((s) => s.material_id === materialId)
  // When editing, this challan's own quantity is already out of the yard.
  const availableQty = toNumber(available?.qty_on_hand) + (delivery && delivery.material_id === materialId ? toNumber(delivery.qty) : 0)
  const shortBy = material && toNumber(qty) > availableQty ? toNumber(qty) - availableQty : 0

  // Auto-fill the rate from the customer's rate card (else the material default) until the user types one.
  useEffect(() => {
    if (!customerId || !materialId || rateTouched.current) return
    let stale = false
    api
      .get<{ rate: string; source: string }>('/masters/rate', { params: { party_id: customerId, material_id: materialId, date } })
      .then(({ data }) => {
        if (!stale) {
          setValue('sale_rate', String(data.rate), { shouldValidate: true })
          setRateSource(data.source)
        }
      })
      .catch(() => undefined)
    return () => {
      stale = true
    }
  }, [customerId, materialId, date, setValue])

  const sites = useMemo(() => lookups.sites.filter((s) => s.party_id === customerId), [lookups.sites, customerId])
  useEffect(() => {
    if (!editing && sites.length === 1) setValue('site_id', sites[0].id)
  }, [sites, editing, setValue])

  const total = toNumber(qty) * toNumber(rate) + toNumber(freight)

  async function submit(values: DeliveryForm, allowNegative = false) {
    setSaving(true)
    try {
      const body = {
        ...values,
        site_id: values.site_id || null,
        vehicle_id: values.vehicle_id || null,
        driver_id: values.driver_id || null,
        notes: values.notes || null,
        allow_negative_stock: allowNegative,
        ...(editing ? {} : { client_ref: clientRef.current }),
      }
      const { data } = editing
        ? await api.put<Delivery>(`/deliveries/${delivery!.id}`, body)
        : await api.post<Delivery>('/deliveries', body)
      await qc.invalidateQueries()
      message.success(`Challan ${data.challan_no} saved`)
      if (!editing) {
        localStorage.setItem(LAST_KEY, JSON.stringify({ date: values.date, vehicle_id: values.vehicle_id, driver_id: values.driver_id }))
        clientRef.current = crypto.randomUUID()
        rateTouched.current = false
        setRateSource(null)
        reset(blank({ date: values.date, vehicle_id: values.vehicle_id, driver_id: values.driver_id }))
        setTimeout(() => customerRef.current?.focus(), 50)
      }
      onSaved?.(data)
      if (!editing) onPrint?.(data)
    } catch (err) {
      const e = apiError(err)
      if (e.code === 'INSUFFICIENT_STOCK' && !allowNegative) {
        modal.confirm({
          title: 'Not enough stock in the yard',
          content: `${e.message}. Save the challan anyway? Stock will go negative until the next purchase is entered.`,
          okText: 'Save anyway',
          onOk: () => submit(values, true),
        })
      } else {
        message.error(e.message, 6)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Form layout="vertical" onFinish={handleSubmit((v) => submit(v, false))} autoComplete="off">
      <Row gutter={12}>
        <Col xs={24} sm={12} lg={4}>
          <Field control={control} name="date" label="Date" required>{(f) => <DateField id={f.id} value={f.value} onChange={f.onChange} />}</Field>
        </Col>
        <Col xs={24} sm={12} lg={7}>
          <Field control={control} name="customer_id" label="Customer" required>
            {(f) => (
              <EntitySelect id={f.id}
                ref={customerRef}
                autoFocus={!editing}
                options={optionsOf(lookups.customers)}
                value={f.value}
                allowClear={false}
                placeholder="Type customer name"
                onChange={(v) => {
                  f.onChange(v)
                  setValue('site_id', null)
                  rateTouched.current = editing
                }}
              />
            )}
          </Field>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Field control={control} name="site_id" label="Site">
            {(f) => <EntitySelect id={f.id} options={optionsOf(sites)} value={f.value} onChange={f.onChange} placeholder={customerId ? 'Select site' : 'Pick customer first'} disabled={!customerId} />}
          </Field>
        </Col>
        <Col xs={24} sm={12} lg={7}>
          <Field control={control} name="material_id" label="Material" required>
            {(f) => (
              <EntitySelect id={f.id}
                options={optionsOf(lookups.materials, (m) => `${m.name} (${m.unit})`)}
                value={f.value}
                allowClear={false}
                placeholder="Type material"
                onChange={(v) => {
                  f.onChange(v)
                  rateTouched.current = editing
                }}
              />
            )}
          </Field>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col xs={12} sm={8} lg={4}>
          <Field control={control} name="qty" label="Qty" required>
            {(f) => <QtyInput {...f} addonAfter={material?.unit} inputMode="decimal" />}
          </Field>
        </Col>
        <Col xs={12} sm={8} lg={5}>
          <Field
            control={control}
            name="sale_rate"
            label="Rate"
            required
            extra={rateSource ? <Tag color={rateSource === 'rate_card' ? 'green' : 'default'}>{rateSource === 'rate_card' ? 'Customer rate card' : 'Default rate'}</Tag> : undefined}
          >
            {(f) => <MoneyInput {...f} onChange={(v) => { rateTouched.current = true; f.onChange(v) }} />}
          </Field>
        </Col>
        <Col xs={12} sm={8} lg={5}>
          <Field control={control} name="freight_amount" label="Freight (bhara)">{(f) => <MoneyInput {...f} />}</Field>
        </Col>
        <Col xs={12} sm={12} lg={5}>
          <Field control={control} name="vehicle_id" label="Vehicle">
            {(f) => (
              <EntitySelect id={f.id}
                options={optionsOf(lookups.vehicles)}
                value={f.value}
                onChange={(v) => {
                  f.onChange(v)
                  const defaultDriver = lookups.staff.find((s) => s.default_vehicle_id === v && s.role === 'driver')
                  if (v && defaultDriver && !getValues('driver_id')) setValue('driver_id', defaultDriver.id)
                }}
              />
            )}
          </Field>
        </Col>
        <Col xs={12} sm={12} lg={5}>
          <Field control={control} name="driver_id" label="Driver">
            {(f) => <EntitySelect id={f.id} options={optionsOf(lookups.drivers)} value={f.value} onChange={f.onChange} />}
          </Field>
        </Col>
      </Row>
      <Row gutter={12} align="bottom">
        <Col xs={24} lg={12}>
          <Field control={control} name="notes" label="Notes">{(f) => <Input {...f} value={f.value ?? ''} maxLength={500} />}</Field>
        </Col>
        <Col xs={24} lg={12}>
          <Space align="center" style={{ width: '100%', justifyContent: 'flex-end', marginBottom: 12 }} wrap>
            <Typography.Text>
              Total: <Typography.Text strong><Money value={total} /></Typography.Text>
            </Typography.Text>
            <Button type="primary" htmlType="submit" loading={saving} size="large">
              {editing ? 'Save changes' : 'Save & next (Enter)'}
            </Button>
          </Space>
        </Col>
      </Row>
      {material && (
        <Alert
          showIcon
          type={shortBy > 0 ? 'warning' : 'info'}
          message={
            shortBy > 0
              ? `Stock warning: yard has ${formatQty(availableQty)} ${material.unit} of ${material.name}, this challan needs ${formatQty(qty)} (short by ${formatQty(shortBy)}).`
              : `Yard stock: ${formatQty(availableQty)} ${material.unit} of ${material.name}`
          }
        />
      )}
    </Form>
  )
}
