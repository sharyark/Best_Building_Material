import axios, { type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { api, apiError, tokenStore } from './client'

function respond(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { data, status, statusText: String(status), headers: {}, config }
  return status < 400 ? Promise.resolve(response) : Promise.reject(Object.assign(new axios.AxiosError('x', undefined, config, undefined, response), { response }))
}

const user = { id: 1, name: 'A', phone: 'a', email: null, role: 'admin', staff_id: null, party_id: null, is_active: true, permissions: ['*'] }

describe('api client', () => {
  const originalApi = api.defaults.adapter
  const originalAxios = axios.defaults.adapter
  afterEach(() => {
    api.defaults.adapter = originalApi
    axios.defaults.adapter = originalAxios
    tokenStore.set(null)
  })

  it('refreshes once for several parallel 401s, then retries each request with the new token', async () => {
    let refreshCalls = 0
    const seen: (string | undefined)[] = []
    axios.defaults.adapter = ((config) => {
      refreshCalls += 1
      return respond(config, 200, { access_token: 'fresh', expires_in: 900, user })
    }) as AxiosAdapter
    api.defaults.adapter = ((config) => {
      const auth = config.headers.Authorization as string | undefined
      seen.push(auth)
      return auth === 'Bearer fresh' ? respond(config, 200, { ok: true }) : respond(config, 401, { code: 'INVALID_TOKEN', message: 'expired', details: {} })
    }) as AxiosAdapter
    tokenStore.set('stale')

    const results = await Promise.all([api.get('/a'), api.get('/b'), api.get('/c')])
    expect(results.map((r) => r.data)).toEqual([{ ok: true }, { ok: true }, { ok: true }])
    expect(refreshCalls).toBe(1)
    expect(tokenStore.get()).toBe('fresh')
    expect(seen.filter((s) => s === 'Bearer fresh')).toHaveLength(3)
  })

  it('signs the user out when the refresh fails', async () => {
    const expired = vi.fn()
    tokenStore.onExpired(expired)
    axios.defaults.adapter = ((config) => respond(config, 401, { code: 'INVALID_REFRESH_TOKEN', message: 'no', details: {} })) as AxiosAdapter
    api.defaults.adapter = ((config) => respond(config, 401, { code: 'INVALID_TOKEN', message: 'expired', details: {} })) as AxiosAdapter
    tokenStore.set('stale')
    await expect(api.get('/a')).rejects.toBeTruthy()
    expect(expired).toHaveBeenCalled()
    expect(tokenStore.get()).toBeNull()
  })

  it('does not try to refresh a failed login', async () => {
    let refreshCalls = 0
    axios.defaults.adapter = ((config) => { refreshCalls += 1; return respond(config, 200, {}) }) as AxiosAdapter
    api.defaults.adapter = ((config) => respond(config, 401, { code: 'INVALID_CREDENTIALS', message: 'Wrong phone or password', details: {} })) as AxiosAdapter
    await expect(api.post('/auth/login', {})).rejects.toBeTruthy()
    expect(refreshCalls).toBe(0)
  })
})

describe('apiError', () => {
  it('reads the backend error shape and lists field errors', async () => {
    api.defaults.adapter = ((config) => respond(config, 422, { code: 'VALIDATION_ERROR', message: 'Invalid input', details: { errors: [{ field: 'qty', message: 'must be > 0' }] } })) as AxiosAdapter
    const err = await api.get('/x').catch((e) => e)
    expect(apiError(err)).toMatchObject({ code: 'VALIDATION_ERROR', message: 'Invalid input (qty: must be > 0)' })
  })
  it('explains network failures', async () => {
    api.defaults.adapter = ((config) => Promise.reject(new axios.AxiosError('Network Error', 'ERR_NETWORK', config))) as AxiosAdapter
    const err = await api.get('/x').catch((e) => e)
    expect(apiError(err).code).toBe('NETWORK')
  })
})
