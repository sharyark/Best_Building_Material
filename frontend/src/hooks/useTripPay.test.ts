import { describe, expect, it } from 'vitest'
import type { Staff } from '@/api/types'
import { tripPayFor, usualTripRate } from './useTripPay'

const staff = (over: Partial<Staff>): Staff => ({
  id: 1, name: 'Ali', phone: null, role: 'driver', wage_type: 'monthly', wage_amount: '15000.00', trip_rate: '0.00',
  default_vehicle_id: null, account_id: 1, is_active: true, ...over,
})

describe('usualTripRate', () => {
  it('uses the trip rate when set', () => expect(usualTripRate(staff({ trip_rate: '200.00' }))).toBe('200.00'))
  it('falls back to the wage for per-trip workers', () => expect(usualTripRate(staff({ wage_type: 'per_trip', wage_amount: '180.00' }))).toBe('180.00'))
  it('is zero for salaried drivers without a trip rate', () => expect(usualTripRate(staff({}))).toBe('0'))
  it('is zero when no driver is known', () => expect(usualTripRate(undefined)).toBe('0'))
})

describe('tripPayFor', () => {
  it('multiplies the rate by the trips', () => expect(tripPayFor(staff({ trip_rate: '200.00' }), 3)).toBe('600.00'))
  it('is zero without a rate', () => expect(tripPayFor(staff({}), 3)).toBe('0.00'))
})
