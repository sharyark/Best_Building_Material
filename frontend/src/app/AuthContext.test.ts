import type { Me } from '@/api/types'
import { hasPermission } from './AuthContext'

const base: Me = { id: 1, name: 'x', phone: 'x', email: null, role: 'accountant', staff_id: null, party_id: null, is_active: true, permissions: ['challan.create', 'masters.read'] }

describe('hasPermission', () => {
  it('checks the role permission list', () => {
    expect(hasPermission(base, 'challan.create')).toBe(true)
    expect(hasPermission(base, 'challan.void')).toBe(false)
    expect(hasPermission(null, 'challan.create')).toBe(false)
  })
  it('treats * as everything (admin)', () => {
    expect(hasPermission({ ...base, role: 'admin', permissions: ['*'] }, 'report.profit')).toBe(true)
  })
})
