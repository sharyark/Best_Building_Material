import { FileExcelOutlined, FilePdfOutlined, WhatsAppOutlined } from '@ant-design/icons'
import { Alert, App, Button, Select, Space } from 'antd'
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
import { API_DATE, today } from '@/lib/date'
import { openFile } from '@/lib/download'
import type { ReportConfig, ReportValues } from './reportConfigs'

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
  return p
}

export default function ReportPage({ config, embedded = false }: { config: ReportConfig; embedded?: boolean }) {
  const lookups = useLookups()
  const { message } = App.useApp()
  const [search] = useSearchParams()
  const [values, setValues] = useState<ReportValues>(() => ({
    range: [dayjs().subtract((config.defaultDays ?? 30) - 1, 'day').format(API_DATE), today()],
    date: today(),
    party: Number(search.get('party')) || null,
    staff: Number(search.get('staff')) || null,
    account: null,
    group: config.groupOptions?.[0]?.value ?? 'month',
    kind: 'receivable',
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
        {config.filters.includes('outstandingKind') && (
          <Select style={{ width: 240 }} value={values.kind} onChange={(kind) => set({ kind })} options={[{ value: 'receivable', label: 'Receivable (customers owe us)' }, { value: 'payable', label: 'Payable (we owe suppliers)' }]} />
        )}
        <Button icon={<FileExcelOutlined />} disabled={!ready} onClick={() => download('xlsx')}>Excel</Button>
        <Button icon={<FilePdfOutlined />} disabled={!ready} onClick={() => download('pdf')}>PDF</Button>
        {config.key === 'khata' && <Button icon={<WhatsAppOutlined />} disabled={!ready} onClick={share} style={{ color: '#25d366', borderColor: '#25d366' }}>WhatsApp</Button>}
      </Space>
      {!ready && <Alert type="info" showIcon message={`Choose a ${config.needs?.[0] === 'staff' ? 'worker' : 'party'} to see this report.`} />}
      {error && <Alert type="error" showIcon message={apiError(error).message} />}
      {ready && !error && <ReportView data={data} loading={isLoading} />}
      {ready && data?.meta && 'days_present' in data.meta && (
        <Space size="large" wrap style={{ marginTop: 12 }}>
          <span>Present: <b>{String(data.meta.days_present)}</b> day(s), half: <b>{String(data.meta.half_days)}</b>, absent: <b>{String(data.meta.days_absent)}</b></span>
          <span>Wages earned: <b>{String(data.meta.wages_earned)}</b></span>
          <span>Advances paid: <b>{String(data.meta.advances_paid)}</b></span>
          <span>Balance payable: <b>{String(data.meta.balance_payable)}</b></span>
        </Space>
      )}
    </>
  )
}
