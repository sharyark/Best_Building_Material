import { useCallback, useEffect, useRef } from 'react'
import { useLookups } from '@/api/lookups'
import type { Staff } from '@/api/types'
import { formatCurrency, toNumber } from '@/lib/format'

/** Same rule as the server: the driver's trip rate, or his wage when he is paid per trip. */
export function usualTripRate(s: Staff | undefined): string {
  if (!s) return '0'
  if (toNumber(s.trip_rate) > 0) return String(s.trip_rate)
  return s.wage_type === 'per_trip' ? String(s.wage_amount) : '0'
}

/** Trip pay for `trips` trips at the driver's usual rate, as a money string. */
export function tripPayFor(s: Staff | undefined, trips: number): string {
  return (toNumber(usualTripRate(s)) * trips).toFixed(2)
}

/**
 * Pre-fills "Trip pay" as trips x the chosen driver's usual rate, and follows the trip count (2 trolleys =
 * 2 trips). A figure the munshi types stays until the driver changes; an edit keeps its saved figure.
 */
export function useTripPay({ driverId, trips = 1, setTripPay, editing }: {
  driverId: number | null | undefined
  trips?: number
  setTripPay: (v: string) => void
  editing: boolean
}) {
  const { staffById } = useLookups()
  const typed = useRef(editing)
  const prev = useRef({ driverId, trips })

  useEffect(() => {
    const changed = driverId !== prev.current.driverId || trips !== prev.current.trips
    // In an edit, changing the driver or the load count recalculates; until then the saved figure stays.
    if (changed) typed.current = false
    prev.current = { driverId, trips }
    if (!typed.current) setTripPay(driverId ? tripPayFor(staffById.get(driverId), trips) : '')
  }, [driverId, trips, staffById, setTripPay])

  return {
    /** Call from the trip pay input's onChange. */
    onType: useCallback(() => { typed.current = true }, []),
    /** Call after saving a new entry: the form resets, so fill the rate again. */
    refill: useCallback(() => {
      typed.current = false
      setTripPay(driverId ? tripPayFor(staffById.get(driverId), trips) : '')
    }, [driverId, trips, staffById, setTripPay]),
    /** "3 trips x Rs 200" under the field, when the driver has a rate. */
    rateNote: driverId && toNumber(usualTripRate(staffById.get(driverId))) > 0
      ? `${trips} trip${trips === 1 ? '' : 's'} × ${formatCurrency(usualTripRate(staffById.get(driverId)))}`
      : 'No trip rate in Masters: type the amount, or leave 0 for none',
  }
}
