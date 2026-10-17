import { useAuth } from '@/app/AuthContext'

/** Cosmetic only: hides/disables buttons. The server enforces every permission. */
export function usePermission(perm: string): boolean {
  return useAuth().can(perm)
}
