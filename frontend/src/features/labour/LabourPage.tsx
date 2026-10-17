import { Tabs } from 'antd'
import { PageHeader } from '@/components/PageHeader'
import AttendanceGrid from './AttendanceGrid'
import Settlements from './Settlements'

export default function LabourPage() {
  return (
    <>
      <PageHeader title="Labour & wages" subtitle="Attendance, daily wages, advances and settlement for drivers, operators and labour" />
      <Tabs
        destroyInactiveTabPane
        items={[
          { key: 'attendance', label: 'Attendance', children: <AttendanceGrid /> },
          { key: 'settle', label: 'Wage settlement', children: <Settlements /> },
        ]}
      />
    </>
  )
}
