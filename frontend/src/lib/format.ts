import { CURRENCY, LOCALE } from './config'

type Num = string | number | null | undefined

export function toNumber(v: Num): number {
  if (v === null || v === undefined || v === '') return 0
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : 0
}

const money = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const plain = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 3 })

/** Display only. Amounts travel as decimal strings; we never do money math on floats for storage. */
export function formatMoney(v: Num): string {
  return money.format(toNumber(v))
}

export function formatCurrency(v: Num): string {
  return `${CURRENCY} ${formatMoney(v)}`
}

export function formatQty(v: Num): string {
  return plain.format(toNumber(v))
}

/** Signed debit-positive balance -> "1,200.00 Dr" / "300.00 Cr". */
export function formatDrCr(v: Num): string {
  const n = toNumber(v)
  if (n === 0) return formatMoney(0)
  return `${formatMoney(Math.abs(n))} ${n > 0 ? 'Dr' : 'Cr'}`
}

/** Rounds a JS number to 2dp without float noise, as a string for the API. */
export function toDecimalString(n: number, places = 2): string {
  return (Math.round((n + Number.EPSILON) * 10 ** places) / 10 ** places).toFixed(places)
}
