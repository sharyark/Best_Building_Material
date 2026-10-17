import { Select, type SelectProps } from 'antd'
import { forwardRef } from 'react'
import type { RefSelectProps } from 'antd/es/select'

export interface Option {
  value: number | string
  label: string
}

interface Props extends Omit<SelectProps<number | string | null>, 'options' | 'onChange' | 'value'> {
  options: Option[]
  value?: number | string | null
  onChange?: (v: number | null) => void
}

/** Searchable select (type to filter). Clearing gives `null`, which the schemas treat as "not set". */
export const EntitySelect = forwardRef<RefSelectProps, Props>(function EntitySelect(
  { options, value, onChange, placeholder = 'Select…', allowClear = true, ...rest },
  ref,
) {
  return (
    <Select<number | string | null>
      ref={ref}
      showSearch
      optionFilterProp="label"
      style={{ width: '100%' }}
      placeholder={placeholder}
      allowClear={allowClear}
      options={options}
      value={value ?? undefined}
      onChange={(v) => onChange?.(v === undefined || v === null ? null : Number(v))}
      {...rest}
    />
  )
})

export function optionsOf<T extends { id: number; name: string }>(rows: T[], label?: (r: T) => string): Option[] {
  return rows.map((r) => ({ value: r.id, label: label ? label(r) : r.name }))
}
