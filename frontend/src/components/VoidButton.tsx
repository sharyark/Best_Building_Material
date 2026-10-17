import { StopOutlined } from '@ant-design/icons'
import { zodResolver } from '@hookform/resolvers/zod'
import { Button, Form, Input, Modal } from 'antd'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSave } from '@/api/hooks'
import { usePermission } from '@/hooks/usePermission'
import { voidSchema } from '@/lib/schemas'
import { Field } from './Field'

interface Props {
  /** e.g. `/deliveries/12`; `/void` is appended. */
  path: string
  perm: string
  label: string
  disabled?: boolean
  disabledReason?: string
}

/** Admin-only void with a mandatory reason. Hidden (not just disabled) when the role lacks permission. */
export function VoidButton({ path, perm, label, disabled, disabledReason }: Props) {
  const allowed = usePermission(perm)
  const [open, setOpen] = useState(false)
  const { control, handleSubmit, reset } = useForm<{ reason: string }>({
    resolver: zodResolver(voidSchema),
    defaultValues: { reason: '' },
  })
  const save = useSave<{ reason: string }>('post', `${path}/void`, {
    successMessage: `${label} voided`,
    onSuccess: () => {
      setOpen(false)
      reset()
    },
  })
  if (!allowed) return null
  return (
    <>
      <Button size="small" danger icon={<StopOutlined />} disabled={disabled} title={disabledReason} onClick={() => setOpen(true)}>
        Void
      </Button>
      <Modal
        title={`Void ${label}?`}
        open={open}
        onCancel={() => setOpen(false)}
        okText="Void it"
        okButtonProps={{ danger: true, loading: save.isPending }}
        onOk={handleSubmit((v) => save.mutate(v))}
        destroyOnClose
      >
        <p>This posts a reversal to the books. The original stays visible for audit and cannot be undone.</p>
        <Form layout="vertical">
          <Field control={control} name="reason" label="Reason" required>
            {(f) => <Input.TextArea {...f} rows={3} autoFocus maxLength={500} />}
          </Field>
        </Form>
      </Modal>
    </>
  )
}
