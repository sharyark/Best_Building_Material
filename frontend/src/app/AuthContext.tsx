import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, refreshSession, tokenStore } from '@/api/client'
import type { Me, TokenOut } from '@/api/types'

interface AuthState {
  user: Me | null
  loading: boolean
  login: (phone: string, password: string) => Promise<void>
  logout: () => Promise<void>
  can: (perm: string) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function hasPermission(user: Me | null, perm: string): boolean {
  if (!user) return false
  return user.permissions.includes('*') || user.permissions.includes(perm)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const qc = useQueryClient()

  useEffect(() => {
    tokenStore.onExpired(() => {
      setUser(null)
      qc.clear()
    })
    // Restore the session from the httpOnly refresh cookie (the access token is memory-only).
    refreshSession()
      .then((t) => setUser(t?.user ?? null))
      .finally(() => setLoading(false))
  }, [qc])

  const login = useCallback(async (phone: string, password: string) => {
    const { data } = await api.post<TokenOut>('/auth/login', { phone, password })
    tokenStore.set(data.access_token)
    setUser(data.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      tokenStore.set(null)
      setUser(null)
      qc.clear()
    }
  }, [qc])

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, logout, can: (perm) => hasPermission(user, perm) }),
    [user, loading, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
