export type FilterKind = 'range' | 'date' | 'asOf' | 'customerOrSupplier' | 'staff' | 'moneyAccount' | 'groupBy' | 'outstandingKind'

export interface ReportConfig {
  key: string
  title: string
  description: string
  perm: string
  endpoint: (v: ReportValues) => string
  /** Report can't run until these are chosen (e.g. which party's khata). */
  needs?: ('party' | 'staff')[]
  filters: FilterKind[]
  groupOptions?: { value: string; label: string }[]
  defaultDays?: number
}

export interface ReportValues {
  range: [string, string]
  date: string
  party: number | null
  staff: number | null
  account: number | null
  group: string
  kind: string
}

export const REPORTS: ReportConfig[] = [
  { key: 'khata', title: 'Party khata (customer / supplier)', description: 'Date-wise Dr/Cr with running balance. PDF and WhatsApp share.', perm: 'report.khata', endpoint: (v) => `/reports/khata/${v.party}`, needs: ['party'], filters: ['customerOrSupplier', 'range'], defaultDays: 90 },
  { key: 'outstanding', title: 'Outstanding & aging', description: 'Who owes how much, for how long (0-30, 31-60, 60+ days).', perm: 'report.outstanding', endpoint: () => '/reports/outstanding', filters: ['asOf', 'outstandingKind'] },
  { key: 'cash-book', title: 'Cash book / bank book', description: 'Daily money in and out with closing balance.', perm: 'report.cashbook', endpoint: () => '/reports/cash-book', filters: ['moneyAccount', 'range'] },
  { key: 'day-book', title: 'Day book', description: 'Every entry of a single date.', perm: 'report.daybook', endpoint: () => '/reports/day-book', filters: ['date'] },
  { key: 'yard-stock', title: 'Yard stock', description: 'Opening + in - out ± adjustment = closing quantity and value.', perm: 'report.stock', endpoint: () => '/reports/yard-stock', filters: ['range'], defaultDays: 30 },
  { key: 'staff-khata', title: 'Labour / driver khata', description: 'Attendance, wages earned, advances and balance payable.', perm: 'report.labour_khata', endpoint: (v) => `/reports/staff-khata/${v.staff}`, needs: ['staff'], filters: ['staff', 'range'], defaultDays: 30 },
  { key: 'vehicle-pnl', title: 'Vehicle P&L', description: 'Per vehicle: trips, freight and rent, diesel, repair, driver salary, profit.', perm: 'report.profit', endpoint: () => '/reports/vehicle-pnl', filters: ['range'] },
  { key: 'material-margin', title: 'Material margin', description: 'Per material: sale vs purchase rate and total margin.', perm: 'report.profit', endpoint: () => '/reports/material-margin', filters: ['range'] },
  { key: 'labour-cost', title: 'Labour cost summary', description: 'Total wages per week / month, site, vehicle or worker.', perm: 'report.profit', endpoint: () => '/reports/labour-cost', filters: ['range', 'groupBy'], groupOptions: [{ value: 'month', label: 'By month' }, { value: 'week', label: 'By week' }, { value: 'vehicle', label: 'By vehicle' }, { value: 'site', label: 'By site' }, { value: 'staff', label: 'By worker' }] },
  { key: 'rental-income', title: 'Rental income', description: 'Hours / trips per machine, income, unpaid rent.', perm: 'report.profit', endpoint: () => '/reports/rental-income', filters: ['range', 'groupBy'], groupOptions: [{ value: 'vehicle', label: 'By machine' }, { value: 'customer', label: 'By customer' }] },
  { key: 'profit-loss', title: 'Profit & loss', description: 'Income minus expenses for the period.', perm: 'report.profit', endpoint: () => '/reports/profit-loss', filters: ['range'] },
]

export const reportByKey = (key: string) => REPORTS.find((r) => r.key === key)
