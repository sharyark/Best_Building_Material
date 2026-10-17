import { render, screen } from '@testing-library/react'
import type { ReportData } from '@/api/types'
import { ReportView, renderCell } from './ReportView'

const data: ReportData = {
  title: 'Khata', subtitle: null, meta: {},
  columns: [
    { key: 'date', label: 'Date', type: 'date' },
    { key: 'debit', label: 'Debit', type: 'money' },
    { key: 'balance', label: 'Balance', type: 'drcr' },
    { key: 'qty', label: 'Qty', type: 'qty' },
  ],
  rows: [{ date: '2026-10-01', debit: '6500.00', balance: '6500.00', qty: '2.500' }, { date: '2026-10-02', debit: null, balance: '-1200.00', qty: '1.000' }],
  totals: { date: 'Total', debit: '6500.00', balance: '-1200.00', qty: null },
}

describe('ReportView', () => {
  it('formats each column by type', () => {
    render(<ReportView data={data} />)
    expect(screen.getByText('01-10-2026')).toBeInTheDocument()
    expect(screen.getAllByText('6,500.00').length).toBeGreaterThan(0)
    expect(screen.getByText('6,500.00 Dr')).toBeInTheDocument()
    expect(screen.getAllByText('1,200.00 Cr').length).toBeGreaterThan(0)
    expect(screen.getByText('2.5')).toBeInTheDocument()
  })
  it('renders the totals row', () => {
    render(<ReportView data={data} />)
    expect(screen.getByText('Total')).toBeInTheDocument()
  })
  it('shows an empty state', () => {
    render(<ReportView data={{ ...data, rows: [], totals: null }} />)
    expect(screen.getByText('No data for this selection')).toBeInTheDocument()
  })
  it('renders blanks and percentages', () => {
    expect(renderCell(null, 'money')).toBe('')
    expect(renderCell('12.345', 'percent')).toBe('12.3%')
  })
})
