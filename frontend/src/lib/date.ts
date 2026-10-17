import dayjs, { type Dayjs } from 'dayjs'

/** UI shows DD-MM-YYYY; the API speaks ISO (YYYY-MM-DD). */
export const UI_DATE = 'DD-MM-YYYY'
export const API_DATE = 'YYYY-MM-DD'

export function formatDate(v: string | Date | Dayjs | null | undefined): string {
  if (!v) return ''
  const d = dayjs(v)
  return d.isValid() ? d.format(UI_DATE) : ''
}

export function toApiDate(v: Dayjs | Date | string): string {
  return dayjs(v).format(API_DATE)
}

export function today(): string {
  return dayjs().format(API_DATE)
}

export function startOfMonth(d: Dayjs | string = dayjs()): string {
  return dayjs(d).startOf('month').format(API_DATE)
}
