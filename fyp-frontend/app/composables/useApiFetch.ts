import { useRuntimeConfig } from 'nuxt/app'

export function useApiFetch() {
  const config = useRuntimeConfig()

  return async function apiFetch<T>(path: string, opts: any = {}): Promise<T> {
    return await $fetch<T>(path, {
      baseURL: config.public.apiBase,
      retry: false,
      ...opts,
    })
  }
}

export function getApiErrorMessage(e: any): string {
  return e?.data?.detail || e?.message || 'Request failed'
}
