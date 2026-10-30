import { deliverySchema, expenseSchema, paymentSchema, positiveMoney, purchaseSchema, voidSchema } from './schemas'

const delivery = { date: '2026-10-17', customer_id: 1, material_id: 2, qty: '2', sale_rate: '3000', freight_amount: '0' }

describe('money and quantity validation (mirrors the backend rules)', () => {
  it.each(['0', '-5', '1.234', 'abc', '', '1e5'])('rejects %j as a money amount', (v) => {
    expect(positiveMoney.safeParse(v).success).toBe(false)
  })
  it.each(['1', '0.5', '2500.75', '99999999999.99'])('accepts %j', (v) => {
    expect(positiveMoney.safeParse(v).success).toBe(true)
  })
})

describe('deliverySchema', () => {
  it('accepts a normal challan', () => {
    expect(deliverySchema.safeParse(delivery).success).toBe(true)
  })
  it('requires customer, material, positive qty and a rate', () => {
    const r = deliverySchema.safeParse({ ...delivery, customer_id: undefined, qty: '0', sale_rate: '' })
    expect(r.success).toBe(false)
    if (!r.success) {
      const fields = r.error.issues.map((i) => i.path[0])
      expect(fields).toEqual(expect.arrayContaining(['customer_id', 'qty', 'sale_rate']))
    }
  })
  it('allows at most 3 quantity decimals', () => {
    expect(deliverySchema.safeParse({ ...delivery, qty: '1.2345' }).success).toBe(false)
    expect(deliverySchema.safeParse({ ...delivery, qty: '1.234' }).success).toBe(true)
  })
  it('needs bags and a rate when cement rides along', () => {
    const r = deliverySchema.safeParse({ ...delivery, with_cement: true, extra_qty: '', extra_rate: '' })
    expect(r.success).toBe(false)
    if (!r.success) expect(r.error.issues.map((i) => i.path[0])).toEqual(expect.arrayContaining(['extra_qty', 'extra_rate']))
    expect(deliverySchema.safeParse({ ...delivery, with_cement: true, extra_qty: '20', extra_rate: '1500' }).success).toBe(true)
  })
})

describe('purchaseSchema', () => {
  it('needs at least one line', () => {
    const base = { date: '2026-10-17', supplier_id: 1, transport_by: 'supplier' as const }
    expect(purchaseSchema.safeParse({ ...base, lines: [] }).success).toBe(false)
    expect(purchaseSchema.safeParse({ ...base, lines: [{ material_id: 1, qty: '10', rate: '2000' }] }).success).toBe(true)
  })
})

describe('paymentSchema', () => {
  const base = { date: '2026-10-17', direction: 'in', money_account_id: 1, mode: 'cash', purpose: 'general', amount: '500' }
  it('needs the chosen counterparty', () => {
    expect(paymentSchema.safeParse({ ...base, counterparty: 'party' }).success).toBe(false)
    expect(paymentSchema.safeParse({ ...base, counterparty: 'party', party_id: 3 }).success).toBe(true)
    expect(paymentSchema.safeParse({ ...base, counterparty: 'staff', party_id: 3 }).success).toBe(false)
    expect(paymentSchema.safeParse({ ...base, counterparty: 'staff', staff_id: 4 }).success).toBe(true)
  })
})

describe('expenseSchema', () => {
  const base = { date: '2026-10-17', category: 'diesel', amount: '1500', paid_via: 'money_account' }
  it('needs the account matching how it was paid', () => {
    expect(expenseSchema.safeParse(base).success).toBe(false)
    expect(expenseSchema.safeParse({ ...base, money_account_id: 1 }).success).toBe(true)
    expect(expenseSchema.safeParse({ ...base, paid_via: 'party_credit' }).success).toBe(false)
    expect(expenseSchema.safeParse({ ...base, paid_via: 'party_credit', party_id: 9 }).success).toBe(true)
  })
})

describe('voidSchema', () => {
  it('forces a real reason', () => {
    expect(voidSchema.safeParse({ reason: 'ab' }).success).toBe(false)
    expect(voidSchema.safeParse({ reason: '  ' }).success).toBe(false)
    expect(voidSchema.safeParse({ reason: 'entered twice' }).success).toBe(true)
  })
})
