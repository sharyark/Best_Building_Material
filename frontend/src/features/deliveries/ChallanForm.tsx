import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, App, Button, Col, Form, Input, Row, Segmented, Select, Space, Tag, Typography } from 'antd'
import type { RefSelectProps } from 'antd/es/select'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '@/api/client'
import { useGet } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Delivery, LoadUnit, Material, MoneyAccount, PartyBalance, StockItem, VehicleType } from '@/api/types'
import { DateField } from '@/components/DateField'
import { MoneyInput, QtyInput } from '@/components/DecimalInput'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Field } from '@/components/Field'
import { Money } from '@/components/Money'
import { QuickAddParty, QuickAddSite } from '@/components/QuickAdd'
import { usePermission } from '@/hooks/usePermission'
import { formatCurrency, formatQty, toNumber } from '@/lib/format'
import { today } from '@/lib/date'
import { deliverySchema, type DeliveryForm } from '@/lib/schemas'

const LAST_KEY = 'hisaab.challan.last'

const VEHICLE_TYPES: { value: VehicleType; label: string; load: string; loadUnit: LoadUnit | null }[] = [
  { value: 'tractor_trolley', label: 'Tractor', load: 'trolley', loadUnit: null },
  { value: 'dumper', label: 'Dumper', load: 'dumper', loadUnit: 'dumper' },
  { value: 'loader', label: 'Loader', load: 'bucket', loadUnit: 'bucket' },
]

interface Last {
  date?: string
  vehicle_type?: VehicleType
  vehicle_id?: number | null
  driver_id?: number | null
}

function readLast(): Last {
  try {
    return JSON.parse(localStorage.getItem(LAST_KEY) ?? '{}')
  } catch {
    return {}
  }
}

const blank = (last: Last): DeliveryForm => ({
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
  load_size: 'full',
  with_cement: false,
  other_half_id: null,
  extra_qty: '',
  extra_rate: '',
  pay: 'credit',
  paid_amount: '',
  money_account_id: null,
})

/** Half of `qty` loads, kept to the 3 decimals quantities allow. */
const halfOf = (qty: string) => String(Number((toNumber(qty) / 2).toFixed(3)))
const round2 = (n: number) => Math.round(n * 100) / 100

const modeOf = (account: MoneyAccount | undefined) => (account?.kind === 'cash' ? 'cash' : 'bank')

/** The customer's khata at a glance, under the customer field. */
function BalanceTag({ b }: { b: PartyBalance }) {
  const v = toNumber(b.balance)
  if (v < 0) return <Tag color="green">Advance: <Money value={-v} /></Tag>
  if (v > 0)
    return (
      <Tag color={b.days_unpaid !== null && b.days_unpaid > b.credit_overdue_days ? 'red' : 'orange'}>
        Udhaar: <Money value={v} />
        {b.days_unpaid ? ` · ${b.days_unpaid} days` : ''}
      </Tag>
    )
  return <Tag>Khata clear</Tag>
}

/** Loose material (sand, crush, gravel) is sold by the vehicle load; bags and pieces are counted. */
const isLoose = (m: Material | undefined) => m?.unit === 'trolley'

function loadFactor(m: Material | undefined, unit: LoadUnit | null): number {
  if (!m || !unit) return 1
  return toNumber(unit === 'dumper' ? m.dumper_qty : m.bucket_qty)
}

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
  const extraRateTouched = useRef(editing)
  const [rateSource, setRateSource] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const canAdd = usePermission('masters.write')
  const [quick, setQuick] = useState<{ kind: 'customer' | 'site'; name: string } | null>(null)

  const [vehicleType, setVehicleType] = useState<VehicleType>(() => {
    if (delivery?.load_unit === 'dumper') return 'dumper'
    if (delivery?.load_unit === 'bucket') return 'loader'
    if (delivery) return lookups.vehicleById.get(delivery.vehicle_id ?? -1)?.type ?? 'tractor_trolley'
    return readLast().vehicle_type ?? 'tractor_trolley'
  })
  const typeInfo = VEHICLE_TYPES.find((t) => t.value === vehicleType)!
  // Editing bags/pieces: lookups may load after mount, so pick the type from the challan's vehicle then.
  // (Loose material without a load_unit was sold by the trolley, so it stays on Tractor.)
  useEffect(() => {
    if (!delivery || delivery.load_unit) return
    const t = lookups.vehicleById.get(delivery.vehicle_id ?? -1)?.type
    if (t && !isLoose(lookups.materialById.get(delivery.material_id))) setVehicleType(t)
  }, [delivery, lookups.vehicleById, lookups.materialById])

  const { control, handleSubmit, reset, setValue, getValues } = useForm<DeliveryForm>({
    resolver: zodResolver(deliverySchema),
    defaultValues: delivery
      ? {
          date: delivery.date, customer_id: delivery.customer_id, site_id: delivery.site_id, material_id: delivery.material_id,
          // qty on the challan is already halved; the form edits the number of loads
          qty: delivery.load_size === 'half' ? String(toNumber(delivery.qty) * 2) : String(delivery.qty),
          sale_rate: String(delivery.sale_rate), freight_amount: String(delivery.freight_amount),
          vehicle_id: delivery.vehicle_id, driver_id: delivery.driver_id, notes: delivery.notes ?? '',
          load_size: delivery.load_size,
          // a second loose material on a half load is the other half; anything else rode along (cement)
          with_cement: delivery.extra_material_id !== null && !(delivery.load_size === 'half' && delivery.extra_unit === 'trolley'),
          other_half_id: delivery.load_size === 'half' && delivery.extra_unit === 'trolley' ? delivery.extra_material_id : null,
          extra_qty: delivery.extra_qty ? String(toNumber(delivery.extra_qty)) : '',
          extra_rate: delivery.extra_rate ? String(delivery.extra_rate) : '',
          pay: 'credit', paid_amount: '', money_account_id: null,
        }
      : blank(readLast()),
  })
  const [date, customerId, materialId, qty, rate, freight, loadSize, withCement, otherHalfId, extraQty, extraRate, pay, paidAmount, moneyAccountId] = useWatch({
    control,
    name: ['date', 'customer_id', 'material_id', 'qty', 'sale_rate', 'freight_amount', 'load_size', 'with_cement', 'other_half_id', 'extra_qty', 'extra_rate', 'pay', 'paid_amount', 'money_account_id'],
  })
  const balanceQuery = useGet<PartyBalance>(`/masters/parties/${customerId}/balance`, undefined, { enabled: Boolean(customerId), staleTime: 5_000 })
  // keepPreviousData would briefly show the last customer's khata; only trust a matching answer
  const khata = balanceQuery.data?.party_id === customerId ? balanceQuery.data : undefined
  const [udhaarOk, setUdhaarOk] = useState(false)
  useEffect(() => setUdhaarOk(false), [customerId])
  const cashAccount = lookups.moneyAccounts.find((a) => a.kind === 'cash') ?? lookups.moneyAccounts[0]
  useEffect(() => {
    if (pay !== 'credit' && !moneyAccountId && cashAccount) setValue('money_account_id', cashAccount.id)
  }, [pay, moneyAccountId, cashAccount, setValue])

  const material = lookups.materialById.get(materialId)
  const loose = isLoose(material)
  // Bags or pieces on a dumper are still counted in their own unit.
  const loadUnit = loose ? typeInfo.loadUnit : null
  const unitLabel = loose ? typeInfo.load : material?.unit
  const cement = useMemo(
    () => lookups.materials.find((m) => /cement/i.test(m.name)) ?? lookups.materials.find((m) => m.unit === 'bag'),
    [lookups.materials],
  )
  const canAddCement = vehicleType === 'tractor_trolley' && loose && Boolean(cement) && cement?.id !== materialId

  // Half loads and cement only make sense for loose material; drop them when they stop applying
  // (not before master data has loaded, or an edited half load would flip to full).
  const ready = !lookups.loading
  useEffect(() => {
    if (ready && !loose && loadSize === 'half') setValue('load_size', 'full')
  }, [ready, loose, loadSize, setValue])
  useEffect(() => {
    if (ready && !canAddCement && withCement) setValue('with_cement', false)
  }, [ready, canAddCement, withCement, setValue])
  // Splitting a half trolley between two materials only applies to the tractor's half load.
  const canSplitHalf = vehicleType === 'tractor_trolley' && loose && loadSize === 'half'
  useEffect(() => {
    if (ready && !canSplitHalf && otherHalfId) setValue('other_half_id', null)
  }, [ready, canSplitHalf, otherHalfId, setValue])
  const halfMaterials = useMemo(() => lookups.materials.filter((m) => isLoose(m) && m.id !== materialId), [lookups.materials, materialId])
  const otherHalf = otherHalfId ? lookups.materialById.get(otherHalfId) : undefined
  // The second line on the challan: cement bags, or the other half of the trolley.
  const extraMaterial = withCement ? cement : otherHalf
  const extraLineQty = withCement ? toNumber(extraQty) : otherHalf ? toNumber(qty) / 2 : 0

  const loadsFactor = loadSize === 'half' ? 0.5 : 1
  const factor = loadFactor(material, loadUnit)
  const needed = toNumber(qty) * loadsFactor * factor
  const stock = useGet<StockItem[]>('/stock', undefined, { staleTime: 5_000 })
  const available = stock.data?.find((s) => s.material_id === materialId)
  // When editing, this challan's own quantity is already out of the yard.
  const availableQty = toNumber(available?.qty_on_hand) + (delivery && delivery.material_id === materialId ? toNumber(delivery.stock_qty ?? delivery.qty) : 0)
  const shortBy = material && needed > availableQty ? needed - availableQty : 0
  const extraStock = toNumber(stock.data?.find((s) => s.material_id === extraMaterial?.id)?.qty_on_hand) + (extraMaterial && delivery?.extra_material_id === extraMaterial.id ? toNumber(delivery?.extra_qty) : 0)
  const missingLoadSize = Boolean(material && loadUnit && !factor)

  // Auto-fill the rate from the customer's rate card (else the material default) until the user types one.
  useEffect(() => {
    if (!customerId || !materialId || rateTouched.current) return
    let stale = false
    api
      .get<{ rate: string; source: string }>('/masters/rate', { params: { party_id: customerId, material_id: materialId, date, load_unit: loadUnit ?? undefined } })
      .then(({ data }) => {
        if (!stale) {
          setValue('sale_rate', String(data.rate), { shouldValidate: true })
          setRateSource(data.source)
        }
      })
      .catch(() => {
        if (!stale) setRateSource(null)
      })
    return () => {
      stale = true
    }
  }, [customerId, materialId, date, loadUnit, setValue])

  useEffect(() => {
    if (!extraMaterial || !customerId || extraRateTouched.current) return
    let stale = false
    api
      .get<{ rate: string }>('/masters/rate', { params: { party_id: customerId, material_id: extraMaterial.id, date } })
      .then(({ data }) => {
        if (!stale) setValue('extra_rate', String(data.rate), { shouldValidate: true })
      })
      .catch(() => undefined)
    return () => {
      stale = true
    }
  }, [extraMaterial, customerId, date, setValue])

  const sites = useMemo(() => lookups.sites.filter((s) => s.party_id === customerId), [lookups.sites, customerId])
  useEffect(() => {
    if (!editing && sites.length === 1) setValue('site_id', sites[0].id)
  }, [sites, editing, setValue])

  const vehicles = useMemo(() => lookups.vehicles.filter((v) => v.type === vehicleType), [lookups.vehicles, vehicleType])

  function changeVehicleType(t: VehicleType) {
    setVehicleType(t)
    const current = lookups.vehicleById.get(getValues('vehicle_id') ?? -1)
    if (current && current.type !== t) {
      setValue('vehicle_id', null)
      setValue('driver_id', null)
    }
    // the rate is per load, so a different vehicle means a different rate
    rateTouched.current = false
  }

  const total = round2(toNumber(qty) * loadsFactor * toNumber(rate) + toNumber(freight) + extraLineQty * toNumber(extraRate))
  const paidNow = editing ? 0 : pay === 'full' ? total : pay === 'part' ? toNumber(paidAmount) : 0
  // Khata after this challan (when editing, the balance already includes it).
  const khataBalance = toNumber(khata?.balance)
  const advance = khataBalance < 0 ? -khataBalance : 0
  const after = round2(khataBalance + (editing ? 0 : total) - paidNow)
  const advanceRunsOut = !editing && advance > 0 && total > 0 && after > 0
  const advanceLow = !editing && advance > 0 && total > 0 && after <= 0 && -after < toNumber(khata?.advance_low_threshold)

  async function submit(values: DeliveryForm, allowNegative = false) {
    setSaving(true)
    try {
      const { with_cement, other_half_id, extra_qty, extra_rate, pay: payHow, paid_amount, money_account_id, ...rest } = values
      const paid = editing || payHow === 'credit' ? 0 : payHow === 'full' ? total : toNumber(paid_amount)
      if (payHow === 'full' && !editing && total <= 0) {
        message.error('The challan total is zero, so there is nothing to receive. Enter the rate first.')
        return
      }
      const half = !with_cement && other_half_id && canSplitHalf ? other_half_id : null
      const body = {
        ...rest,
        site_id: values.site_id || null,
        vehicle_id: values.vehicle_id || null,
        driver_id: values.driver_id || null,
        notes: values.notes || null,
        load_unit: loadUnit,
        load_size: loose ? values.load_size : 'full',
        extra_material_id: with_cement && cement ? cement.id : half,
        extra_qty: with_cement ? extra_qty : half ? halfOf(values.qty) : null,
        extra_rate: with_cement || half ? extra_rate : null,
        allow_negative_stock: allowNegative,
        ...(paid > 0
          ? { payment: { amount: paid.toFixed(2), money_account_id, mode: modeOf(lookups.moneyAccountById.get(money_account_id ?? -1)) } }
          : {}),
        ...(editing ? {} : { client_ref: clientRef.current }),
      }
      const { data } = editing
        ? await api.put<Delivery>(`/deliveries/${delivery!.id}`, body)
        : await api.post<Delivery>('/deliveries', body)
      await qc.invalidateQueries()
      message.success(data.receipt_id ? `Challan ${data.challan_no} saved, ${formatCurrency(paid)} received` : `Challan ${data.challan_no} saved`)
      if (!editing) {
        const last: Last = { date: values.date, vehicle_type: vehicleType, vehicle_id: values.vehicle_id, driver_id: values.driver_id }
        localStorage.setItem(LAST_KEY, JSON.stringify(last))
        clientRef.current = crypto.randomUUID()
        rateTouched.current = false
        extraRateTouched.current = false
        setRateSource(null)
        setUdhaarOk(false)
        reset(blank(last))
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

  // Tractor: one dropdown for full / half / full + cement. Dumper and loader: full or half.
  const loadOptions = [
    { value: 'full', label: `Full ${typeInfo.load}` },
    { value: 'half', label: `Half ${typeInfo.load}` },
    ...(canAddCement ? [{ value: 'cement', label: `Full ${typeInfo.load} + cement` }] : []),
  ]
  const loadValue = withCement ? 'cement' : loadSize

  return (
    <Form layout="vertical" onFinish={handleSubmit((v) => submit(v, false))} autoComplete="off">
      <div className="challan-vehicle-type">
        <Typography.Text type="secondary" id="challan-vehicle-type-label">Vehicle type</Typography.Text>
        <Segmented
          aria-labelledby="challan-vehicle-type-label"
          size="large"
          block
          value={vehicleType}
          onChange={(v) => changeVehicleType(v as VehicleType)}
          options={VEHICLE_TYPES.map((t) => ({ value: t.value, label: t.label }))}
        />
      </div>
      <Row gutter={12}>
        <Col xs={24} sm={12} lg={4}>
          <Field control={control} name="date" label="Date" required>{(f) => <DateField id={f.id} value={f.value} onChange={f.onChange} />}</Field>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Field control={control} name="customer_id" label="Customer" required extra={khata ? <BalanceTag b={khata} /> : undefined}>
            {(f) => (
              <EntitySelect id={f.id}
                ref={customerRef}
                autoFocus={!editing}
                options={optionsOf(lookups.customers)}
                value={f.value}
                allowClear={false}
                placeholder="Type customer name"
                addLabel="New customer"
                onAdd={canAdd ? (name) => setQuick({ kind: 'customer', name }) : undefined}
                onChange={(v) => {
                  f.onChange(v)
                  setValue('site_id', null)
                  rateTouched.current = editing
                  extraRateTouched.current = editing
                }}
              />
            )}
          </Field>
        </Col>
        <Col xs={24} sm={12} lg={5}>
          <Field control={control} name="site_id" label="Site">
            {(f) => <EntitySelect id={f.id} options={optionsOf(sites)} value={f.value} onChange={f.onChange} placeholder={customerId ? 'Select site' : 'Pick customer first'} disabled={!customerId} addLabel="New site" onAdd={canAdd && customerId ? (name) => setQuick({ kind: 'site', name }) : undefined} />}
          </Field>
        </Col>
        <Col xs={12} sm={6} lg={5}>
          <Field control={control} name="vehicle_id" label={typeInfo.label}>
            {(f) => (
              <EntitySelect id={f.id}
                options={optionsOf(vehicles)}
                value={f.value}
                placeholder={`Select ${typeInfo.label.toLowerCase()}`}
                onChange={(v) => {
                  f.onChange(v)
                  const defaultDriver = lookups.staff.find((s) => s.default_vehicle_id === v && (s.role === 'driver' || s.role === 'operator'))
                  if (v && defaultDriver && !getValues('driver_id')) setValue('driver_id', defaultDriver.id)
                }}
              />
            )}
          </Field>
        </Col>
        <Col xs={12} sm={6} lg={4}>
          <Field control={control} name="driver_id" label="Driver">
            {(f) => <EntitySelect id={f.id} options={optionsOf(lookups.drivers)} value={f.value} onChange={f.onChange} />}
          </Field>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col xs={24} sm={12} lg={6}>
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
        <Col xs={12} sm={6} lg={3}>
          <Field control={control} name="qty" label={loose ? `${typeInfo.load[0].toUpperCase()}${typeInfo.load.slice(1)}s` : 'Qty'} required>
            {(f) => <QtyInput {...f} addonAfter={unitLabel} inputMode="decimal" />}
          </Field>
        </Col>
        {loose && (
          <Col xs={12} sm={6} lg={5}>
            <Field control={control} name="load_size" label="Load">
              {(f) =>
                vehicleType === 'tractor_trolley' ? (
                  <Select
                    id={f.id}
                    value={loadValue}
                    options={loadOptions}
                    onChange={(v: string) => {
                      if ((v === 'cement') !== withCement) {
                        // switching what rides along: the old second line's rate no longer applies
                        extraRateTouched.current = false
                        setValue('extra_rate', '')
                      }
                      setValue('with_cement', v === 'cement')
                      f.onChange(v === 'half' ? 'half' : 'full')
                    }}
                  />
                ) : (
                  <Segmented
                    id={f.id}
                    block
                    value={f.value}
                    onChange={f.onChange}
                    options={[{ value: 'full', label: 'Full' }, { value: 'half', label: 'Half' }]}
                  />
                )
              }
            </Field>
          </Col>
        )}
        <Col xs={12} sm={6} lg={5}>
          <Field
            control={control}
            name="sale_rate"
            label={loose ? `Rate (per full ${typeInfo.load})` : 'Rate'}
            required
            extra={rateSource ? <Tag color={rateSource === 'rate_card' ? 'green' : 'default'}>{rateSource === 'rate_card' ? 'Customer rate card' : 'Default rate'}</Tag> : undefined}
          >
            {(f) => <MoneyInput {...f} onChange={(v) => { rateTouched.current = true; f.onChange(v) }} />}
          </Field>
        </Col>
        <Col xs={12} sm={6} lg={5}>
          <Field control={control} name="freight_amount" label="Freight (bhara)">{(f) => <MoneyInput {...f} />}</Field>
        </Col>
      </Row>
      {withCement && cement && (
        <Row gutter={12} className="challan-extra">
          <Col xs={12} sm={6} lg={4}>
            <Field control={control} name="extra_qty" label={`${cement.name} (${cement.unit}s)`} required>
              {(f) => <QtyInput {...f} addonAfter={cement.unit} inputMode="numeric" />}
            </Field>
          </Col>
          <Col xs={12} sm={6} lg={5}>
            <Field control={control} name="extra_rate" label={`${cement.name} rate (per ${cement.unit})`} required>
              {(f) => <MoneyInput {...f} onChange={(v) => { extraRateTouched.current = true; f.onChange(v) }} />}
            </Field>
          </Col>
          <Col xs={24} sm={12} lg={15}>
            <Typography.Text type={toNumber(extraQty) > extraStock ? 'warning' : 'secondary'} className="challan-extra-hint">
              Yard has {formatQty(extraStock)} {cement.unit} of {cement.name}
            </Typography.Text>
          </Col>
        </Row>
      )}
      {canSplitHalf && (
        <Row gutter={12} className="challan-extra">
          <Col xs={24} sm={12} lg={6}>
            <Field control={control} name="other_half_id" label="Other half (optional)">
              {(f) => (
                <EntitySelect id={f.id}
                  options={optionsOf(halfMaterials)}
                  value={f.value}
                  placeholder="Same trolley, other material"
                  onChange={(v) => {
                    f.onChange(v ?? null)
                    extraRateTouched.current = false
                    setValue('extra_rate', '')
                  }}
                />
              )}
            </Field>
          </Col>
          {otherHalf && (
            <Col xs={12} sm={6} lg={5}>
              <Field control={control} name="extra_rate" label={`${otherHalf.name} rate (per full trolley)`} required>
                {(f) => <MoneyInput {...f} onChange={(v) => { extraRateTouched.current = true; f.onChange(v) }} />}
              </Field>
            </Col>
          )}
          <Col xs={24} sm={12} lg={otherHalf ? 13 : 18}>
            <Typography.Text type={otherHalf && extraLineQty > extraStock ? 'warning' : 'secondary'} className="challan-extra-hint">
              {otherHalf
                ? `Half ${material?.name} + half ${otherHalf.name}. Yard has ${formatQty(extraStock)} ${otherHalf.unit} of ${otherHalf.name}.`
                : `Leave empty if the whole half trolley is ${material?.name}.`}
            </Typography.Text>
          </Col>
        </Row>
      )}
      {!editing && (
        <Row gutter={12} className="challan-pay">
          <Col xs={24} sm={12} lg={8}>
            <Field control={control} name="pay" label="Payment">
              {(f) => (
                <Segmented
                  id={f.id}
                  block
                  value={f.value}
                  onChange={f.onChange}
                  options={[
                    { value: 'credit', label: advance > 0 ? 'From advance' : 'Udhaar' },
                    { value: 'full', label: 'Paid in full' },
                    { value: 'part', label: 'Part paid' },
                  ]}
                />
              )}
            </Field>
          </Col>
          {pay === 'part' && (
            <Col xs={12} sm={6} lg={5}>
              <Field control={control} name="paid_amount" label="Amount received" required>{(f) => <MoneyInput {...f} />}</Field>
            </Col>
          )}
          {pay !== 'credit' && (
            <Col xs={12} sm={6} lg={5}>
              <Field control={control} name="money_account_id" label="Received in" required>
                {(f) => <EntitySelect id={f.id} options={optionsOf(lookups.moneyAccounts)} value={f.value} onChange={f.onChange} allowClear={false} />}
              </Field>
            </Col>
          )}
          {customerId && khata && total > 0 && (
            <Col xs={24} lg={pay === 'credit' ? 16 : pay === 'part' ? 6 : 11}>
              <Typography.Text type="secondary" className="challan-extra-hint">
                {after > 0 ? <>Udhaar after this: <Money value={after} /></> : after < 0 ? <>Advance left after this: <Money value={-after} /></> : 'Khata will be clear'}
              </Typography.Text>
            </Col>
          )}
        </Row>
      )}
      {advanceRunsOut && !udhaarOk && (
        <Alert
          showIcon
          type="warning"
          style={{ marginBottom: 12 }}
          message={<>The advance (<Money value={advance} />) runs out with this challan. <Money value={after} /> will go on udhaar.</>}
          action={
            <Space direction="vertical" size={6}>
              <Button
                size="small"
                type="primary"
                onClick={() => {
                  setValue('pay', 'part')
                  setValue('paid_amount', after.toFixed(2), { shouldValidate: true })
                }}
              >
                Take more advance
              </Button>
              <Button size="small" onClick={() => setUdhaarOk(true)}>Put it on udhaar</Button>
            </Space>
          }
        />
      )}
      {advanceLow && (
        <Alert
          showIcon
          type="info"
          style={{ marginBottom: 12 }}
          message={after === 0 ? 'This challan uses up the whole advance.' : <>Advance is running low: only <Money value={-after} /> will be left after this challan.</>}
        />
      )}
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
      {missingLoadSize && material && (
        <Alert
          showIcon
          type="warning"
          style={{ marginBottom: 8 }}
          message={`${material.name} has no ${typeInfo.load} size yet. Ask the owner to set how much one ${typeInfo.load} holds in Masters > Materials.`}
        />
      )}
      {material && !missingLoadSize && (
        <Alert
          showIcon
          type={shortBy > 0 ? 'warning' : 'info'}
          message={
            shortBy > 0
              ? `Stock warning: yard has ${formatQty(availableQty)} ${material.unit} of ${material.name}, this challan needs ${formatQty(needed)} (short by ${formatQty(shortBy)}).`
              : `Yard stock: ${formatQty(availableQty)} ${material.unit} of ${material.name}` +
                (loadUnit && factor ? ` (1 ${typeInfo.load} = ${formatQty(factor)} ${material.unit})` : '')
          }
        />
      )}
      <QuickAddParty
        open={quick?.kind === 'customer'}
        type="customer"
        initialName={quick?.name ?? ''}
        onClose={() => setQuick(null)}
        onCreated={(p) => {
          setValue('customer_id', p.id, { shouldValidate: true })
          setValue('site_id', null)
          rateTouched.current = editing
        }}
      />
      <QuickAddSite
        open={quick?.kind === 'site'}
        partyId={customerId ?? null}
        initialName={quick?.name ?? ''}
        onClose={() => setQuick(null)}
        onCreated={(s) => setValue('site_id', s.id, { shouldValidate: true })}
      />
    </Form>
  )
}
