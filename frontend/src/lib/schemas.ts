/** Zod schemas: the same rules as the backend's Pydantic models, so forms fail fast with clear messages. */
import { z } from 'zod'

const decimal = (places: number) =>
  z
    .string({ required_error: 'Required' })
    .trim()
    .regex(new RegExp(`^\\d{1,12}(\\.\\d{1,${places}})?$`), `Enter a number${places ? ` (max ${places} decimals)` : ''}`)

export const moneyField = decimal(2)
export const positiveMoney = moneyField.refine((v) => Number(v) > 0, 'Must be above 0')
export const qtyField = decimal(3)
export const positiveQty = qtyField.refine((v) => Number(v) > 0, 'Must be above 0')
export const optionalMoney = z
  .string()
  .trim()
  .regex(/^(\d{1,12}(\.\d{1,2})?)?$/, 'Enter a number')
  .optional()
  .or(z.literal(''))

const id = z.number({ required_error: 'Required', invalid_type_error: 'Required' }).int().positive()
const optionalId = z.number().int().positive().nullable().optional()
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Pick a date')

export const deliverySchema = z.object({
  date: isoDate,
  customer_id: id,
  site_id: optionalId,
  /** UI only: the material list's choice, a material id or a group (negative) whose type is picked next. */
  material_pick: z.number().int().nullable().optional(),
  material_id: z.number().int().positive().optional(),
  /** UI only: which cement type rides on top of a trolley. */
  cement_type_id: optionalId,
  qty: positiveQty,
  sale_rate: positiveMoney,
  freight_amount: moneyField.default('0'),
  vehicle_id: optionalId,
  driver_id: optionalId,
  /** Driver's pay for this trip; pre-filled from his trip rate. */
  trip_pay: optionalMoney,
  notes: z.string().max(500).optional().or(z.literal('')),
  load_size: z.enum(['full', 'half']).default('full'),
  with_cement: z.boolean().default(false),
  /** Half trolley split between two materials: the material of the other half. */
  other_half_id: optionalId,
  extra_qty: z.string().optional().or(z.literal('')),
  extra_rate: z.string().optional().or(z.literal('')),
  /** How the customer pays for this challan: on the khata, or on the spot in full / in part. */
  pay: z.enum(['credit', 'full', 'part']).default('credit'),
  paid_amount: optionalMoney,
  money_account_id: optionalId,
}).superRefine((v, ctx) => {
  if (!v.material_id) {
    const group = (v.material_pick ?? 0) < 0
    ctx.addIssue({ code: 'custom', path: [group ? 'material_id' : 'material_pick'], message: group ? 'Pick the type' : 'Required' })
  }
  if (v.pay !== 'credit' && !v.money_account_id) ctx.addIssue({ code: 'custom', path: ['money_account_id'], message: 'Pick cash or bank' })
  if (v.pay === 'part' && !(Number(v.paid_amount) > 0)) ctx.addIssue({ code: 'custom', path: ['paid_amount'], message: 'Enter the amount received' })
  if (v.with_cement) {
    if (!(Number(v.extra_qty) > 0)) ctx.addIssue({ code: 'custom', path: ['extra_qty'], message: 'Enter the number of bags' })
    if (!(Number(v.extra_rate) > 0)) ctx.addIssue({ code: 'custom', path: ['extra_rate'], message: 'Enter the cement rate' })
  } else if (v.other_half_id) {
    if (v.other_half_id === v.material_id) ctx.addIssue({ code: 'custom', path: ['other_half_id'], message: 'Pick a different material for the other half' })
    if (!(Number(v.extra_rate) > 0)) ctx.addIssue({ code: 'custom', path: ['extra_rate'], message: 'Enter the rate' })
  }
})
export type DeliveryForm = z.infer<typeof deliverySchema>

export const purchaseSchema = z.object({
  date: isoDate,
  supplier_id: id,
  supplier_slip_no: z.string().max(40).optional().or(z.literal('')),
  transport_by: z.enum(['own', 'supplier']),
  vehicle_id: optionalId,
  driver_id: optionalId,
  trip_pay: optionalMoney,
  notes: z.string().max(500).optional().or(z.literal('')),
  lines: z
    .array(z.object({ material_id: id, qty: positiveQty, rate: positiveMoney }))
    .min(1, 'Add at least one material'),
})
export type PurchaseForm = z.infer<typeof purchaseSchema>

export const paymentSchema = z
  .object({
    date: isoDate,
    direction: z.enum(['in', 'out']),
    counterparty: z.enum(['party', 'staff']),
    party_id: optionalId,
    staff_id: optionalId,
    money_account_id: id,
    mode: z.enum(['cash', 'bank', 'cheque', 'online']),
    purpose: z.enum(['general', 'advance', 'salary', 'trip']),
    ref_no: z.string().max(60).optional().or(z.literal('')),
    amount: positiveMoney,
    notes: z.string().max(500).optional().or(z.literal('')),
  })
  .superRefine((v, ctx) => {
    if (v.counterparty === 'party' && !v.party_id) ctx.addIssue({ code: 'custom', path: ['party_id'], message: 'Required' })
    if (v.counterparty === 'staff' && !v.staff_id) ctx.addIssue({ code: 'custom', path: ['staff_id'], message: 'Required' })
  })
export type PaymentForm = z.infer<typeof paymentSchema>

export const expenseSchema = z
  .object({
    date: isoDate,
    category: z.enum(['diesel', 'food', 'repair', 'tyre', 'insurance', 'toll', 'office', 'misc']),
    vehicle_id: optionalId,
    /** Fuel with a rate: worked out as litres x rate, so not typed. */
    amount: optionalMoney,
    litres: z.string().trim().regex(/^(\d{1,9}(\.\d{1,3})?)?$/, 'Enter a number').optional().or(z.literal('')),
    rate_per_litre: optionalMoney,
    meter_reading: z.string().trim().regex(/^(\d{1,9}(\.\d{1,3})?)?$/, 'Enter a number').optional().or(z.literal('')),
    paid_via: z.enum(['money_account', 'party_credit']),
    money_account_id: optionalId,
    party_id: optionalId,
    notes: z.string().max(500).optional().or(z.literal('')),
  })
  .superRefine((v, ctx) => {
    const fuelByRate = v.category === 'diesel' && Number(v.rate_per_litre) > 0
    if (fuelByRate && !(Number(v.litres) > 0)) ctx.addIssue({ code: 'custom', path: ['litres'], message: 'Enter the litres' })
    if (!fuelByRate && !(Number(v.amount) > 0)) ctx.addIssue({ code: 'custom', path: ['amount'], message: v.category === 'diesel' ? 'Enter the rate per litre (or the amount)' : 'Must be above 0' })
    if (v.paid_via === 'money_account' && !v.money_account_id)
      ctx.addIssue({ code: 'custom', path: ['money_account_id'], message: 'Pick cash/bank account' })
    if (v.paid_via === 'party_credit' && !v.party_id)
      ctx.addIssue({ code: 'custom', path: ['party_id'], message: 'Pick the pump / workshop' })
  })
export type ExpenseForm = z.infer<typeof expenseSchema>

export const rentalSchema = z.object({
  date: isoDate,
  customer_id: id,
  site_id: optionalId,
  vehicle_id: id,
  operator_id: optionalId,
  trip_pay: optionalMoney,
  basis: z.enum(['hour', 'trip', 'day']),
  qty: positiveQty,
  rate: positiveMoney,
  notes: z.string().max(500).optional().or(z.literal('')),
})
export type RentalForm = z.infer<typeof rentalSchema>

export const partySchema = z.object({
  type: z.enum(['customer', 'supplier', 'both']),
  name: z.string().trim().min(1, 'Required').max(150),
  phone: z.string().max(30).optional().or(z.literal('')),
  address: z.string().optional().or(z.literal('')),
  tax_no: z.string().max(40).optional().or(z.literal('')),
})

export const loginSchema = z.object({
  phone: z.string().trim().min(1, 'Enter your phone / username'),
  password: z.string().min(1, 'Enter your password'),
})

export const voidSchema = z.object({ reason: z.string().trim().min(3, 'Give a reason (min 3 characters)').max(500) })
