import { zodResolver } from '@hookform/resolvers/zod'
import { Form, Input, Modal } from 'antd'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { useSave } from '@/api/hooks'
import type { Party, Site } from '@/api/types'
import { Field } from './Field'

const partySchema = z.object({
  name: z.string().trim().min(1, 'Enter a name').max(150),
  phone: z.string().max(30).optional().or(z.literal('')),
  address: z.string().optional().or(z.literal('')),
})
type PartyForm = z.infer<typeof partySchema>

/** Add a customer or supplier without leaving the entry screen. Its ledger (khata) starts at zero. */
export function QuickAddParty({
  open, type, initialName, onClose, onCreated,
}: { open: boolean; type: 'customer' | 'supplier'; initialName: string; onClose: () => void; onCreated: (p: Party) => void }) {
  const { control, handleSubmit, reset } = useForm<PartyForm>({ resolver: zodResolver(partySchema), defaultValues: { name: '', phone: '', address: '' } })
  useEffect(() => {
    if (open) reset({ name: initialName, phone: '', address: '' })
  }, [open, initialName, reset])
  const label = type === 'customer' ? 'customer' : 'supplier'
  const save = useSave<object, Party>('post', '/masters/parties', {
    successMessage: `New ${label} added`,
    onSuccess: (p) => {
      onCreated(p)
      onClose()
    },
  })
  return (
    <Modal
      open={open}
      title={`New ${label}`}
      okText={`Add ${label}`}
      onCancel={onClose}
      okButtonProps={{ loading: save.isPending }}
      onOk={handleSubmit((v) => save.mutate({ type, name: v.name, phone: v.phone || null, address: v.address || null }))}
      destroyOnClose
    >
      <Form layout="vertical" onFinish={handleSubmit((v) => save.mutate({ type, name: v.name, phone: v.phone || null, address: v.address || null }))}>
        <Field control={control} name="name" label="Name" required>{(f) => <Input {...f} autoFocus />}</Field>
        <Field control={control} name="phone" label="Phone (also used for WhatsApp statements)">{(f) => <Input {...f} />}</Field>
        <Field control={control} name="address" label="Address">{(f) => <Input.TextArea {...f} rows={2} />}</Field>
        <button type="submit" hidden />
      </Form>
    </Modal>
  )
}

/** Add a construction site for a customer from the challan screen. */
export function QuickAddSite({
  open, partyId, initialName, onClose, onCreated,
}: { open: boolean; partyId: number | null; initialName: string; onClose: () => void; onCreated: (s: Site) => void }) {
  const { control, handleSubmit, reset } = useForm<{ name: string; address?: string }>({
    resolver: zodResolver(z.object({ name: z.string().trim().min(1, 'Enter a site name'), address: z.string().optional() })),
    defaultValues: { name: '', address: '' },
  })
  useEffect(() => {
    if (open) reset({ name: initialName, address: '' })
  }, [open, initialName, reset])
  const save = useSave<object, Site>('post', '/masters/sites', {
    successMessage: 'New site added',
    onSuccess: (s) => {
      onCreated(s)
      onClose()
    },
  })
  const submit = handleSubmit((v) => save.mutate({ party_id: partyId, name: v.name, address: v.address || null }))
  return (
    <Modal open={open} title="New site" okText="Add site" onCancel={onClose} okButtonProps={{ loading: save.isPending }} onOk={submit} destroyOnClose>
      <Form layout="vertical" onFinish={submit}>
        <Field control={control} name="name" label="Site name" required>{(f) => <Input {...f} autoFocus />}</Field>
        <Field control={control} name="address" label="Address">{(f) => <Input.TextArea {...f} rows={2} />}</Field>
        <button type="submit" hidden />
      </Form>
    </Modal>
  )
}
