import { formatDrCr, formatMoney } from '@/lib/format'

export function Money({ value, drcr = false, bold = false }: { value: string | number | null | undefined; drcr?: boolean; bold?: boolean }) {
  const n = Number(value ?? 0)
  const color = drcr ? (n > 0 ? '#1f4e79' : n < 0 ? '#b45309' : undefined) : undefined
  return <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: bold ? 600 : undefined, color }}>{drcr ? formatDrCr(value) : formatMoney(value)}</span>
}
