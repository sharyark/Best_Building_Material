import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { MoneyInput, QtyInput, sanitizeDecimal } from './DecimalInput'

describe('sanitizeDecimal', () => {
  it.each([
    ['abc12.345', 2, '12.34'],
    ['1.2.3', 2, '1.23'],
    ['007', 2, '7'],
    ['0.5', 2, '0.5'],
    ['12,500', 2, '12500'],
    ['2.5559', 3, '2.555'],
    ['9.9', 0, '9'],
  ])('%j with %i places -> %j', (raw, places, expected) => {
    expect(sanitizeDecimal(raw, places)).toBe(expected)
  })
})

function Harness({ qty = false }: { qty?: boolean }) {
  const [v, setV] = useState('')
  const Input = qty ? QtyInput : MoneyInput
  return <><Input value={v} onChange={setV} aria-label="amount" /><output>{v}</output></>
}

describe('inputs', () => {
  it('money keeps strings with max 2 decimals and shows the currency', async () => {
    render(<Harness />)
    await userEvent.type(screen.getByLabelText('amount'), '1x2.345')
    expect(screen.getByRole('status')).toHaveTextContent('12.34')
    expect(screen.getByText('Rs')).toBeInTheDocument()
  })
  it('quantity allows 3 decimals', async () => {
    render(<Harness qty />)
    await userEvent.type(screen.getByLabelText('amount'), '2.5559')
    expect(screen.getByRole('status')).toHaveTextContent('2.555')
  })
})
