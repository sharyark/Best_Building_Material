import { Button, Form, Space } from 'antd'
import type { ReactNode } from 'react'

export function DocFormShell({ onSubmit, saving, children, extra }: { onSubmit: () => void; saving: boolean; children: ReactNode; extra?: ReactNode }) {
  return (
    <Form layout="vertical" onFinish={onSubmit} autoComplete="off">
      {children}
      <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
        <div>{extra}</div>
        <Button type="primary" htmlType="submit" loading={saving} size="large">Save</Button>
      </Space>
    </Form>
  )
}
