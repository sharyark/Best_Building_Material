import { Alert, App, Button, Select, Space, Table, Tabs } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '@/api/client'
import { useGet } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { OpeningBalance } from '@/api/types'
import { DateField } from '@/components/DateField'
import { MoneyInput, QtyInput } from '@/components/DecimalInput'
import { PageHeader } from '@/components/PageHeader'
import { today } from '@/lib/date'

type Kind = OpeningBalance['kind']
type Entry = { side: 'dr' | 'cr'; amount: string }
interface OpeningStock { material_id: number; qty: string; rate: string; date: string }

const SIDE_LABELS: Record<Kind, [string, string]> = {
  party: ['They owe us (Dr)', 'We owe them (Cr)'],
  staff: ['Advance given (Dr)', 'Wages due to them (Cr)'],
  money_account: ['Balance in hand (Dr)', 'Overdraft (Cr)'],
}

function BalanceTable({ kind, rows, entries, onChange }: { kind: Kind; rows: { id: number; name: string; note?: string }[]; entries: Record<string, Entry>; onChange: (key: string, e: Entry) => void }) {
  const [drLabel, crLabel] = SIDE_LABELS[kind]
  return (
    <Table size="small" rowKey="id" pagination={false} dataSource={rows} scroll={{ x: 'max-content' }}
      columns={[
        { title: 'Name', dataIndex: 'name' },
        { title: 'Note', dataIndex: 'note' },
        { title: 'Type', width: 240, render: (_, r) => <Select style={{ width: 220 }} value={entries[`${kind}:${r.id}`]?.side ?? 'dr'} onChange={(side) => onChange(`${kind}:${r.id}`, { amount: entries[`${kind}:${r.id}`]?.amount ?? '', side })} options={[{ value: 'dr', label: drLabel }, { value: 'cr', label: crLabel }]} /> },
        { title: 'Amount', width: 200, render: (_, r) => <MoneyInput value={entries[`${kind}:${r.id}`]?.amount ?? ''} onChange={(amount) => onChange(`${kind}:${r.id}`, { side: entries[`${kind}:${r.id}`]?.side ?? 'dr', amount })} /> },
      ]} />
  )
}

export default function OpeningPage() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const lookups = useLookups()
  const existing = useGet<OpeningBalance[]>('/accounting/opening-balances')
  const existingStock = useGet<OpeningStock[]>('/stock/opening')
  const [date, setDate] = useState(today())
  const [entries, setEntries] = useState<Record<string, Entry>>({})
  const [stock, setStock] = useState<Record<number, { qty: string; rate: string }>>({})
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (loaded || !existing.data || !existingStock.data) return
    setEntries(Object.fromEntries(existing.data.map((o) => [`${o.kind}:${o.ref_id}`, { side: o.side, amount: String(o.amount) }])))
    setStock(Object.fromEntries(existingStock.data.map((s) => [s.material_id, { qty: String(s.qty), rate: String(s.rate) }])))
    if (existing.data[0]) setDate(existing.data[0].date)
    setLoaded(true)
  }, [existing.data, existingStock.data, loaded])

  const original = useMemo(() => new Map((existing.data ?? []).map((o) => [`${o.kind}:${o.ref_id}`, o])), [existing.data])
  const onChange = (key: string, e: Entry) => setEntries((cur) => ({ ...cur, [key]: e }))

  async function save() {
    setSaving(true)
    try {
      const balances = Object.entries(entries).flatMap(([key, e]) => {
        const [kind, id] = key.split(':')
        const before = original.get(key)
        const amount = e.amount || '0'
        const unchanged = before ? Number(before.amount) === Number(amount) && before.side === e.side && before.date === date : Number(amount) === 0
        return unchanged ? [] : [{ date, kind, ref_id: Number(id), side: e.side, amount }]
      })
      const stockRows = lookups.materials.flatMap((m) => {
        const row = stock[m.id]
        const before = existingStock.data?.find((s) => s.material_id === m.id)
        const qty = row?.qty || '0'
        const unchanged = before ? Number(before.qty) === Number(qty) && Number(before.rate) === Number(row?.rate || 0) : Number(qty) === 0
        return unchanged ? [] : [{ date, material_id: m.id, qty, rate: row?.rate || '0' }]
      })
      if (balances.length) await api.post('/accounting/opening-balances', balances)
      if (stockRows.length) await api.post('/stock/opening', stockRows)
      message.success(balances.length + stockRows.length ? `Saved ${balances.length + stockRows.length} opening entr${balances.length + stockRows.length === 1 ? 'y' : 'ies'}` : 'Nothing changed')
      setLoaded(false)
      await qc.invalidateQueries()
    } catch (e) {
      message.error(apiError(e).message, 6)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader title="Opening balances" subtitle="Enter balances from the old registers as of the cut-over date" />
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Everything here is posted against Opening Balance Equity as of the cut-over date. Re-saving an entry replaces the earlier opening, it never doubles it. Enter masters (customers, suppliers, materials, vehicles, staff) first." />
      <Space wrap style={{ marginBottom: 12 }}>
        <b>Cut-over date</b>
        <div style={{ width: 170 }}><DateField value={date} onChange={setDate} /></div>
        <Button type="primary" loading={saving} onClick={save}>Save opening balances</Button>
      </Space>
      <Tabs
        items={[
          { key: 'party', label: 'Customers & suppliers', children: <BalanceTable kind="party" rows={lookups.parties.map((p) => ({ id: p.id, name: p.name, note: p.type }))} entries={entries} onChange={onChange} /> },
          { key: 'staff', label: 'Staff advances / wages due', children: <BalanceTable kind="staff" rows={lookups.allStaff.map((s) => ({ id: s.id, name: s.name, note: s.role }))} entries={entries} onChange={onChange} /> },
          { key: 'money', label: 'Cash & bank', children: <BalanceTable kind="money_account" rows={lookups.moneyAccounts.map((m) => ({ id: m.id, name: m.name, note: m.kind }))} entries={entries} onChange={onChange} /> },
          {
            key: 'stock', label: 'Yard stock',
            children: (
              <Table size="small" rowKey="id" pagination={false} dataSource={lookups.materials} scroll={{ x: 'max-content' }}
                columns={[
                  { title: 'Material', dataIndex: 'name' },
                  { title: 'Physical quantity', width: 220, render: (_, m) => <QtyInput addonAfter={m.unit} value={stock[m.id]?.qty ?? ''} onChange={(qty) => setStock((s) => ({ ...s, [m.id]: { rate: s[m.id]?.rate ?? '', qty } }))} /> },
                  { title: `Cost rate per ${'unit'}`, width: 200, render: (_, m) => <MoneyInput value={stock[m.id]?.rate ?? ''} onChange={(rate) => setStock((s) => ({ ...s, [m.id]: { qty: s[m.id]?.qty ?? '', rate } }))} placeholder={String(m.default_purchase_rate)} /> },
                ]} />
            ),
          },
        ]}
      />
    </>
  )
}
