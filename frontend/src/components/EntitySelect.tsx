import { PlusOutlined } from '@ant-design/icons'
import { Button, Divider, Select, type SelectProps } from 'antd'
import type { RefSelectProps } from 'antd/es/select'
import { forwardRef, useState } from 'react'

export interface Option {
  value: number | string
  label: string
}

interface Props extends Omit<SelectProps<number | string | null>, 'options' | 'onChange' | 'value'> {
  options: Option[]
  value?: number | string | null
  onChange?: (v: number | null) => void
  /** Adds a "+ New ..." entry at the bottom of the list; receives whatever was typed in the search box. */
  onAdd?: (typed: string) => void
  addLabel?: string
}

/** Searchable select (type to filter). Clearing gives `null`, which the schemas treat as "not set". */
export const EntitySelect = forwardRef<RefSelectProps, Props>(function EntitySelect(
  { options, value, onChange, placeholder = 'Select…', allowClear = true, onAdd, addLabel = 'Add new', ...rest },
  ref,
) {
  const [search, setSearch] = useState('')
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
      onSearch={setSearch}
      onDropdownVisibleChange={(open) => {
        if (!open) setSearch('')
      }}
      dropdownRender={
        onAdd
          ? (menu) => (
              <>
                {menu}
                <Divider style={{ margin: '4px 0' }} />
                <Button
                  type="link"
                  block
                  icon={<PlusOutlined />}
                  style={{ textAlign: 'left' }}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => onAdd(search)}
                >
                  {addLabel}
                  {search ? `: "${search}"` : ''}
                </Button>
              </>
            )
          : undefined
      }
      {...rest}
    />
  )
})

export function optionsOf<T extends { id: number; name: string }>(rows: T[], label?: (r: T) => string): Option[] {
  return rows.map((r) => ({ value: r.id, label: label ? label(r) : r.name }))
}
