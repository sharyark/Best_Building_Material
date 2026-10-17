import { Alert, Button, Form, Space, Table, Tabs, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useGet, useSave } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { Material, MoneyAccount, Party, RateCard, Site, Staff, Vehicle } from '@/api/types'
import { MoneyInput } from '@/components/DecimalInput'
import { DateField } from '@/components/DateField'
import { EntitySelect, optionsOf } from '@/components/EntitySelect'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { usePermission } from '@/hooks/usePermission'
import { formatDate, today } from '@/lib/date'
import { CrudTable, type FieldSpec } from './CrudTable'

const partyType = (t: Party['type']) => <Tag color={t === 'customer' ? 'blue' : t === 'supplier' ? 'orange' : 'purple'}>{t}</Tag>
const khata = (row: { id: number }) => (
  <Link to={`/reports/khata?party=${row.id}`}>
    <Button size="small" type="link">Khata</Button>
  </Link>
)

const partyFields = (types: { value: string; label: string }[]): FieldSpec[] => [
  { name: 'type', label: 'Type', kind: 'select', required: true, options: types },
  { name: 'name', label: 'Name', kind: 'text', required: true },
  { name: 'phone', label: 'Phone (also used for WhatsApp)', kind: 'text' },
  { name: 'address', label: 'Address', kind: 'textarea' },
  { name: 'tax_no', label: 'Tax / GST no.', kind: 'text' },
]

function Customers() {
  const columns: ColumnsType<Party> = [
    { title: 'Name', dataIndex: 'name' },
    { title: 'Type', dataIndex: 'type', render: partyType },
    { title: 'Phone', dataIndex: 'phone' },
    { title: 'Balance (Dr = owes us)', dataIndex: 'balance', align: 'right', render: (v) => <Money value={v} drcr /> },
  ]
  return (
    <CrudTable<Party & Record<string, unknown>>
      endpoint="/masters/parties"
      entityName="Customer"
      params={{ type: 'customer', with_balance: true }}
      columns={columns as never}
      fields={partyFields([{ value: 'customer', label: 'Customer' }, { value: 'both', label: 'Customer + supplier' }])}
      defaults={{ type: 'customer' }}
      rowActions={khata}
    />
  )
}

function Suppliers() {
  const columns: ColumnsType<Party> = [
    { title: 'Name', dataIndex: 'name' },
    { title: 'Type', dataIndex: 'type', render: partyType },
    { title: 'Phone', dataIndex: 'phone' },
    { title: 'Balance (Cr = we owe)', dataIndex: 'balance', align: 'right', render: (v) => <Money value={v} drcr /> },
  ]
  return (
    <CrudTable<Party & Record<string, unknown>>
      endpoint="/masters/parties"
      entityName="Supplier"
      params={{ type: 'supplier', with_balance: true }}
      columns={columns as never}
      fields={partyFields([{ value: 'supplier', label: 'Supplier (crusher, bhatta, dealer, pump)' }, { value: 'both', label: 'Customer + supplier' }])}
      defaults={{ type: 'supplier' }}
      rowActions={khata}
    />
  )
}

function Materials() {
  const units = ['trolley', 'cft', 'ton', 'bag', 'piece', 'brass'].map((u) => ({ value: u, label: u }))
  const columns: ColumnsType<Material> = [
    { title: 'Material', dataIndex: 'name' },
    { title: 'Unit', dataIndex: 'unit' },
    { title: 'Default sale rate', dataIndex: 'default_sale_rate', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Default purchase rate', dataIndex: 'default_purchase_rate', align: 'right', render: (v) => <Money value={v} /> },
  ]
  const fields: FieldSpec[] = [
    { name: 'name', label: 'Name', kind: 'text', required: true },
    { name: 'unit', label: 'Unit (same for buying and selling)', kind: 'select', required: true, options: units },
    { name: 'default_sale_rate', label: 'Default sale rate', kind: 'money', required: true },
    { name: 'default_purchase_rate', label: 'Default purchase rate', kind: 'money', required: true },
    { name: 'hsn_code', label: 'HSN code (tax)', kind: 'text' },
  ]
  return <CrudTable<Material & Record<string, unknown>> endpoint="/masters/materials" entityName="Material" columns={columns as never} fields={fields} defaults={{ unit: 'trolley', default_sale_rate: '0', default_purchase_rate: '0' }} />
}

function Vehicles() {
  const types = [{ value: 'tractor_trolley', label: 'Tractor-trolley' }, { value: 'dumper', label: 'Dumper' }, { value: 'loader', label: 'Loader' }]
  const columns: ColumnsType<Vehicle> = [
    { title: 'Name', dataIndex: 'name' },
    { title: 'Type', dataIndex: 'type', render: (v: string) => v.replace('_', ' ') },
    { title: 'Reg. no.', dataIndex: 'reg_no' },
    { title: 'Meter', dataIndex: 'meter_type' },
  ]
  const fields: FieldSpec[] = [
    { name: 'name', label: 'Name (e.g. Tractor-1)', kind: 'text', required: true },
    { name: 'type', label: 'Type', kind: 'select', required: true, options: types },
    { name: 'reg_no', label: 'Registration no.', kind: 'text' },
    { name: 'capacity', label: 'Capacity', kind: 'qty' },
    { name: 'meter_type', label: 'Meter', kind: 'select', required: true, options: [{ value: 'km', label: 'Kilometres' }, { value: 'hours', label: 'Hours' }] },
  ]
  return <CrudTable<Vehicle & Record<string, unknown>> endpoint="/masters/vehicles" entityName="Vehicle" columns={columns as never} fields={fields} defaults={{ type: 'tractor_trolley', meter_type: 'km' }} />
}

function StaffTab() {
  const { allVehicles } = useLookups()
  const columns: ColumnsType<Staff> = [
    { title: 'Name', dataIndex: 'name' },
    { title: 'Role', dataIndex: 'role' },
    { title: 'Pay type', dataIndex: 'wage_type', render: (v: string) => v.replace('_', ' ') },
    { title: 'Wage', dataIndex: 'wage_amount', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Balance (Cr = we owe)', dataIndex: 'balance', align: 'right', render: (v) => <Money value={v} drcr /> },
  ]
  const fields: FieldSpec[] = [
    { name: 'name', label: 'Name', kind: 'text', required: true },
    { name: 'phone', label: 'Phone', kind: 'text' },
    { name: 'role', label: 'Role', kind: 'select', required: true, options: ['driver', 'operator', 'labour', 'helper', 'munshi'].map((v) => ({ value: v, label: v })) },
    { name: 'wage_type', label: 'Paid', kind: 'select', required: true, options: [{ value: 'monthly', label: 'Monthly salary' }, { value: 'daily', label: 'Daily wage' }, { value: 'per_trip', label: 'Per trip' }] },
    { name: 'wage_amount', label: 'Wage amount (per month / day / trip)', kind: 'money', required: true },
    { name: 'default_vehicle_id', label: 'Default vehicle (cost centre)', kind: 'entity', options: optionsOf(allVehicles) },
  ]
  return <CrudTable<Staff & Record<string, unknown>> endpoint="/masters/staff" entityName="Staff" params={{ with_balance: true }} columns={columns as never} fields={fields} defaults={{ role: 'labour', wage_type: 'daily', wage_amount: '0' }} rowActions={(r) => <Link to={`/reports/staff-khata?staff=${r.id}`}><Button size="small" type="link">Khata</Button></Link>} />
}

function MoneyAccounts() {
  const columns: ColumnsType<MoneyAccount> = [
    { title: 'Account', dataIndex: 'name' },
    { title: 'Kind', dataIndex: 'kind' },
    { title: 'Balance', dataIndex: 'balance', align: 'right', render: (v) => <Money value={v} drcr /> },
  ]
  const fields: FieldSpec[] = [
    { name: 'name', label: 'Name (e.g. Bank - HBL, JazzCash)', kind: 'text', required: true },
    { name: 'kind', label: 'Kind', kind: 'select', required: true, options: [{ value: 'cash', label: 'Cash' }, { value: 'bank', label: 'Bank' }, { value: 'wallet', label: 'Wallet / UPI' }], createOnly: true },
  ]
  return <CrudTable<MoneyAccount & Record<string, unknown>> endpoint="/masters/money-accounts" entityName="Cash/bank account" params={{ with_balance: true }} columns={columns as never} fields={fields} defaults={{ kind: 'bank' }} searchable={false} />
}

function SitesTab() {
  const { customers } = useLookups()
  const [customerId, setCustomerId] = useState<number | null>(null)
  const columns: ColumnsType<Site> = [{ title: 'Site', dataIndex: 'name' }, { title: 'Address', dataIndex: 'address' }]
  const fields: FieldSpec[] = [
    { name: 'party_id', label: 'Customer', kind: 'entity', required: true, options: optionsOf(customers), createOnly: true },
    { name: 'name', label: 'Site name', kind: 'text', required: true },
    { name: 'address', label: 'Address', kind: 'textarea' },
  ]
  return (
    <>
      <Form layout="inline" style={{ marginBottom: 12 }}>
        <Form.Item label="Customer" style={{ minWidth: 280 }}>
          <EntitySelect options={optionsOf(customers)} value={customerId} onChange={setCustomerId} placeholder="All customers" />
        </Form.Item>
      </Form>
      <CrudTable<Site & Record<string, unknown>> key={customerId ?? 'all'} endpoint="/masters/sites" entityName="Site" params={{ party_id: customerId ?? undefined }} columns={columns as never} fields={fields} defaults={{ party_id: customerId ?? undefined }} deactivatable={false} />
    </>
  )
}

function RateCards() {
  const { customers, materials, materialById, partyById } = useLookups()
  const canWrite = usePermission('masters.write')
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [materialId, setMaterialId] = useState<number | null>(null)
  const [rate, setRate] = useState('')
  const [from, setFrom] = useState(today())
  const { data = [], isLoading } = useGet<RateCard[]>('/masters/rate-cards', { party_id: customerId })
  const save = useSave<object>('post', '/masters/rate-cards', { successMessage: 'Rate saved', onSuccess: () => setRate('') })
  const columns: ColumnsType<RateCard> = [
    { title: 'Customer', dataIndex: 'party_id', render: (id: number) => partyById.get(id)?.name },
    { title: 'Material', dataIndex: 'material_id', render: (id: number) => materialById.get(id)?.name },
    { title: 'Rate', dataIndex: 'rate', align: 'right', render: (v) => <Money value={v} /> },
    { title: 'Effective from', dataIndex: 'effective_from', render: formatDate },
  ]
  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 12 }} message="A customer-specific rate fills the challan automatically. The latest rate on or before the challan date applies; otherwise the material's default rate is used." />
      <Space wrap style={{ marginBottom: 12 }} align="start">
        <div style={{ width: 240 }}><EntitySelect options={optionsOf(customers)} value={customerId} onChange={setCustomerId} placeholder="Customer" /></div>
        {canWrite && (
          <>
            <div style={{ width: 200 }}><EntitySelect options={optionsOf(materials)} value={materialId} onChange={setMaterialId} placeholder="Material" /></div>
            <div style={{ width: 150 }}><MoneyInput value={rate} onChange={setRate} placeholder="Rate" /></div>
            <div style={{ width: 150 }}><DateField value={from} onChange={setFrom} /></div>
            <Button type="primary" loading={save.isPending} disabled={!customerId || !materialId || !(Number(rate) > 0)} onClick={() => save.mutate({ party_id: customerId, material_id: materialId, rate, effective_from: from })}>
              Save rate
            </Button>
          </>
        )}
      </Space>
      <Table size="small" rowKey="id" loading={isLoading} columns={columns} dataSource={data} pagination={{ pageSize: 50, hideOnSinglePage: true }} scroll={{ x: 'max-content' }} />
    </>
  )
}

export default function MastersPage() {
  const [tab, setTab] = useState('customers')
  return (
    <>
      <PageHeader title="Masters" subtitle="Customers, suppliers, materials, fleet and staff" />
      <Tabs
        activeKey={tab}
        onChange={setTab}
        destroyInactiveTabPane
        items={[
          { key: 'customers', label: 'Customers', children: <Customers /> },
          { key: 'suppliers', label: 'Suppliers', children: <Suppliers /> },
          { key: 'sites', label: 'Sites', children: <SitesTab /> },
          { key: 'materials', label: 'Materials', children: <Materials /> },
          { key: 'rates', label: 'Rate cards', children: <RateCards /> },
          { key: 'vehicles', label: 'Vehicles', children: <Vehicles /> },
          { key: 'staff', label: 'Staff & labour', children: <StaffTab /> },
          { key: 'money', label: 'Cash & bank', children: <MoneyAccounts /> },
        ]}
      />
    </>
  )
}
