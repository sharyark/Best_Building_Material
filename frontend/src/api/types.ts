/** Mirrors the backend response models. Decimals arrive as strings (never floats). */
export type Decimal = string

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export type Role = 'admin' | 'accountant' | 'driver' | 'customer'

export interface User {
  id: number
  name: string
  phone: string
  email: string | null
  role: Role
  staff_id: number | null
  party_id: number | null
  is_active: boolean
}
export interface Me extends User {
  permissions: string[]
}
export interface TokenOut {
  access_token: string
  expires_in: number
  user: Me
}

export interface ApiErrorBody {
  code: string
  message: string
  details: Record<string, unknown>
}

export type PartyType = 'customer' | 'supplier' | 'both'
export interface Party {
  id: number
  type: PartyType
  name: string
  phone: string | null
  address: string | null
  tax_no: string | null
  account_id: number | null
  is_active: boolean
  balance?: Decimal | null
}
export interface Site {
  id: number
  party_id: number
  name: string
  address: string | null
}
export type Unit = 'trolley' | 'cft' | 'ton' | 'bag' | 'piece' | 'brass'
export interface Material {
  id: number
  name: string
  unit: Unit
  default_sale_rate: Decimal
  default_purchase_rate: Decimal
  hsn_code: string | null
  /** Stock (in `unit`) one full dumper / loader bucket holds; null = not sold that way. */
  dumper_qty: Decimal | null
  dumper_rate: Decimal | null
  bucket_qty: Decimal | null
  bucket_rate: Decimal | null
  is_active: boolean
}
export interface RateCard {
  id: number
  party_id: number
  material_id: number
  rate: Decimal
  effective_from: string
}
export type VehicleType = 'tractor_trolley' | 'dumper' | 'loader'
export interface Vehicle {
  id: number
  type: VehicleType
  reg_no: string | null
  name: string
  capacity: Decimal | null
  meter_type: 'km' | 'hours'
  is_active: boolean
}
export type StaffRole = 'driver' | 'operator' | 'labour' | 'helper' | 'munshi'
export type WageType = 'monthly' | 'daily' | 'per_trip'
export interface Staff {
  id: number
  name: string
  phone: string | null
  role: StaffRole
  wage_type: WageType
  wage_amount: Decimal
  default_vehicle_id: number | null
  account_id: number | null
  is_active: boolean
  balance?: Decimal | null
}
export interface MoneyAccount {
  id: number
  name: string
  kind: 'cash' | 'bank' | 'wallet'
  account_id: number | null
  is_active: boolean
  balance?: Decimal | null
}

interface DocBase {
  id: number
  status: 'active' | 'void'
  void_reason: string | null
  journal_id: number | null
  notes: string | null
}
export interface PurchaseLine {
  id: number
  material_id: number
  qty: Decimal
  rate: Decimal
  amount: Decimal
}
export interface Purchase extends DocBase {
  bill_no: string
  supplier_slip_no: string | null
  date: string
  supplier_id: number
  total: Decimal
  vehicle_id: number | null
  driver_id: number | null
  transport_by: 'own' | 'supplier'
  lines: PurchaseLine[]
}
export interface Delivery extends DocBase {
  challan_no: string
  date: string
  customer_id: number
  site_id: number | null
  material_id: number
  qty: Decimal
  unit: string
  sale_rate: Decimal
  sale_amount: Decimal
  freight_amount: Decimal
  load_unit: LoadUnit | null
  load_size: LoadSize
  stock_qty: Decimal
  cost_rate: Decimal
  cost_amount: Decimal
  extra_material_id: number | null
  extra_qty: Decimal | null
  extra_unit: string | null
  extra_rate: Decimal | null
  extra_amount: Decimal
  extra_cost_amount: Decimal
  vehicle_id: number | null
  driver_id: number | null
  invoice_id: number | null
  receipt_id: number | null
}
export type LoadUnit = 'dumper' | 'bucket'
export type LoadSize = 'full' | 'half'
export interface Rental extends DocBase {
  rental_no: string
  date: string
  customer_id: number
  site_id: number | null
  vehicle_id: number
  operator_id: number | null
  basis: 'hour' | 'trip' | 'day'
  qty: Decimal
  rate: Decimal
  amount: Decimal
  invoice_id: number | null
}
export interface Payment extends DocBase {
  voucher_no: string
  date: string
  direction: 'in' | 'out'
  party_id: number | null
  staff_id: number | null
  money_account_id: number
  mode: 'cash' | 'bank' | 'cheque' | 'online'
  purpose: 'general' | 'advance' | 'salary'
  ref_no: string | null
  amount: Decimal
}
export type ExpenseCategory = 'diesel' | 'repair' | 'tyre' | 'insurance' | 'toll' | 'office' | 'misc'
export interface Expense extends DocBase {
  voucher_no: string
  date: string
  category: ExpenseCategory
  vehicle_id: number | null
  amount: Decimal
  litres: Decimal | null
  meter_reading: Decimal | null
  paid_via: 'money_account' | 'party_credit'
  money_account_id: number | null
  party_id: number | null
}
export interface Invoice extends DocBase {
  invoice_no: string
  date: string
  customer_id: number
  site_id: number | null
  period_from: string
  period_to: string
  subtotal: Decimal
  tax_rate: Decimal
  tax_amount: Decimal
  total: Decimal
  is_tax_invoice: boolean
}
export interface InvoiceLine {
  kind: 'challan' | 'rental'
  doc_id: number
  doc_no: string
  date: string
  description: string
  qty: Decimal
  unit: string
  rate: Decimal
  amount: Decimal
}
export interface InvoiceDetail extends Invoice {
  lines: InvoiceLine[]
}
export interface Uninvoiced {
  deliveries: Delivery[]
  rentals: Rental[]
}

export interface StockItem {
  material_id: number
  material_name: string
  unit: string
  qty_on_hand: Decimal
  avg_cost: Decimal
  value: Decimal
}
export interface StockCount {
  id: number
  date: string
  material_id: number
  system_qty: Decimal
  physical_qty: Decimal
  diff: Decimal
  journal_id: number | null
}

export type AttendanceStatus = 'present' | 'half' | 'absent'
export interface Attendance {
  id: number
  date: string
  staff_id: number
  status: AttendanceStatus
  overtime_hours: Decimal
  site_id: number | null
  vehicle_id: number | null
  journal_id: number | null
}
export interface SettlementPreview {
  staff_id: number
  period_from: string
  period_to: string
  wage_type: WageType
  days: Decimal
  trips: number
  gross: Decimal
  accrues_on_settlement: boolean
  advances_in_period: Decimal
  current_balance: Decimal
}
export interface Settlement {
  id: number
  staff_id: number
  period_from: string
  period_to: string
  days: Decimal
  trips: number
  gross: Decimal
  advances_adjusted: Decimal
  deductions: Decimal
  net_payable: Decimal
  status: 'active' | 'void'
  void_reason: string | null
  journal_id: number | null
  notes: string | null
}

export interface ReportColumn {
  key: string
  label: string
  type: 'text' | 'date' | 'money' | 'qty' | 'int' | 'drcr' | 'percent'
}
export interface ReportData {
  title: string
  subtitle: string | null
  columns: ReportColumn[]
  rows: Record<string, string | number | null>[]
  totals: Record<string, string | number | null> | null
  meta: Record<string, unknown>
}
export interface Dashboard {
  date: string
  trips_today: number
  trips_by_material: { material: string; unit: string; trips: number; qty: Decimal }[]
  sales_today: Decimal
  sales_month: Decimal
  cash_in_hand: Decimal
  bank_balance: Decimal
  total_receivable: Decimal
  total_payable: Decimal
  staff_payable: Decimal
  staff_advances: Decimal
  stock_value: Decimal
  top_debtors: { party_id: number; name: string; balance: Decimal }[]
  advance_low: { party_id: number; name: string; advance: Decimal }[]
  old_udhaar: { party_id: number; name: string; balance: Decimal; days: number }[]
  advance_low_threshold: Decimal
  credit_overdue_days: number
}

/** A customer's khata in one number: positive = owes us (udhaar), negative = advance with us. */
export interface PartyBalance {
  party_id: number
  balance: Decimal
  oldest_unpaid_date: string | null
  days_unpaid: number | null
  advance_low_threshold: Decimal
  credit_overdue_days: number
}

export interface PeriodLock {
  month: string
  locked_by: number | null
  locked_at: string
}
export interface OpeningBalance {
  kind: 'party' | 'staff' | 'money_account'
  ref_id: number
  name: string
  date: string
  side: 'dr' | 'cr'
  amount: Decimal
}
export interface AuditLog {
  id: number
  user_id: number | null
  action: 'create' | 'update' | 'void' | 'delete'
  entity: string
  entity_id: number | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  ip: string | null
  at: string
}
export interface TrialBalance {
  upto: string | null
  rows: { account_id: number; code: string; name: string; type: string; debit: Decimal; credit: Decimal }[]
  total_debit: Decimal
  total_credit: Decimal
  balanced: boolean
}
