import { DatePicker } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { API_DATE, UI_DATE } from '@/lib/date'

/** Controlled by an ISO string (what the API wants), shows DD-MM-YYYY. */
export function DateField({
  id,
  value,
  onChange,
  disabled,
  autoFocus,
}: {
  id?: string
  value?: string
  onChange?: (iso: string) => void
  disabled?: boolean
  autoFocus?: boolean
}) {
  return (
    <DatePicker
      id={id}
      style={{ width: '100%' }}
      format={UI_DATE}
      value={value ? dayjs(value) : null}
      allowClear={false}
      disabled={disabled}
      autoFocus={autoFocus}
      onChange={(d: Dayjs | null) => d && onChange?.(d.format(API_DATE))}
    />
  )
}

const presets = [
  { label: 'Today', value: [dayjs(), dayjs()] as [Dayjs, Dayjs] },
  { label: 'Last 7 days', value: [dayjs().subtract(6, 'day'), dayjs()] as [Dayjs, Dayjs] },
  { label: 'This month', value: [dayjs().startOf('month'), dayjs()] as [Dayjs, Dayjs] },
  {
    label: 'Last month',
    value: [dayjs().subtract(1, 'month').startOf('month'), dayjs().subtract(1, 'month').endOf('month')] as [Dayjs, Dayjs],
  },
  { label: 'Last 30 days', value: [dayjs().subtract(29, 'day'), dayjs()] as [Dayjs, Dayjs] },
]

export type DateRange = [string, string]

export function DateRangeField({ value, onChange }: { value: DateRange; onChange: (v: DateRange) => void }) {
  return (
    <DatePicker.RangePicker
      format={UI_DATE}
      value={[dayjs(value[0]), dayjs(value[1])]}
      presets={presets}
      allowClear={false}
      onChange={(r) => r?.[0] && r[1] && onChange([r[0].format(API_DATE), r[1].format(API_DATE)])}
    />
  )
}
