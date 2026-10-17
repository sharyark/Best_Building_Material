import { CheckCircleOutlined, LockOutlined, UnlockOutlined, WarningOutlined } from '@ant-design/icons'
import { Alert, App, Button, DatePicker, Space, Table } from "antd"
import dayjs, { type Dayjs } from 'dayjs'
import { useState } from 'react'
import { api, apiError } from '@/api/client'
import { useGet, useSave } from '@/api/hooks'
import type { PeriodLock, TrialBalance } from '@/api/types'
import { PageHeader } from '@/components/PageHeader'
import { Money } from '@/components/Money'
import { API_DATE } from '@/lib/date'
import { useQueryClient } from '@tanstack/react-query'

export default function LocksPage() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const locks = useGet<PeriodLock[]>('/accounting/locks')
  const tb = useGet<TrialBalance>('/accounting/trial-balance')
  const [month, setMonth] = useState<Dayjs | null>(dayjs().subtract(1, 'month'))
  const save = useSave<{ month: string }>('post', '/accounting/locks', { successMessage: 'Month locked' })

  function lock() {
    if (!month) return
    modal.confirm({
      title: `Lock ${month.format('MMMM YYYY')}?`,
      content: 'Nobody (including you) can add, edit or void entries dated in this month until it is unlocked. Do this after the month is reconciled.',
      okText: 'Lock month',
      onOk: () => save.mutateAsync({ month: month.startOf('month').format(API_DATE) }),
    })
  }

  function unlock(m: string) {
    modal.confirm({
      title: `Unlock ${dayjs(m).format('MMMM YYYY')}?`,
      content: 'Unlocking is audited. Only do this to correct a real mistake, then lock the month again.',
      okText: 'Unlock',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await api.delete(`/accounting/locks/${m}`)
          message.success('Month unlocked')
          await qc.invalidateQueries()
        } catch (e) {
          message.error(apiError(e).message)
        }
      },
    })
  }

  return (
    <>
      <PageHeader title="Month lock" subtitle="Lock a closed month so closed books can't change" />
      {tb.data && (
        <Alert
          style={{ marginBottom: 16 }}
          showIcon
          type={tb.data.balanced ? 'success' : 'error'}
          icon={tb.data.balanced ? <CheckCircleOutlined /> : <WarningOutlined />}
          message={tb.data.balanced ? 'Books are balanced' : 'BOOKS ARE OUT OF BALANCE: contact support before continuing'}
          description={<>Total debit <Money value={tb.data.total_debit} /> = total credit <Money value={tb.data.total_credit} /></>}
        />
      )}
      <Space style={{ marginBottom: 16 }} wrap>
        <DatePicker picker="month" value={month} onChange={setMonth} allowClear={false} format="MMMM YYYY" />
        <Button type="primary" icon={<LockOutlined />} loading={save.isPending} onClick={lock}>Lock month</Button>
      </Space>
      <Table<PeriodLock> size="small" rowKey="month" loading={locks.isLoading} dataSource={locks.data ?? []} pagination={false}
        locale={{ emptyText: 'No months are locked yet' }}
        columns={[
          { title: 'Month', dataIndex: 'month', render: (m: string) => dayjs(m).format('MMMM YYYY') },
          { title: 'Locked at', dataIndex: 'locked_at', render: (v: string) => dayjs(v).format('DD-MM-YYYY HH:mm') },
          { title: '', render: (_, l) => <Button size="small" danger icon={<UnlockOutlined />} onClick={() => unlock(l.month)}>Unlock</Button> },
        ]} />
    </>
  )
}
