import { formatDate, startOfMonth, toApiDate } from './date'

it('shows DD-MM-YYYY and sends ISO', () => {
  expect(formatDate('2026-03-09')).toBe('09-03-2026')
  expect(toApiDate('2026-03-09')).toBe('2026-03-09')
  expect(formatDate(null)).toBe('')
  expect(startOfMonth('2026-10-17')).toBe('2026-10-01')
})
