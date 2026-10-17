import { Form } from 'antd'
import { useId, type ReactNode } from 'react'
import { Controller, type Control, type FieldValues, type Path } from 'react-hook-form'

interface Props<T extends FieldValues> {
  control: Control<T>
  name: Path<T>
  label?: ReactNode
  extra?: ReactNode
  required?: boolean
  children: (field: FieldRenderProps) => ReactNode
}

/** The controller's render props with a loosely typed value, so one input component fits any field. */
export interface FieldRenderProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  value: any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onChange: (...event: any[]) => void
  onBlur: () => void
  name: string
  /** Put this on the input so the <label> is associated with it (screen readers, getByLabel). */
  id: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ref: (instance: any) => void
}

/** React Hook Form Controller + antd Form.Item showing the Zod error under the field. */
export function Field<T extends FieldValues>({ control, name, label, extra, required, children }: Props<T>) {
  const id = useId()
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <Form.Item
          label={label}
          htmlFor={id}
          required={required}
          extra={extra}
          validateStatus={fieldState.error ? 'error' : undefined}
          help={fieldState.error?.message}
          style={{ marginBottom: 12 }}
        >
          {children({ ...field, id })}
        </Form.Item>
      )}
    />
  )
}
