import { defineStore } from 'pinia'
import { useApiFetch } from '../composables/useApiFetch'

export type AuthUser = {
  id: string
  email: string
  nickname?: string
  avatar_url?: string | null
  is_verified?: boolean
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as AuthUser | null,
    fetched: false,
    accessToken: null as string | null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.user,
    isVerified: (state) => state.user?.is_verified ?? false,
  },

  actions: {
    async register(email: string, password: string, nickname?: string, avatar_url?: string) {
      const apiFetch = useApiFetch()
      const res = await apiFetch<{
        ok: boolean
        message: string
        user: AuthUser
      }>('/auth/register', {
        method: 'POST',
        body: { email, password, nickname, avatar_url },
      })
      return res
    },

    async login(email: string, password: string) {
      const apiFetch = useApiFetch()
      const res = await apiFetch<{
        ok: boolean
        access_token: string
        user: AuthUser
      }>('/auth/login', {
        method: 'POST',
        body: { email, password },
      })

      this.user = res.user
      this.accessToken = res.access_token
      this.fetched = true
      return res
    },

    async fetchMe() {
      const apiFetch = useApiFetch()
      try {
        const res = await apiFetch<AuthUser>('/auth/me', { method: 'GET' })
        this.user = res
        // 如果 /auth/me 成功但没有 accessToken，说明是通过 cookie 认证的
        // 这种情况下保持 accessToken 为 null，后续请求会依赖 cookie
        return res
      } catch (error) {
        this.user = null
        this.accessToken = null
        throw error
      } finally {
        this.fetched = true
      }
    },

    async ensureMe() {
      if (this.fetched) return this.user
      try {
        await this.fetchMe()
      } catch (e) {
        // Ignore errors; caller can check user state
      }
      return this.user
    },

    async logout() {
      const apiFetch = useApiFetch()
      await apiFetch<{ ok: boolean }>('/auth/logout', { method: 'POST' })
      this.user = null
      this.accessToken = null
      this.fetched = true
    },
  },
})

