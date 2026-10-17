import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'
import { api } from '@/api/client'
import type { Delivery } from '@/api/types'
import ChallanForm from './ChallanForm'

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, size: 500 })

const delivery: Delivery = {
  id: 7, challan_no: 'CH/2026-27/00007', date: '2026-10-17', customer_id: 1, site_id: null, material_id: 2, qty: '5.000', unit: 'trolley',
  sale_rate: '3000.00', sale_amount: '15000.00', freight_amount: '0.00', cost_rate: '2000.0000', cost_amount: '10000.00',
  vehicle_id: null, driver_id: null, invoice_id: null, journal_id: 1, status: 'active', void_reason: null, notes: null,
}

function ok(config: InternalAxiosRequestConfig, data: unknown) {
  return Promise.resolve({ data, status: 200, statusText: 'OK', headers: {}, config })
}
function fail(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { data, status, statusText: 'err', headers: {}, config }
  return Promise.reject(Object.assign(new Error('fail'), { isAxiosError: true, response, config }))
}

function setup(putResponses: ((c: InternalAxiosRequestConfig) => Promise<unknown>)[]) {
  const puts: Record<string, unknown>[] = []
  api.defaults.adapter = ((config: InternalAxiosRequestConfig) => {
    const url = config.url ?? ''
    if (url === '/masters/parties') return ok(config, page([{ id: 1, type: 'customer', name: 'Ali Builders', phone: null, address: null, tax_no: null, account_id: 10, is_active: true }]))
    if (url === '/masters/materials') return ok(config, page([{ id: 2, name: 'Rait', unit: 'trolley', default_sale_rate: '3000', default_purchase_rate: '2000', hsn_code: null, is_active: true }]))
    if (url.startsWith('/masters/')) return ok(config, page([]))
    if (url === '/stock') return ok(config, [{ material_id: 2, material_name: 'Rait', unit: 'trolley', qty_on_hand: '2.000', avg_cost: '2000', value: '4000' }])
    if (url === '/masters/rate') return ok(config, { rate: '3000', source: 'default' })
    if (config.method === 'put') {
      puts.push(JSON.parse(String(config.data)))
      return putResponses.shift()!(config)
    }
    return fail(config, 404, { code: 'NOT_FOUND', message: url, details: {} })
  }) as AxiosAdapter
  return puts
}

function renderForm(onSaved = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <AntApp>
        <ChallanForm delivery={delivery} onSaved={onSaved} />
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
