import { formatCurrency, formatDrCr, formatMoney, formatQty, toDecimalString, toNumber } from './format'

describe('format', () => {
  it('groups money with two decimals (lakh style for en-IN)', () => {
    expect(formatMoney('1234567.5')).toBe('12,34,567.50')
    expect(formatMoney(0)).toBe('0.00')
    expect(formatMoney(null)).toBe('0.00')
  })
  it('prefixes the currency', () => {
    expect(formatCurrency('1500')).toBe('Rs 1,500.00')
  })
  it('shows signed balances as Dr / Cr', () => {
    expect(formatDrCr('1200')).toBe('1,200.00 Dr')
    expect(formatDrCr('-300.5')).toBe('300.50 Cr')
    expect(formatDrCr(0)).toBe('0.00')
  })
  it('trims quantity decimals', () => {
    expect(formatQty('2.500')).toBe('2.5')
    expect(formatQty('10.000')).toBe('10')
  })
  it('tolerates junk numbers', () => {
    expect(toNumber('abc')).toBe(0)
    expect(toNumber(undefined)).toBe(0)
    expect(toNumber('12.5')).toBe(12.5)
  })
  it('rounds without float noise', () => {
    expect(toDecimalString(0.1 + 0.2)).toBe('0.30')
    expect(toDecimalString(1.005)).toBe('1.01')
    expect(toDecimalString(2.5, 3)).toBe('2.500')
  })
})
