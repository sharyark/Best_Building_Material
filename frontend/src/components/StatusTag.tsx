import { Tag, Tooltip } from 'antd'

export function StatusTag({ status, reason }: { status: 'active' | 'void'; reason?: string | null }) {
  if (status === 'active') return <Tag color="green">Active</Tag>
  return (
    <Tooltip title={reason ? `Voided: ${reason}` : 'Voided'}>
      <Tag color="red">Void</Tag>
    </Tooltip>
  )
}
