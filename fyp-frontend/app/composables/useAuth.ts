import { useState } from 'nuxt/app'
import { useApiFetch } from './useApiFetch'

type AuthUser = {
  id: string
  email: string
  nickname?: string
  avatar_url?: string | null
  is_verified?: boolean
}

export function useAuth() {
  const apiFetch = useApiFetch()
  const user = useState<AuthUser | null>('auth_user', () => null)
  const fetched = useState<boolean>('auth_user_fetched', () => false)

  async function login(email: string, password: string) {
    const res = await apiFetch<{
      ok: boolean
      access_token: string
      user: {
        id: string
        email: string
        nickname?: string
        avatar_url?: string | null
        is_verified?: boolean
      }
    }>('/auth/login', {
      method: 'POST',
      body: { email, password },
    })

    user.value = res.user
    fetched.value = true
    return res
  }

  async function me() {
    try {
      const res = await apiFetch<AuthUser>('/auth/me', { method: 'GET' })
      user.value = res
      return res
    } finally {
      fetched.value = true
    }
  }

  async function ensureMe() {
    if (fetched.value) return user.value
    try {
      await me()
    } catch (e) {
      // ignore errors here; caller can rely on user.value
    }
    return user.value
  }

  async function logout() {
    await apiFetch<{ ok: boolean }>('/auth/logout', { method: 'POST' })
    user.value = null
    fetched.value = true
  }

  return { user, login, me, ensureMe, logout }
}

