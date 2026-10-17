import { Input, type InputProps, type InputRef } from 'antd'
import { forwardRef } from 'react'
import { CURRENCY } from '@/lib/config'

interface Props extends Omit<InputProps, 'value' | 'onChange' | 'type'> {
  value?: string
  onChange?: (v: string) => void
  places?: number
}

/** Text input that only accepts digits and one dot, capped at `places` decimals. Values stay strings. */
export function sanitizeDecimal(raw: string, places: number): string {
  let s = raw.replace(/[^\d.]/g, '')
  const dot = s.indexOf('.')
  if (dot !== -1) s = s.slice(0, dot + 1) + s.slice(dot + 1).replace(/\./g, '').slice(0, places)
  if (places === 0) s = s.replace('.', '')
  return s.replace(/^0+(?=\d)/, '')
}

const DecimalInput = forwardRef<InputRef, Props>(function DecimalInput({ value, onChange, places = 2, ...rest }, ref) {
  return (
    <Input
      ref={ref}
      inputMode="decimal"
      autoComplete="off"
      value={value ?? ''}
      onChange={(e) => onChange?.(sanitizeDecimal(e.target.value, places))}
      style={{ textAlign: 'right', ...rest.style }}
      {...rest}
    />
  )
})

export const MoneyInput = forwardRef<InputRef, Omit<Props, 'places'>>(function MoneyInput(props, ref) {
  return <DecimalInput ref={ref} places={2} addonBefore={CURRENCY} {...props} />
})

export const QtyInput = forwardRef<InputRef, Omit<Props, 'places'>>(function QtyInput(props, ref) {
  return <DecimalInput ref={ref} places={3} {...props} />
})

export default DecimalInput
