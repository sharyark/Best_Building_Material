import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'
import { api } from '@/api/client'
import type { Delivery } from '@/api/types'
import ChallanForm from './ChallanForm'

// The form only offers "New customer" to roles that may edit masters (the accountant can).
vi.mock('@/app/AuthContext', () => ({
  useAuth: () => ({ user: { role: 'accountant' }, can: (perm: string) => perm === 'masters.write' }),
}))

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, size: 500 })

const delivery: Delivery = {
  id: 7, challan_no: 'CH/2026-27/00007', date: '2026-10-17', customer_id: 1, site_id: null, material_id: 2, qty: '5.000', unit: 'trolley',
  sale_rate: '3000.00', sale_amount: '15000.00', freight_amount: '0.00', cost_rate: '2000.0000', cost_amount: '10000.00',
  vehicle_id: null, driver_id: null, invoice_id: null, journal_id: 1, status: 'active', void_reason: null, notes: null,
  load_unit: null, load_size: 'full', stock_qty: '5.000', extra_material_id: null, extra_qty: null, extra_unit: null,
  extra_rate: null, extra_amount: '0.00', extra_cost_amount: '0.00', receipt_id: null,
}

function ok(config: InternalAxiosRequestConfig, data: unknown) {
  return Promise.resolve({ data, status: 200, statusText: 'OK', headers: {}, config })
}
function fail(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { data, status, statusText: 'err', headers: {}, config }
  return Promise.reject(Object.assign(new Error('fail'), { isAxiosError: true, response, config }))
}

let khataBalance = '0.00'
const posts: Record<string, unknown>[] = []

function setup(putResponses: ((c: InternalAxiosRequestConfig) => Promise<unknown>)[]) {
  const puts: Record<string, unknown>[] = []
  posts.length = 0
  api.defaults.adapter = ((config: InternalAxiosRequestConfig) => {
    const url = config.url ?? ''
    if (url === '/masters/parties') return ok(config, page([{ id: 1, type: 'customer', name: 'Ali Builders', phone: null, address: null, tax_no: null, account_id: 10, is_active: true }]))
    if (url === '/masters/materials') return ok(config, page([
      { id: 2, name: 'Rait', unit: 'trolley', default_sale_rate: '3000', default_purchase_rate: '2000', hsn_code: null, dumper_qty: '3', dumper_rate: null, bucket_qty: null, bucket_rate: null, is_active: true },
      { id: 4, name: 'Crush', unit: 'trolley', default_sale_rate: '4600', default_purchase_rate: '3000', hsn_code: null, dumper_qty: null, dumper_rate: null, bucket_qty: null, bucket_rate: null, is_active: true },
      { id: 3, name: 'Cement', unit: 'bag', default_sale_rate: '1500', default_purchase_rate: '1300', hsn_code: null, dumper_qty: null, dumper_rate: null, bucket_qty: null, bucket_rate: null, is_active: true },
    ]))
    if (url === '/masters/rate') {
      const p = config.params as { material_id: number; load_unit?: string }
      const rate = p.material_id === 3 ? '1500' : p.material_id === 4 ? '4600' : p.load_unit === 'dumper' ? '9000' : '3000'
      return ok(config, { rate, source: 'default' })
    }
    if (url === '/masters/parties/1/balance')
      return ok(config, { party_id: 1, balance: khataBalance, oldest_unpaid_date: null, days_unpaid: null, advance_low_threshold: '5000', credit_overdue_days: 7 })
    if (url === '/masters/money-accounts') return ok(config, page([{ id: 9, name: 'Cash in Hand', kind: 'cash', account_id: 50, is_active: true }]))
    if (config.method === 'post' && url === '/deliveries') {
      posts.push(JSON.parse(String(config.data)))
      return ok(config, { ...delivery, receipt_id: 77 })
    }
    if (url.startsWith('/masters/')) return ok(config, page([]))
    if (url === '/stock') return ok(config, [{ material_id: 2, material_name: 'Rait', unit: 'trolley', qty_on_hand: '2.000', avg_cost: '2000', value: '4000' }])
    if (config.method === 'put') {
      puts.push(JSON.parse(String(config.data)))
      return putResponses.shift()!(config)
    }
    return fail(config, 404, { code: 'NOT_FOUND', message: url, details: {} })
  }) as AxiosAdapter
  return puts
}

function renderForm(onSaved = vi.fn(), d: Delivery | null = delivery) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <AntApp>
        <ChallanForm delivery={d ?? undefined} onSaved={onSaved} />
      </AntApp>
    </QueryClientProvider>,
  )
  return onSaved
}

describe('ChallanForm (edit mode)', () => {
  const original = api.defaults.adapter
  afterEach(() => {
    api.defaults.adapter = original
  })

  it("counts the challan's own quantity as available, then warns when edited above stock", async () => {
    setup([])
    renderForm()
    // yard has 2 + this challan's 5 = 7 available
    expect(await screen.findByText(/Yard stock: 7 trolley of Rait/)).toBeInTheDocument()
    const qty = screen.getByDisplayValue('5.000')
    await userEvent.clear(qty)
    await userEvent.type(qty, '9')
    expect(await screen.findByText(/Stock warning: yard has 7 trolley of Rait, this challan needs 9 \(short by 2\)/)).toBeInTheDocument()
  })

  it('asks before saving into negative stock, then resends with the confirmation flag', async () => {
    const puts = setup([
      (c) => fail(c, 409, { code: 'INSUFFICIENT_STOCK', message: 'Only 7.000 in yard, trying to issue 9', details: {} }),
      (c) => ok(c, { ...delivery, qty: '9.000' }),
    ])
    const onSaved = renderForm()
    await screen.findByText(/Yard stock: 7/)
    const qty = screen.getByDisplayValue('5.000')
    await userEvent.clear(qty)
    await userEvent.type(qty, '9')
    await userEvent.click(screen.getByRole('button', { name: /Save changes/ }))

    expect(await screen.findByText('Not enough stock in the yard')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Save anyway' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(puts).toHaveLength(2)
    expect(puts[0]).toMatchObject({ qty: '9', allow_negative_stock: false, customer_id: 1, material_id: 2 })
    expect(puts[1]).toMatchObject({ qty: '9', allow_negative_stock: true })
    // editing never sends a new client_ref (the challan already exists)
    expect(puts[0]).not.toHaveProperty('client_ref')
  })

  it('blocks submit and shows field errors for an invalid quantity', async () => {
    const puts = setup([])
    renderForm()
    await screen.findByText(/Yard stock: 7/)
    const qty = screen.getByDisplayValue('5.000')
    await userEvent.clear(qty)
    await userEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    expect(await screen.findAllByText(/Enter a number|Required/)).not.toHaveLength(0)
    expect(puts).toHaveLength(0)
  })
})

describe('ChallanForm loads', () => {
  const original = api.defaults.adapter
  afterEach(() => {
    api.defaults.adapter = original
  })

  it('half trolley halves the total and stock needed, and sends the number of loads', async () => {
    const puts = setup([(c) => ok(c, { ...delivery, load_size: 'half' })])
    const onSaved = renderForm()
    await screen.findByText(/Yard stock: 7/)
    await userEvent.click(screen.getByLabelText('Load'))
    await userEvent.click(await screen.findByTitle('Half trolley'))
    expect(await screen.findByText(/7,500\.00|7500\.00/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(puts[0]).toMatchObject({ qty: '5.000', load_size: 'half', load_unit: null, extra_material_id: null })
  })

  it('half trolley can be split: the other half is a second material at half a trolley', async () => {
    const puts = setup([(c) => ok(c, delivery)])
    const onSaved = renderForm(vi.fn(), { ...delivery, qty: '0.500', stock_qty: '0.500', load_size: 'half', sale_amount: '1500.00' })
    await screen.findByText(/Yard stock/)
    await userEvent.click(screen.getByLabelText('Other half (optional)'))
    await userEvent.click(await screen.findByTitle('Crush'))
    // auto-filled per-trolley rate for the other half: 0.5 x 3000 + 0.5 x 4600
    const crushRate = await screen.findByLabelText(/Crush rate/)
    await waitFor(() => expect((crushRate as HTMLInputElement).value).toBe('4600'))
    await waitFor(() => expect(screen.getByText(/^Total:/).textContent).toMatch(/3,800/))
    await userEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0]).toMatchObject({ qty: '1', load_size: 'half', extra_material_id: 4, extra_qty: '0.5', extra_rate: '4600' })
    expect(puts[0]).not.toHaveProperty('other_half_id')
    void onSaved
  }, 15_000)

  it('full trolley + cement asks for bags and sends cement as the second material', async () => {
    const puts = setup([(c) => ok(c, delivery)])
    const onSaved = renderForm()
    await screen.findByText(/Yard stock: 7/)
    await userEvent.click(screen.getByLabelText('Load'))
    await userEvent.click(await screen.findByTitle('Full trolley + cement'))
    const bags = await screen.findByLabelText(/Cement \(bags\)/)
    await userEvent.type(bags, '20')
    // the cement rate fills itself from the customer's rate / material default
    await waitFor(() => expect((screen.getByLabelText(/Cement rate/) as HTMLInputElement).value).toBe('1500'))
    await userEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(puts[0]).toMatchObject({ load_size: 'full', extra_material_id: 3, extra_qty: '20', extra_rate: '1500' })
    expect(puts[0]).not.toHaveProperty('with_cement')
  }, 15_000)

  it('a dumper challan opens on Dumper, shows the trolley conversion and sends load_unit', async () => {
    const puts = setup([(c) => ok(c, delivery)])
    const onSaved = renderForm(vi.fn(), { ...delivery, load_unit: 'dumper', unit: 'dumper', qty: '1.000', stock_qty: '3.000', sale_rate: '9000.00' })
    expect(await screen.findByText(/1 dumper = 3 trolley/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0]).toMatchObject({ load_unit: 'dumper', qty: '1.000', load_size: 'full' })
    void onSaved
  })
})

describe('ChallanForm payment (new challan)', () => {
  const original = api.defaults.adapter
  afterEach(() => {
    api.defaults.adapter = original
    khataBalance = '0.00'
    localStorage.clear()
  })

  async function fillChallan() {
    await userEvent.click(screen.getByLabelText('Customer'))
    await userEvent.click((await screen.findAllByTitle('Ali Builders'))[0])
    await userEvent.click(screen.getByLabelText('Material'))
    await userEvent.click((await screen.findAllByTitle('Rait (trolley)'))[0])
    await userEvent.type(screen.getByLabelText('Trolleys'), '2')
    await waitFor(() => expect(screen.getByText(/^Total:/).textContent).toMatch(/6,000/))
  }

  it('warns when the advance runs out and "Take more advance" receives the shortfall', async () => {
    khataBalance = '-5000.00'
    setup([])
    renderForm(vi.fn(), null)
    await fillChallan()
    // the khata tag under the customer shows the advance
    expect(await screen.findByText((_, el) => Boolean(el?.classList.contains('ant-tag') && /Advance: .*5,000/.test(el.textContent ?? '')))).toBeInTheDocument()
    expect(await screen.findByText(/runs out with this challan/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Take more advance' }))
    expect(screen.queryByText(/runs out with this challan/)).not.toBeInTheDocument()
    expect(screen.getByText(/Khata will be clear/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Save & next/ }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toMatchObject({ payment: { amount: '1000.00', money_account_id: 9, mode: 'cash' } })
    expect(posts[0]).not.toHaveProperty('pay')
  }, 20_000)

  it('"Put it on udhaar" hides the warning and saves without a payment', async () => {
    khataBalance = '-5000.00'
    setup([])
    renderForm(vi.fn(), null)
    await fillChallan()
    await userEvent.click(await screen.findByRole('button', { name: 'Put it on udhaar' }))
    expect(screen.queryByText(/runs out with this challan/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Save & next/ }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).not.toHaveProperty('payment')
  }, 20_000)

  it('paid in full sends the challan total as the payment', async () => {
    setup([])
    renderForm(vi.fn(), null)
    await fillChallan()
    await userEvent.click(screen.getByText('Paid in full'))
    await userEvent.click(screen.getByRole('button', { name: /Save & next/ }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toMatchObject({ payment: { amount: '6000.00', money_account_id: 9 } })
  }, 20_000)
})
