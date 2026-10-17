import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { API_BASE } from '@/lib/config'
import type { ApiErrorBody, TokenOut } from './types'

/** Access token lives in memory only (never localStorage); the refresh token is an httpOnly cookie. */
let accessToken: string | null = null
let onSessionExpired: (() => void) | null = null
let refreshing: Promise<TokenOut | null> | null = null

export const tokenStore = {
  get: () => accessToken,
  set: (t: string | null) => {
    accessToken = t
  },
  onExpired: (fn: () => void) => {
    onSessionExpired = fn
  },
}

export const api = axios.create({ baseURL: API_BASE, withCredentials: true })

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

const AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/logout']

/** One refresh at a time, shared by every request that hit a 401 at the same moment. */
export function refreshSession(): Promise<TokenOut | null> {
  refreshing ??= axios
    .post<TokenOut>(`${API_BASE}/auth/refresh`, null, { withCredentials: true })
    .then((r) => {
      accessToken = r.data.access_token
      return r.data
    })
    .catch(() => null)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError<ApiErrorBody>) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const isAuthCall = AUTH_PATHS.some((p) => original?.url?.startsWith(p))
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true
      const fresh = await refreshSession()
      if (fresh) {
        original.headers.Authorization = `Bearer ${fresh.access_token}`
        return api(original)
      }
      accessToken = null
      onSessionExpired?.()
    }
    return Promise.reject(error)
  },
)

/** Readable message + machine code from any thrown API error. */
export function apiError(err: unknown): { code: string; message: string; details: Record<string, unknown> } {
  if (axios.isAxiosError<ApiErrorBody>(err)) {
    const body = err.response?.data
    if (body && typeof body === 'object' && 'code' in body) {
      const fields = (body.details?.errors as { field: string; message: string }[] | undefined)
        ?.map((e) => `${e.field}: ${e.message}`)
        .join('; ')
      return { code: body.code, message: fields ? `${body.message} (${fields})` : body.message, details: body.details }
    }
    if (!err.response) return { code: 'NETWORK', message: 'Cannot reach the server. Check your connection.', details: {} }
  }
  return { code: 'UNKNOWN', message: err instanceof Error ? err.message : 'Something went wrong', details: {} }
}
