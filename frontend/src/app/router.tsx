import { Result, Spin } from 'antd'
import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate, useLocation } from 'react-router-dom'
import { RequirePerm } from '@/components/RequirePerm'
import { useAuth } from './AuthContext'
import AppLayout from './Layout'

const LoginPage = lazy(() => import('@/features/auth/LoginPage'))
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage'))
const ChallanPage = lazy(() => import('@/features/deliveries/ChallanPage'))
const PurchasesPage = lazy(() => import('@/features/purchases/PurchasesPage'))
const RentalsPage = lazy(() => import('@/features/rentals/RentalsPage'))
const PaymentsPage = lazy(() => import('@/features/payments/PaymentsPage'))
const ExpensesPage = lazy(() => import('@/features/expenses/ExpensesPage'))
const LabourPage = lazy(() => import('@/features/labour/LabourPage'))
const StockPage = lazy(() => import('@/features/stock/StockPage'))
const InvoicesPage = lazy(() => import('@/features/invoices/InvoicesPage'))
const MastersPage = lazy(() => import('@/features/masters/MastersPage'))
const UsersPage = lazy(() => import('@/features/admin/UsersPage'))
const OpeningPage = lazy(() => import('@/features/admin/OpeningPage'))
const LocksPage = lazy(() => import('@/features/admin/LocksPage'))
const AuditPage = lazy(() => import('@/features/admin/AuditPage'))
const ReportsHub = lazy(() => import('@/features/reports/ReportsHub').then((m) => ({ default: m.ReportsHub })))
const ReportRoute = lazy(() => import('@/features/reports/ReportsHub').then((m) => ({ default: m.ReportRoute })))

const Loading = () => <div style={{ display: 'grid', placeItems: 'center', minHeight: 240 }}><Spin size="large" /></div>

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <>{children}</>
}

const page = (perm: string, element: ReactNode) => (
  <RequirePerm perm={perm}>
    <Suspense fallback={<Loading />}>{element}</Suspense>
  </RequirePerm>
)

export const router = createBrowserRouter([
  { path: '/login', element: <Suspense fallback={<Loading />}><LoginPage /></Suspense> },
  {
    path: '/',
    element: <RequireAuth><AppLayout /></RequireAuth>,
    children: [
      { index: true, element: page('dashboard.view', <DashboardPage />) },
      { path: 'challans', element: page('challan.create', <ChallanPage />) },
      { path: 'purchases', element: page('purchase.create', <PurchasesPage />) },
      { path: 'rentals', element: page('rental.create', <RentalsPage />) },
      { path: 'payments', element: page('payment.create', <PaymentsPage />) },
      { path: 'expenses', element: page('expense.create', <ExpensesPage />) },
      { path: 'labour', element: page('attendance.write', <LabourPage />) },
      { path: 'stock', element: page('stock.view', <StockPage />) },
      { path: 'invoices', element: page('invoice.create', <InvoicesPage />) },
      { path: 'masters', element: page('masters.read', <MastersPage />) },
      { path: 'reports', element: page('report.khata', <ReportsHub />) },
      { path: 'reports/:key', element: <Suspense fallback={<Loading />}><ReportRoute /></Suspense> },
      { path: 'admin/users', element: page('users.manage', <UsersPage />) },
      { path: 'admin/opening', element: page('opening.write', <OpeningPage />) },
      { path: 'admin/locks', element: page('period.lock', <LocksPage />) },
      { path: 'admin/audit', element: page('audit.view', <AuditPage />) },
      { path: '*', element: <Result status="404" title="Page not found" /> },
    ],
  },
])
