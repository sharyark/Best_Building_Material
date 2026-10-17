import { EditOutlined, PlusOutlined } from '@ant-design/icons'
import { zodResolver } from '@hookform/resolvers/zod'
import { Button, Form, Input, Modal, Select, Switch, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { usePage, useSave } from '@/api/hooks'
import { Field } from '@/components/Field'
import { MoneyInput, QtyInput } from '@/components/DecimalInput'
import { EntitySelect, type Option } from '@/components/EntitySelect'
import { useDebounce } from '@/hooks/useDebounce'
import { usePermission } from '@/hooks/usePermission'
import { moneyField, optionalMoney, qtyField } from '@/lib/schemas'

export interface FieldSpec {
  name: string
  label: string
  kind: 'text' | 'textarea' | 'money' | 'qty' | 'select' | 'entity' | 'switch'
  required?: boolean
  options?: Option[]
  /** Only editable when creating (e.g. a site's customer). */
  createOnly?: boolean
  hint?: string
}

function buildSchema(fields: FieldSpec[]) {
  const shape: Record<string, z.ZodTypeAny> = {}
  for (const f of fields) {
    switch (f.kind) {
      case 'text':
      case 'textarea':
        shape[f.name] = f.required ? z.string().trim().min(1, 'Required') : z.string().optional().or(z.literal(''))
        break
      case 'money':
        shape[f.name] = f.required ? moneyField : optionalMoney
        break
      case 'qty':
        shape[f.name] = f.required ? qtyField : z.string().optional().or(z.literal(''))
        break
      case 'select':
        shape[f.name] = f.required ? z.string().min(1, 'Required') : z.string().optional()
        break
      case 'entity':
        shape[f.name] = f.required
          ? z.number({ required_error: 'Required', invalid_type_error: 'Required' })
          : z.number().nullable().optional()
        break
      case 'switch':
        shape[f.name] = z.boolean().optional()
    }
  }
  return z.object(shape)
}

type Row = { id: number } & Record<string, unknown>

interface Props<T extends Row> {
  endpoint: string
  columns: ColumnsType<T>
  fields: FieldSpec[]
  entityName: string
  params?: Record<string, string | number | boolean | undefined>
  defaults?: Record<string, unknown>
  searchable?: boolean
  writePerm?: string
  /** Extra buttons per row (e.g. link to khata). */
  rowActions?: (row: T) => React.ReactNode
  /** Rows can be deactivated through `is_active`. */
  deactivatable?: boolean
}

function toPayload(values: Record<string, unknown>, fields: FieldSpec[]): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of fields) {
    const v = values[f.name]
    out[f.name] = v === '' || v === undefined ? null : v
  }
  return out
}

export function CrudTable<T extends Row>({
  endpoint, columns, fields, entityName, params, defaults, searchable = true, writePerm = 'masters.write',
  rowActions, deactivatable = true,
}: Props<T>) {
  const canWrite = usePermission(writePerm)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const search = useDebounce(q)
  const { data, isLoading } = usePage<T>(endpoint, { ...params, q: search, page, size: 50 })
  const [editing, setEditing] = useState<T | 'new' | null>(null)
  const schema = useMemo(() => buildSchema(fields), [fields])
  const { control, handleSubmit, reset } = useForm<Record<string, unknown>>({ resolver: zodResolver(schema) })
  const isNew = editing === 'new'

  const save = useSave<Record<string, unknown>, unknown>(
    isNew ? 'post' : 'patch',
    isNew ? endpoint : `${endpoint}/${(editing as T | null)?.id}`,
    { successMessage: `${entityName} saved`, onSuccess: () => setEditing(null) },
  )
  const toggle = useSave<{ id: number; is_active: boolean }>('patch', (v) => `${endpoint}/${v.id}`, {
    successMessage: `${entityName} updated`,
  })

  const open = (row: T | 'new') => {
    const base: Record<string, unknown> = {}
    for (const f of fields) base[f.name] = f.kind === 'switch' ? false : f.kind === 'entity' ? undefined : ''
    reset(row === 'new' ? { ...base, ...defaults } : { ...base, ...Object.fromEntries(fields.map((f) => [f.name, (row as T)[f.name] ?? base[f.name]])) })
    setEditing(row)
  }

  const cols: ColumnsType<T> = [
    ...columns,
    {
      title: '',
      key: 'actions',
      align: 'right',
      render: (_, row) => (
        <>
          {rowActions?.(row)}
          {canWrite && (
            <Button size="small" type="text" icon={<EditOutlined />} aria-label={`Edit ${entityName}`} onClick={() => open(row)} />
          )}
          {canWrite && deactivatable && 'is_active' in row && (
            <Switch
              size="small"
              checked={Boolean(row.is_active)}
              title={row.is_active ? 'Active: click to deactivate' : 'Inactive: click to activate'}
              onChange={(checked) => toggle.mutate({ id: row.id, is_active: checked })}
            />
          )}
        </>
      ),
    },
  ]

  return (
    <>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {searchable && <Input.Search allowClear placeholder={`Search ${entityName.toLowerCase()}…`} onChange={(e) => { setQ(e.target.value); setPage(1) }} style={{ maxWidth: 320 }} />}
        {canWrite && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => open('new')}>
            Add {entityName.toLowerCase()}
          </Button>
        )}
      </div>
      <Table<T>
        size="small"
        rowKey="id"
        loading={isLoading}
        columns={cols}
        dataSource={data?.items ?? []}
        scroll={{ x: 'max-content' }}
        pagination={{ current: page, pageSize: 50, total: data?.total ?? 0, onChange: setPage, showSizeChanger: false, hideOnSinglePage: true }}
      />
      <Modal
        open={editing !== null}
        title={`${isNew ? 'Add' : 'Edit'} ${entityName.toLowerCase()}`}
        onCancel={() => setEditing(null)}
        okText="Save"
        okButtonProps={{ loading: save.isPending }}
        onOk={handleSubmit((v) => save.mutate(toPayload(v, isNew ? fields : fields.filter((f) => !f.createOnly))))}
        destroyOnClose
      >
        <Form layout="vertical">
          {fields
            .filter((f) => isNew || !f.createOnly)
            .map((f) => (
              <Field key={f.name} control={control} name={f.name} label={f.label} required={f.required} extra={f.hint}>
                {(field) =>
                  f.kind === 'textarea' ? (
                    <Input.TextArea {...field} value={field.value as string} rows={2} />
                  ) : f.kind === 'money' ? (
                    <MoneyInput {...field} value={field.value as string} />
                  ) : f.kind === 'qty' ? (
                    <QtyInput {...field} value={field.value as string} />
                  ) : f.kind === 'select' ? (
                    <Select {...field} value={(field.value as string) || undefined} options={f.options} style={{ width: '100%' }} />
                  ) : f.kind === 'entity' ? (
                    <EntitySelect id={field.id} options={f.options ?? []} value={field.value as number} onChange={field.onChange} />
                  ) : f.kind === 'switch' ? (
                    <Switch checked={Boolean(field.value)} onChange={field.onChange} />
                  ) : (
                    <Input {...field} value={field.value as string} />
                  )
                }
              </Field>
            ))}
        </Form>
      </Modal>
    </>
  )
}
