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
  material_id: id,
  qty: positiveQty,
  sale_rate: positiveMoney,
  freight_amount: moneyField.default('0'),
  vehicle_id: optionalId,
  driver_id: optionalId,
  notes: z.string().max(500).optional().or(z.literal('')),
})
export type DeliveryForm = z.infer<typeof deliverySchema>

export const purchaseSchema = z.object({
  date: isoDate,
  supplier_id: id,
  supplier_slip_no: z.string().max(40).optional().or(z.literal('')),
  transport_by: z.enum(['own', 'supplier']),
  vehicle_id: optionalId,
  driver_id: optionalId,
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
    purpose: z.enum(['general', 'advance', 'salary']),
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
    category: z.enum(['diesel', 'repair', 'tyre', 'insurance', 'toll', 'office', 'misc']),
    vehicle_id: optionalId,
    amount: positiveMoney,
    litres: z.string().trim().regex(/^(\d{1,9}(\.\d{1,3})?)?$/, 'Enter a number').optional().or(z.literal('')),
    meter_reading: z.string().trim().regex(/^(\d{1,9}(\.\d{1,3})?)?$/, 'Enter a number').optional().or(z.literal('')),
    paid_via: z.enum(['money_account', 'party_credit']),
    money_account_id: optionalId,
    party_id: optionalId,
    notes: z.string().max(500).optional().or(z.literal('')),
  })
  .superRefine((v, ctx) => {
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
