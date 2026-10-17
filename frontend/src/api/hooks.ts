import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { App } from 'antd'
import { api, apiError } from './client'
import type { Page } from './types'

type Params = Record<string, string | number | boolean | undefined | null>

function clean(params?: Params) {
  return Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== ''))
}

export function useGet<T>(url: string, params?: Params, options: { enabled?: boolean; staleTime?: number } = {}) {
  return useQuery({
    queryKey: [url, clean(params)],
    queryFn: async () => (await api.get<T>(url, { params: clean(params) })).data,
    placeholderData: keepPreviousData,
    ...options,
  })
}

export function usePage<T>(url: string, params?: Params) {
  return useGet<Page<T>>(url, params)
}

/** POST/PUT/PATCH with toast on error. A saved financial change can move balances anywhere, so refetch all. */
export function useSave<TIn, TOut = unknown>(
  method: 'post' | 'put' | 'patch',
  url: string | ((v: TIn) => string),
  opts: { onSuccess?: (data: TOut, v: TIn) => void; successMessage?: string } = {},
) {
  const qc = useQueryClient()
  const { message } = App.useApp()
  return useMutation({
    mutationFn: async (v: TIn) => (await api[method]<TOut>(typeof url === 'function' ? url(v) : url, v)).data,
    onSuccess: async (data, v) => {
      await qc.invalidateQueries()
      if (opts.successMessage) message.success(opts.successMessage)
      opts.onSuccess?.(data, v)
    },
    onError: (err) => message.error(apiError(err).message, 6),
  })
}
