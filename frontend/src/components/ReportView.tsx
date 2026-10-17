import { Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { ReportColumn, ReportData } from '@/api/types'
import { formatDate } from '@/lib/date'
import { formatDrCr, formatMoney, formatQty } from '@/lib/format'

type Cell = string | number | null

export function renderCell(value: Cell, type: ReportColumn['type']): string {
  if (value === null || value === undefined || value === '') return ''
  switch (type) {
    case 'money':
      return formatMoney(value)
    case 'qty':
      return formatQty(value)
    case 'int':
      return String(value)
    case 'percent':
      return `${Number(value).toFixed(1)}%`
    case 'drcr':
      return formatDrCr(value)
    case 'date':
      // Totals rows put a label (e.g. "Period") in the date column; only real ISO dates are reformatted.
      return /^\d{4}-\d{2}-\d{2}$/.test(String(value)) ? formatDate(String(value)) : String(value)
    default:
      return String(value)
  }
}

const numeric = new Set<ReportColumn['type']>(['money', 'qty', 'int', 'percent', 'drcr'])

/** Renders any backend ReportTable. The Excel/PDF exports come from the same data on the server. */
export function ReportView({ data, loading }: { data?: ReportData; loading?: boolean }) {
  const columns: ColumnsType<Record<string, Cell>> = (data?.columns ?? []).map((c) => ({
    title: c.label,
    dataIndex: c.key,
    key: c.key,
    align: numeric.has(c.type) ? 'right' : 'left',
    render: (v: Cell) => <span style={{ fontVariantNumeric: 'tabular-nums' }}>{renderCell(v, c.type)}</span>,
  }))
  const totals = data?.totals
  return (
    <Table
      size="small"
      loading={loading}
      columns={columns}
      dataSource={(data?.rows ?? []).map((r, i) => ({ ...r, __key: i }))}
      rowKey="__key"
      pagination={false}
      scroll={{ x: 'max-content' }}
      locale={{ emptyText: 'No data for this selection' }}
      summary={() =>
        totals ? (
          <Table.Summary fixed>
            <Table.Summary.Row style={{ background: '#fafafa' }}>
              {(data?.columns ?? []).map((c, i) => (
                <Table.Summary.Cell key={c.key} index={i} align={numeric.has(c.type) ? 'right' : 'left'}>
                  <Typography.Text strong>{renderCell((totals[c.key] ?? null) as Cell, c.type)}</Typography.Text>
                </Table.Summary.Cell>
              ))}
            </Table.Summary.Row>
          </Table.Summary>
        ) : null
      }
    />
  )
}
