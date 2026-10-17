import { FilePdfOutlined, LoadingOutlined } from '@ant-design/icons'
import { App, Button } from 'antd'
import { useState } from 'react'
import { apiError } from '@/api/client'
import { openFile } from '@/lib/download'

export function PrintButton({ url, label = 'Print', size = 'small' }: { url: string; label?: string; size?: 'small' | 'middle' }) {
  const { message } = App.useApp()
  const [busy, setBusy] = useState(false)
  return (
    <Button
      size={size}
      icon={busy ? <LoadingOutlined /> : <FilePdfOutlined />}
      onClick={async () => {
        setBusy(true)
        try {
          await openFile(url)
        } catch (e) {
          message.error(apiError(e).message)
        } finally {
          setBusy(false)
        }
      }}
    >
      {label}
    </Button>
  )
}
