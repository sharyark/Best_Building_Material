import { CheckOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { App, Button } from 'antd'
import { useState } from 'react'
import { api, apiError } from '@/api/client'
import type { Delivery } from '@/api/types'

/** One-way: asks first, because a delivered challan goes to the khata and the munshi cannot undo it. */
export function DeliverButton({ delivery }: { delivery: Delivery }) {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)

  async function deliver(allowNegative: boolean) {
    setBusy(true)
    try {
      await api.post(`/deliveries/${delivery.id}/deliver`, { allow_negative_stock: allowNegative })
      message.success(`Challan ${delivery.challan_no} delivered and added to the khata`)
      void qc.invalidateQueries()
    } catch (err) {
      const e = apiError(err)
      if (e.code === 'INSUFFICIENT_STOCK' && !allowNegative) {
        modal.confirm({
          title: 'Not enough stock in the yard',
          content: `${e.message}. Mark it delivered anyway? Stock will go negative until the next purchase is entered.`,
          okText: 'Deliver anyway',
          onOk: () => deliver(true),
        })
      } else {
        message.error(e.message, 6)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Button
      size="small"
      type="primary"
      ghost
      icon={<CheckOutlined />}
      loading={busy}
      onClick={() =>
        modal.confirm({
          title: `Mark challan ${delivery.challan_no} delivered?`,
          content: 'It will be added to the customer\'s khata and the driver\'s trip pay. This cannot be changed back.',
          okText: 'Yes, delivered',
          onOk: () => deliver(false),
        })
      }
    >
      Mark delivered
    </Button>
  )
}
