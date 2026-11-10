import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { auth } from '../services/api'

export const useAuthStore = defineStore('auth', () => {
  const household = ref(null)
  const token = ref(localStorage.getItem('token'))

  const isLoggedIn = computed(() => !!token.value)

  async function setSession(response) {
    token.value = response.data.access_token
    localStorage.setItem('token', token.value)
    await fetchHousehold()
  }

  async function login(name, password) {
    await setSession(await auth.login(name, password))
  }

  async function updateHousehold(data) {
    const response = await auth.update(data)
    household.value = response.data
  }

  async function fetchHousehold() {
    if (!token.value) return
    try {
      const response = await auth.me()
      household.value = response.data
    } catch (e) {
      // Only an invalid token should end the session; offline or server errors keep it
      if (e.response?.status === 401) logout()
    }
  }

  function logout() {
    household.value = null
    token.value = null
    localStorage.removeItem('token')
  }

  return { household, token, isLoggedIn, login, updateHousehold, fetchHousehold, logout }
})
