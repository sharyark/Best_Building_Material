import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import { Alert, App, Button, InputNumber, Popover, Segmented, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'
import { api, apiError } from '@/api/client'
import { useGet } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Attendance, AttendanceStatus, Staff } from '@/api/types'
import { usePermission } from '@/hooks/usePermission'
import { API_DATE } from '@/lib/date'
import { useQueryClient } from '@tanstack/react-query'

type Cell = { status: AttendanceStatus; overtime_hours: string }
const COLORS: Record<AttendanceStatus, string> = { present: 'green', half: 'orange', absent: 'red' }
const SHORT: Record<AttendanceStatus, string> = { present: 'P', half: 'H', absent: 'A' }
const WEIGHT: Record<AttendanceStatus, number> = { present: 1, half: 0.5, absent: 0 }

function CellEditor({ cell, disabled, onChange }: { cell?: Cell; disabled: boolean; onChange: (c: Cell) => void }) {
  const content = (
    <Space direction="vertical" size={8}>
      <Segmented
        value={cell?.status}
        options={[{ value: 'present', label: 'Present' }, { value: 'half', label: 'Half' }, { value: 'absent', label: 'Absent' }]}
        onChange={(v) => onChange({ status: v as AttendanceStatus, overtime_hours: cell?.overtime_hours ?? '0' })}
      />
      <Space>
        <span>Overtime hrs</span>
        <InputNumber
          min={0} max={16} step={0.5} size="small" disabled={!cell} value={Number(cell?.overtime_hours ?? 0)}
          onChange={(v) => cell && onChange({ ...cell, overtime_hours: String(v ?? 0) })}
        />
      </Space>
    </Space>
  )
  const tag = (
    <Tag
      color={cell ? COLORS[cell.status] : 'default'}
      style={{ cursor: disabled ? 'default' : 'pointer', minWidth: 38, textAlign: 'center', margin: 0 }}
      onClick={() => {
        if (disabled) return
        // Quick tap cycles unmarked -> present -> half -> absent -> present
        const next: AttendanceStatus = !cell ? 'present' : cell.status === 'present' ? 'half' : cell.status === 'half' ? 'absent' : 'present'
        onChange({ status: next, overtime_hours: cell?.overtime_hours ?? '0' })
      }}
    >
      {cell ? SHORT[cell.status] : '–'}
      {cell && Number(cell.overtime_hours) > 0 ? `+${cell.overtime_hours}` : ''}
    </Tag>
  )
  return disabled ? tag : <Popover content={content} trigger="contextMenu" title="Mark attendance (tap to cycle, right-click for details)">{tag}</Popover>
}

export default function AttendanceGrid() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const canWrite = usePermission('attendance.write')
  const lookups = useLookups()
  const [weekStart, setWeekStart] = useState(() => dayjs().startOf('week').add(1, 'day'))
  const [edits, setEdits] = useState<Record<string, Cell>>({})
  const [saving, setSaving] = useState(false)
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => weekStart.add(i, 'day')), [weekStart])
  const from = days[0].format(API_DATE)
  const to = days[6].format(API_DATE)
  const { data: rows = [], isLoading } = useGet<Attendance[]>('/labour/attendance', { date_from: from, date_to: to })
  const staff = lookups.staff.filter((s) => s.role !== 'munshi')

  const saved = useMemo(() => {
    const m = new Map<string, Cell>()
    rows.forEach((r) => m.set(`${r.staff_id}|${r.date}`, { status: r.status, overtime_hours: String(r.overtime_hours) }))
    return m
  }, [rows])
  const cellOf = (staffId: number, date: string) => edits[`${staffId}|${date}`] ?? saved.get(`${staffId}|${date}`)
  const set = (staffId: number, date: string, c: Cell) => setEdits((e) => ({ ...e, [`${staffId}|${date}`]: c }))
  const pending = Object.keys(edits).length

  const markAllPresent = (date: string) =>
    staff.forEach((s) => {
      if (!cellOf(s.id, date)) set(s.id, date, { status: 'present', overtime_hours: '0' })
    })

  async function save() {
    setSaving(true)
    try {
      const entries = Object.entries(edits).map(([k, c]) => {
        const [staff_id, date] = k.split('|')
        return { staff_id: Number(staff_id), date, status: c.status, overtime_hours: c.overtime_hours }
      })
      await api.put('/labour/attendance', { entries })
      message.success(`Saved ${entries.length} attendance mark(s)`)
      setEdits({})
      await qc.invalidateQueries()
    } catch (e) {
      message.error(apiError(e).message, 6)
    } finally {
      setSaving(false)
    }
  }

  const columns: ColumnsType<Staff> = [
    { title: 'Worker', fixed: 'left', width: 170, render: (_, s) => <div><b>{s.name}</b><br /><Typography.Text type="secondary" style={{ fontSize: 12 }}>{s.role}, {s.wage_type.replace('_', ' ')}</Typography.Text></div> },
    ...days.map((d) => {
      const iso = d.format(API_DATE)
      return {
        title: (
          <div style={{ textAlign: 'center' }}>
            {d.format('ddd')}<br />{d.format('DD-MM')}
            {canWrite && <><br /><Button type="link" size="small" style={{ padding: 0, height: 'auto' }} onClick={() => markAllPresent(iso)}>all P</Button></>}
          </div>
        ),
        key: iso,
        align: 'center' as const,
        width: 78,
        render: (_: unknown, s: Staff) => <CellEditor cell={cellOf(s.id, iso)} disabled={!canWrite} onChange={(c) => set(s.id, iso, c)} />,
      }
    }),
    { title: 'Days', key: 'total', align: 'right', width: 70, render: (_, s) => days.reduce((sum, d) => { const c = cellOf(s.id, d.format(API_DATE)); return sum + (c ? WEIGHT[c.status] : 0) }, 0) },
  ]

  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Tap a cell to cycle Present → Half → Absent. Right-click (or long-press) to add overtime. Daily-wage workers earn that day's wage as soon as you save." />
      <Space wrap style={{ marginBottom: 12 }}>
        <Button icon={<LeftOutlined />} onClick={() => setWeekStart((w) => w.subtract(7, 'day'))} aria-label="Previous week" />
        <b>{days[0].format('DD-MM-YYYY')} to {days[6].format('DD-MM-YYYY')}</b>
        <Button icon={<RightOutlined />} onClick={() => setWeekStart((w) => w.add(7, 'day'))} aria-label="Next week" />
        <Button onClick={() => setWeekStart(dayjs().startOf('week').add(1, 'day'))}>This week</Button>
        {canWrite && <Button type="primary" disabled={!pending} loading={saving} onClick={save}>Save attendance{pending ? ` (${pending})` : ''}</Button>}
        {pending > 0 && <Button onClick={() => setEdits({})}>Discard changes</Button>}
      </Space>
      <Table<Staff> size="small" rowKey="id" loading={isLoading} columns={columns} dataSource={staff} pagination={false} scroll={{ x: 'max-content' }} />
    </>
  )
}
