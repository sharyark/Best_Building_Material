import { Typography } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useGet } from '@/api/hooks'
import { useLookups } from '@/api/lookups'
import type { DriverSuggestion } from '@/api/types'
import { optionsOf } from '@/components/EntitySelect'
import { QuickAddDriver } from '@/components/QuickAdd'
import { usePermission } from '@/hooks/usePermission'

/**
 * Driver for the chosen vehicle. The vehicle's own driver (set in Masters > Staff) is filled in and locked.
 * Only when it has none, or he is marked absent that day, may the munshi pick a free driver (one not linked to
 * any vehicle); that pick becomes the vehicle's driver for the rest of the day. With no free driver left, the
 * list offers to add a temporary one. The server applies the same rule.
 */
export function useVehicleDriver({ vehicleId, date, driverId, setDriver, editing, role = 'driver' }: {
  vehicleId: number | null | undefined
  date: string | undefined
  driverId: number | null | undefined
  setDriver: (id: number | null) => void
  editing: boolean
  role?: 'driver' | 'operator'
}) {
  const lookups = useLookups()
  const canAdd = usePermission('masters.write')
  const [adding, setAdding] = useState<string | null>(null)
  // While editing, the saved driver stays until the munshi changes the vehicle.
  const picked = useRef(editing)
  const { data, isPlaceholderData } = useGet<DriverSuggestion>(`/masters/vehicles/${vehicleId}/driver`, { on: date }, { enabled: Boolean(vehicleId) })
  const current = vehicleId && !isPlaceholderData ? data : undefined
  const locked = Boolean(current?.locked)

  useEffect(() => {
    if (!current || current.driver_id === (driverId ?? null)) return
    // A locked vehicle overrides an earlier pick (e.g. the date moved to a day its driver is present), except in
    // an edit that keeps its vehicle: that keeps its saved driver even if Masters has changed since.
    if (!picked.current || (current.locked && !editing)) setDriver(current.driver_id)
  }, [current, driverId, setDriver, editing])

  const options = useMemo(() => {
    const allowed = new Set(current?.allowed_driver_ids ?? [])
    // The current value stays listed so a saved or just-added driver still shows by name.
    return optionsOf(lookups.drivers.filter((s) => allowed.has(s.id) || s.id === driverId))
  }, [lookups.drivers, current, driverId])

  const name = (id: number | null | undefined) => (id ? lookups.staffById.get(id)?.name ?? '' : '')
  const noneFree = Boolean(current && !locked && current.allowed_driver_ids.length === 0)
  let hint: React.ReactNode = null
  if (current && locked) hint = driverId === current.regular_driver_id ? 'Vehicle\'s own driver (change in Masters > Staff)' : 'Saved driver kept for this edit'
  else if (current && vehicleId) {
    const why = current.regular_absent ? `${name(current.regular_driver_id)} is absent on this day` : 'This vehicle has no driver of its own'
    if (driverId && driverId === current.driver_id && current.source === 'today') hint = 'Driving this vehicle today'
    else if (noneFree && !driverId) hint = <Typography.Text type="warning">{why}. No free driver left: add a temporary one.</Typography.Text>
    else if (!driverId) hint = <Typography.Text type="warning">{why}. Pick a free driver.</Typography.Text>
  }

  return {
    hint,
    /** Spread onto the driver EntitySelect. */
    selectProps: {
      options,
      disabled: !vehicleId || (locked && driverId === current?.regular_driver_id),
      placeholder: vehicleId ? (noneFree ? 'No free driver' : 'Select driver') : 'Pick vehicle first',
      onAdd: canAdd && noneFree ? (typed: string) => setAdding(typed) : undefined,
      addLabel: `New temporary ${role}`,
      notFoundContent: noneFree ? `No free ${role}: every one is linked to a vehicle` : undefined,
    },
    /** Render once in the form: the "temporary driver" dialog. */
    modal: (
      <QuickAddDriver
        open={adding !== null}
        role={role}
        initialName={adding ?? ''}
        onClose={() => setAdding(null)}
        onCreated={(s) => {
          picked.current = true
          setDriver(s.id)
        }}
      />
    ),
    /** Call from the driver select's onChange. */
    onPick: () => { picked.current = true },
    /** Call when the vehicle changes (and after saving a new entry) so the next suggestion applies. */
    release: () => { picked.current = false },
  }
}
