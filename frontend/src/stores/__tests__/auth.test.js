import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'
import { vi } from 'vitest'

// Mock the API module
vi.mock('../../services/api', () => ({
  auth: {
    create: vi.fn(),
    login: vi.fn(),
    me: vi.fn(),
    update: vi.fn(),
  },
}))

import { auth as authApi } from '../../services/api'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('has null initial state', () => {
    const store = useAuthStore()
    expect(store.household).toBeNull()
    expect(store.token).toBeNull()
  })

  it('computes isLoggedIn correctly', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    store.token = 'some-token'
    expect(store.isLoggedIn).toBe(true)
  })

  it('login sets token and fetches household', async () => {
    authApi.login.mockResolvedValue({ data: { access_token: 'jwt-456' } })
    authApi.me.mockResolvedValue({ data: { name: 'Home', created_at: '2024-01-01' } })

    const store = useAuthStore()
    await store.login('Home', 'secret')
    expect(store.token).toBe('jwt-456')
    expect(authApi.login).toHaveBeenCalledWith('Home', 'secret')
    expect(store.household.name).toBe('Home')
  })

  it('login failure leaves the user logged out', async () => {
    authApi.login.mockRejectedValue({ response: { status: 401 } })
    const store = useAuthStore()
    await expect(store.login('Home', 'wrong')).rejects.toBeTruthy()
    expect(store.token).toBeNull()
  })

  it('updateHousehold stores the updated household', async () => {
    authApi.update.mockResolvedValue({ data: { name: 'Flat', created_at: '2024-01-01' } })
    const store = useAuthStore()
    store.household = { name: 'Home', created_at: '2024-01-01' }
    await store.updateHousehold({ name: 'Flat' })
    expect(authApi.update).toHaveBeenCalledWith({ name: 'Flat' })
    expect(store.household.name).toBe('Flat')
  })

  it('fetchHousehold sets household data', async () => {
    authApi.me.mockResolvedValue({ data: { name: 'AAAA-BBBB' } })
    const store = useAuthStore()
    store.token = 'jwt-123'
    await store.fetchHousehold()
    expect(store.household).toEqual({ name: 'AAAA-BBBB' })
  })

  it('fetchHousehold calls logout on 401', async () => {
    authApi.me.mockRejectedValue({ response: { status: 401 } })
    const store = useAuthStore()
    store.token = 'jwt-bad'
    await store.fetchHousehold()
    expect(store.token).toBeNull()
    expect(store.household).toBeNull()
  })

  it('fetchHousehold keeps the session on network or server errors', async () => {
    const store = useAuthStore()
    store.token = 'jwt-123'
    authApi.me.mockRejectedValueOnce(new Error('Network Error'))
    await store.fetchHousehold()
    authApi.me.mockRejectedValueOnce({ response: { status: 503 } })
    await store.fetchHousehold()
    expect(store.token).toBe('jwt-123')
  })

  it('fetchHousehold skips if no token', async () => {
    const store = useAuthStore()
    await store.fetchHousehold()
    expect(authApi.me).not.toHaveBeenCalled()
  })

  it('logout clears all state', () => {
    const store = useAuthStore()
    store.token = 'jwt-123'
    store.household = { name: 'AAAA-BBBB' }
    store.logout()
    expect(store.token).toBeNull()
    expect(store.household).toBeNull()
    expect(localStorage.removeItem).toHaveBeenCalledWith('token')
  })
})
