import { useRequestEvent, useRequestHeaders, useRuntimeConfig } from 'nuxt/app'

export function useApiFetch() {
  const config = useRuntimeConfig()

  return async function apiFetch<T>(path: string, opts: any = {}): Promise<T> {
    const headers: Record<string, string> = {
      ...(opts.headers || {}),
    }

    // SSR 时把浏览器 cookie 带到后端（/auth/me 这种会用到）
    const event = useRequestEvent()
    if (event) {
      Object.assign(headers, useRequestHeaders(['cookie']))
    }

    return await $fetch<T>(path, {
      baseURL: config.public.apiBase,
      credentials: 'include', // 关键：让浏览器接收/携带后端 set-cookie
      ...opts,
      headers,
    })
  }
}

export function getApiErrorMessage(e: any): string {
  return e?.data?.detail || e?.message || 'Request failed'
}

