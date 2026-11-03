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
  // + = lena (they owe us), - = dena (we owe them); no debit/credit words on screen
  return `${formatMoney(Math.abs(n))} ${n > 0 ? 'lena' : 'dena'}`
}

/** Rounds a JS number to 2dp without float noise, as a string for the API. */
export function toDecimalString(n: number, places = 2): string {
  return (Math.round((n + Number.EPSILON) * 10 ** places) / 10 ** places).toFixed(places)
}

const whole = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 })

/** Short amount for headlines and chart axes, in the shop's own words: "36.1 lakh", "1.2 crore", "75,000". */
export function formatShort(v: Num): string {
  const n = toNumber(v)
  const a = Math.abs(n)
  const trim = (x: number, dp: number) => x.toFixed(dp).replace(/\.?0+$/, '')
  if (a >= 1e7) return `${trim(n / 1e7, a >= 1e8 ? 1 : 2)} crore`
  if (a >= 1e5) return `${trim(n / 1e5, a >= 1e6 ? 1 : 2)} lakh`
  return whole.format(n)
}
