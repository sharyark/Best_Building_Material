import {
  AuditOutlined,
  BankOutlined,
  BarChartOutlined,
  CarOutlined,
  CloudOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  LockOutlined,
  LogoutOutlined,
  MenuOutlined,
  ProfileOutlined,
  SettingOutlined,
  ShoppingCartOutlined,
  SwapOutlined,
  TeamOutlined,
  ToolOutlined,
  UserOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import { Button, Drawer, Dropdown, Grid, Layout, Menu, Typography } from 'antd'
import { useMemo, useState, type ReactNode } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { t, type TextKey } from '@/i18n'
import { useAuth } from './AuthContext'

const { Header, Sider, Content } = Layout

interface NavItem {
  key: string
  label: TextKey
  icon: ReactNode
  perm?: string
  children?: NavItem[]
}

export const NAV: NavItem[] = [
  { key: '/', label: 'nav.dashboard', icon: <DashboardOutlined />, perm: 'dashboard.view' },
  {
    key: 'entries',
    label: 'nav.entries',
    icon: <ProfileOutlined />,
    children: [
      { key: '/challans', label: 'nav.challans', icon: <CarOutlined />, perm: 'challan.create' },
      { key: '/purchases', label: 'nav.purchases', icon: <ShoppingCartOutlined />, perm: 'purchase.create' },
      { key: '/rentals', label: 'nav.rentals', icon: <ToolOutlined />, perm: 'rental.create' },
      { key: '/payments', label: 'nav.payments', icon: <WalletOutlined />, perm: 'payment.create' },
      { key: '/expenses', label: 'nav.expenses', icon: <SwapOutlined />, perm: 'expense.create' },
      { key: '/labour', label: 'nav.labour', icon: <TeamOutlined />, perm: 'attendance.write' },
    ],
  },
  { key: '/stock', label: 'nav.stock', icon: <DatabaseOutlined />, perm: 'stock.view' },
  { key: '/invoices', label: 'nav.invoices', icon: <FileTextOutlined />, perm: 'invoice.create' },
  { key: '/reports', label: 'nav.reports', icon: <BarChartOutlined />, perm: 'report.khata' },
  { key: '/masters', label: 'nav.masters', icon: <BankOutlined />, perm: 'masters.read' },
  {
    key: 'admin',
    label: 'nav.admin',
    icon: <SettingOutlined />,
    perm: 'users.manage',
    children: [
      { key: '/admin/users', label: 'nav.users', icon: <UserOutlined />, perm: 'users.manage' },
      { key: '/admin/opening', label: 'nav.opening', icon: <CloudOutlined />, perm: 'opening.write' },
      { key: '/admin/locks', label: 'nav.locks', icon: <LockOutlined />, perm: 'period.lock' },
      { key: '/admin/audit', label: 'nav.audit', icon: <AuditOutlined />, perm: 'audit.view' },
    ],
  },
]

function selectedKey(pathname: string): string {
  const all = NAV.flatMap((n) => n.children ?? [n])
  const match = all
    .filter((n) => (n.key === '/' ? pathname === '/' : pathname === n.key || pathname.startsWith(n.key + '/')))
    .sort((a, b) => b.key.length - a.key.length)[0]
  return match?.key ?? '/'
}

export default function AppLayout() {
  const { user, logout, can } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const screens = Grid.useBreakpoint()
  const mobile = !screens.lg
  const [drawer, setDrawer] = useState(false)

  const items = useMemo(() => {
    const toMenu = (n: NavItem): object | null => {
      if (n.perm && !can(n.perm)) return null
      if (n.children) {
        const kids = n.children.map(toMenu).filter(Boolean)
        return kids.length ? { key: n.key, icon: n.icon, label: t(n.label), children: kids } : null
      }
      return { key: n.key, icon: n.icon, label: t(n.label) }
    }
    return NAV.map(toMenu).filter(Boolean)
  }, [can])

  const menu = (
    <Menu
      mode="inline"
      theme={mobile ? 'light' : 'dark'}
      selectedKeys={[selectedKey(location.pathname)]}
      defaultOpenKeys={['entries', 'admin']}
      items={items as never}
      onClick={({ key }) => {
        navigate(key)
        setDrawer(false)
      }}
    />
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {!mobile && (
        <Sider width={230} theme="dark" style={{ position: 'sticky', top: 0, height: '100vh', overflow: 'auto' }}>
          <div style={{ color: '#fff', fontWeight: 600, fontSize: 17, padding: '18px 20px' }}>{t('app.name')}</div>
          {menu}
        </Sider>
      )}
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #eee',
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          {mobile ? (
            <Button type="text" icon={<MenuOutlined />} aria-label="Open menu" onClick={() => setDrawer(true)} />
          ) : (
            <span />
          )}
          <Dropdown
            menu={{
              items: [
                { key: 'who', label: `${user?.name} (${user?.role})`, disabled: true },
                { key: 'out', icon: <LogoutOutlined />, label: t('action.logout'), onClick: () => void logout() },
              ],
            }}
          >
            <Button type="text" icon={<UserOutlined />}>
              {user?.name}
            </Button>
          </Dropdown>
        </Header>
        <Content style={{ padding: mobile ? 12 : 24, minWidth: 0 }}>
          <Outlet />
        </Content>
      </Layout>
      <Drawer
        placement="left"
        open={drawer}
        onClose={() => setDrawer(false)}
        width={260}
        title={<Typography.Text strong>{t('app.name')}</Typography.Text>}
        styles={{ body: { padding: 0 } }}
      >
        {menu}
      </Drawer>
    </Layout>
  )
}
