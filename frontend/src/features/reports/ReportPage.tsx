import { FileExcelOutlined, FilePdfOutlined, WhatsAppOutlined } from '@ant-design/icons'
import { Alert, App, Button, Checkbox, Select, Space } from 'antd'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiError, api } from '@/api/client'
import { useGet } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { ReportData } from '@/api/types'
import { DateField, DateRangeField } from '@/components/DateField'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { PageHeader } from '@/components/PageHeader'
import { ReportView } from '@/components/ReportView'
import { API_DATE, rangeFromUrl, today } from '@/lib/date'
import { openFile } from '@/lib/download'
import type { ReportConfig, ReportValues } from './reportConfigs'
import { StaffKhataSummary } from './StaffKhataSummary'

function params(cfg: ReportConfig, v: ReportValues): Record<string, string | number> {
  const p: Record<string, string | number> = {}
  if (cfg.filters.includes('range')) {
    p.from = v.range[0]
    p.to = v.range[1]
  }
  if (cfg.filters.includes('date')) p.date = v.date
  if (cfg.filters.includes('asOf')) p.as_of = v.date
  if (cfg.filters.includes('moneyAccount') && v.account) p.money_account_id = v.account
  if (cfg.filters.includes('groupBy')) p.group_by = v.group
  if (cfg.filters.includes('outstandingKind')) p.kind = v.kind
  if (cfg.filters.includes('direction')) p.direction = v.direction
  if (cfg.filters.includes('history') && v.history) p.history = 'true'
  return p
}

export default function ReportPage({ config, embedded = false }: { config: ReportConfig; embedded?: boolean }) {
  const lookups = useLookups()
  const { message } = App.useApp()
  const [search] = useSearchParams()
  const [values, setValues] = useState<ReportValues>(() => ({
    // a link may carry the day or range to show (e.g. from the dashboard)
    range: rangeFromUrl(search) ?? [dayjs().subtract((config.defaultDays ?? 30) - 1, 'day').format(API_DATE), today()],
    date: rangeFromUrl(search)?.[0] ?? today(),
    party: Number(search.get('party')) || null,
    staff: Number(search.get('staff')) || null,
    account: null,
    group: config.groupOptions?.[0]?.value ?? 'month',
    kind: 'receivable',
    direction: search.get('direction') === 'out' ? 'out' : 'in',
    history: false,
  }))
  const set = (patch: Partial<ReportValues>) => setValues((v) => ({ ...v, ...patch }))
  const ready = (config.needs ?? []).every((n) => values[n])
  const query = useMemo(() => params(config, values), [config, values])
  const url = ready ? config.endpoint(values) : ''
  const { data, isLoading, error } = useGet<ReportData>(url, query, { enabled: ready })

  const download = (format: 'xlsx' | 'pdf') => openFile(url, { ...query, format }).catch((e) => message.error(apiError(e).message))
  const share = async () => {
    try {
      const { data: s } = await api.get<{ url: string; has_phone: boolean }>(`${url}/share`, { params: query })
      if (!s.has_phone) message.warning('This party has no phone number. Pick the contact in WhatsApp manually.')
      window.open(s.url, '_blank', 'noopener')
    } catch (e) {
      message.error(apiError(e).message)
    }
  }

  const partyOptions = optionsOf(lookups.parties.filter((p) => p.is_active), (p) => `${p.name} (${p.type})`)

  return (
    <>
      {!embedded && <PageHeader title={config.title} subtitle={config.description} />}
      <Space wrap align="start" style={{ marginBottom: 12 }}>
        {config.filters.includes('customerOrSupplier') && (
          <div style={{ width: 280 }}><EntitySelect options={partyOptions} value={values.party} onChange={(v) => set({ party: v })} placeholder="Choose customer / supplier" allowClear={false} /></div>
        )}
        {config.filters.includes('staff') && (
          <div style={{ width: 260 }}><EntitySelect options={optionsOf(lookups.allStaff)} value={values.staff} onChange={(v) => set({ staff: v })} placeholder="Choose worker" allowClear={false} /></div>
        )}
        {config.filters.includes('moneyAccount') && (
          <div style={{ width: 220 }}><EntitySelect options={optionsOf(lookups.moneyAccounts)} value={values.account} onChange={(v) => set({ account: v })} placeholder="All cash & bank" /></div>
        )}
        {config.filters.includes('range') && <DateRangeField value={values.range} onChange={(range) => set({ range })} />}
        {(config.filters.includes('date') || config.filters.includes('asOf')) && <div style={{ width: 160 }}><DateField value={values.date} onChange={(date) => set({ date })} /></div>}
        {config.filters.includes('groupBy') && <Select style={{ width: 170 }} value={values.group} onChange={(group) => set({ group })} options={config.groupOptions} />}
        {config.filters.includes('history') && (
          <Checkbox checked={values.history} onChange={(e) => set({ history: e.target.checked })}>Edit / void ki purani lines bhi dikhao</Checkbox>
        )}
        {config.filters.includes('direction') && (
          <Select style={{ width: 190 }} value={values.direction} onChange={(direction) => set({ direction })} options={[{ value: 'in', label: 'Money received' }, { value: 'out', label: 'Money paid out' }]} />
        )}
        {config.filters.includes('outstandingKind') && (
          <Select style={{ width: 240 }} value={values.kind} onChange={(kind) => set({ kind })} options={[{ value: 'receivable', label: 'Receivable (customers owe us)' }, { value: 'payable', label: 'Payable (we owe suppliers)' }]} />
        )}
        <Button icon={<FileExcelOutlined />} disabled={!ready} onClick={() => download('xlsx')}>Excel</Button>
        <Button icon={<FilePdfOutlined />} disabled={!ready} onClick={() => download('pdf')}>PDF</Button>
        {config.key === 'khata' && <Button icon={<WhatsAppOutlined />} disabled={!ready} onClick={share} style={{ color: '#25d366', borderColor: '#25d366' }}>WhatsApp</Button>}
      </Space>
      {!ready && <Alert type="info" showIcon message={`Choose a ${config.needs?.[0] === 'staff' ? 'worker' : 'party'} to see this report.`} />}
      {error && <Alert type="error" showIcon message={apiError(error).message} />}
      {ready && !error && data?.meta && 'days_present' in data.meta && <StaffKhataSummary meta={data.meta} />}
      {ready && !error && <ReportView data={data} loading={isLoading} />}
    </>
  )
}
