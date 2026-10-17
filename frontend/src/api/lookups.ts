import { useMemo } from 'react'
import { useGet } from './hooks'
import type { Material, MoneyAccount, Page, Party, Site, Staff, Vehicle } from './types'

const STALE = 60_000
const ALL = { size: 500 }

/** Master data for selects. Cached, so every form shares one fetch. */
export function useLookups() {
  const parties = useGet<Page<Party>>('/masters/parties', ALL, { staleTime: STALE })
  const sites = useGet<Page<Site>>('/masters/sites', ALL, { staleTime: STALE })
  const materials = useGet<Page<Material>>('/masters/materials', ALL, { staleTime: STALE })
  const vehicles = useGet<Page<Vehicle>>('/masters/vehicles', ALL, { staleTime: STALE })
  const staff = useGet<Page<Staff>>('/masters/staff', ALL, { staleTime: STALE })
  const moneyAccounts = useGet<Page<MoneyAccount>>('/masters/money-accounts', ALL, { staleTime: STALE })

  return useMemo(() => {
    const p = parties.data?.items ?? []
    const byId = <T extends { id: number }>(rows: T[]) => new Map(rows.map((r) => [r.id, r]))
    const m = materials.data?.items ?? []
    const v = vehicles.data?.items ?? []
    const s = staff.data?.items ?? []
    const ma = moneyAccounts.data?.items ?? []
    const si = sites.data?.items ?? []
    return {
      loading: [parties, sites, materials, vehicles, staff, moneyAccounts].some((q) => q.isLoading),
      parties: p,
      customers: p.filter((x) => x.type !== 'supplier' && x.is_active),
      suppliers: p.filter((x) => x.type !== 'customer' && x.is_active),
      sites: si,
      materials: m.filter((x) => x.is_active),
      allMaterials: m,
      vehicles: v.filter((x) => x.is_active),
      allVehicles: v,
      staff: s.filter((x) => x.is_active),
      allStaff: s,
      drivers: s.filter((x) => x.is_active && (x.role === 'driver' || x.role === 'operator')),
      moneyAccounts: ma.filter((x) => x.is_active),
      partyById: byId(p),
      siteById: byId(si),
      materialById: byId(m),
      vehicleById: byId(v),
      staffById: byId(s),
      moneyAccountById: byId(ma),
    }
  }, [parties, sites, materials, vehicles, staff, moneyAccounts])
}

export type Lookups = ReturnType<typeof useLookups>
