import { KeyOutlined, PlusOutlined } from '@ant-design/icons'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Form, Input, Modal, Select, Switch, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { useGet, useSave } from '@/api/hooks'
import type { Role, User } from '@/api/types'
import { useAuth } from '@/app/AuthContext'
import { Field } from '@/components/Field'
import { PageHeader } from '@/components/PageHeader'

const createSchema = z.object({
  name: z.string().trim().min(1, 'Required'),
  phone: z.string().trim().min(3, 'Min 3 characters'),
  email: z.string().email('Not a valid email').optional().or(z.literal('')),
  role: z.enum(['admin', 'accountant', 'driver', 'customer']),
  password: z.string().min(8, 'At least 8 characters'),
})
const resetSchema = z.object({ new_password: z.string().min(8, 'At least 8 characters') })

const ROLE_COLOR: Record<Role, string> = { admin: 'red', accountant: 'blue', driver: 'default', customer: 'default' }

export default function UsersPage() {
  const { user: me } = useAuth()
  const { data = [], isLoading } = useGet<User[]>('/users')
  const [adding, setAdding] = useState(false)
  const [resetFor, setResetFor] = useState<User | null>(null)

  const create = useForm<z.infer<typeof createSchema>>({ resolver: zodResolver(createSchema), defaultValues: { role: 'accountant', name: '', phone: '', email: '', password: '' } })
  const reset = useForm<z.infer<typeof resetSchema>>({ resolver: zodResolver(resetSchema), defaultValues: { new_password: '' } })
  const createUser = useSave<object>('post', '/users', { successMessage: 'User created', onSuccess: () => { setAdding(false); create.reset() } })
  const toggle = useSave<{ id: number; is_active: boolean }>('patch', (v) => `/users/${v.id}`, { successMessage: 'User updated' })
  const resetPw = useSave<{ new_password: string }>('post', () => `/users/${resetFor?.id}/reset-password`, { successMessage: 'Password changed. The user is signed out everywhere.', onSuccess: () => { setResetFor(null); reset.reset() } })

  const columns: ColumnsType<User> = [
    { title: 'Name', dataIndex: 'name' },
    { title: 'Phone / username', dataIndex: 'phone' },
    { title: 'Role', dataIndex: 'role', render: (r: Role) => <Tag color={ROLE_COLOR[r]}>{r}</Tag> },
    { title: 'Active', dataIndex: 'is_active', render: (a: boolean, u) => <Switch checked={a} disabled={u.id === me?.id} onChange={(checked) => toggle.mutate({ id: u.id, is_active: checked })} /> },
    { title: '', render: (_, u) => <Button size="small" icon={<KeyOutlined />} onClick={() => setResetFor(u)}>Reset password</Button> },
  ]

  return (
    <>
      <PageHeader title="Users" subtitle="Admin and accountant sign in today. Driver and customer roles are ready for phase 3." extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setAdding(true)}>Add user</Button>} />
      <Table<User> size="small" rowKey="id" loading={isLoading} columns={columns} dataSource={data} pagination={false} scroll={{ x: 'max-content' }} />
      <Modal title="Add user" open={adding} onCancel={() => setAdding(false)} okText="Create" okButtonProps={{ loading: createUser.isPending }} onOk={create.handleSubmit((v) => createUser.mutate({ ...v, email: v.email || null }))} destroyOnClose>
        <Form layout="vertical">
          <Field control={create.control} name="name" label="Name" required>{(f) => <Input {...f} autoFocus />}</Field>
          <Field control={create.control} name="phone" label="Phone / username" required>{(f) => <Input {...f} />}</Field>
          <Field control={create.control} name="email" label="Email">{(f) => <Input {...f} />}</Field>
          <Field control={create.control} name="role" label="Role" required>{(f) => <Select {...f} options={[{ value: 'accountant', label: 'Accountant (daily entries)' }, { value: 'admin', label: 'Admin (owner)' }, { value: 'driver', label: 'Driver (phase 3)' }, { value: 'customer', label: 'Customer (phase 3)' }]} />}</Field>
          <Field control={create.control} name="password" label="Temporary password" required>{(f) => <Input.Password {...f} autoComplete="new-password" />}</Field>
        </Form>
      </Modal>
      <Modal title={`Reset password: ${resetFor?.name ?? ''}`} open={resetFor !== null} onCancel={() => setResetFor(null)} okText="Change password" okButtonProps={{ loading: resetPw.isPending }} onOk={reset.handleSubmit((v) => resetPw.mutate(v))} destroyOnClose>
        <Alert type="warning" showIcon message="This signs the user out of every device." style={{ marginBottom: 12 }} />
        <Form layout="vertical"><Field control={reset.control} name="new_password" label="New password" required>{(f) => <Input.Password {...f} autoComplete="new-password" autoFocus />}</Field></Form>
      </Modal>
    </>
  )
}
