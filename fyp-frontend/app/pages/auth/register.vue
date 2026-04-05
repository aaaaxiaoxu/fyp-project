<template>
  <div class="min-h-screen bg-black text-white">
    <div class="min-h-screen relative overflow-hidden grid grid-cols-1 lg:grid-cols-2">
      <div
        class="pointer-events-none absolute inset-y-0 left-1/2 w-40 -translate-x-1/2 bg-gradient-to-r from-transparent via-black/60 to-transparent hidden lg:block"
      ></div>
      <!-- Left: Register Panel -->
      <section class="relative flex items-center justify-center px-8 py-10">
        <div class="absolute inset-0 bg-gradient-to-b from-neutral-950 to-neutral-900"></div>
        <div class="absolute inset-y-0 right-0 w-24 bg-gradient-to-r from-transparent to-black/40"></div>

        <div class="relative w-full max-w-sm">
          <div class="mb-8 flex justify-center">
            <div class="w-20 h-20 rounded-md bg-black/70 border border-white/10 flex items-center justify-center">
              <span class="font-semibold tracking-wide">GraphRAG</span>
            </div>
          </div>

          <h1 class="text-3xl font-semibold tracking-tight">Create Account</h1>
          <p class="text-sm text-gray-400 mt-2">Sign up to get started</p>

          <v-alert v-if="error" type="error" variant="tonal" class="mt-6" density="comfortable">
            {{ error }}
          </v-alert>

          <v-alert v-if="success" type="success" variant="tonal" class="mt-6" density="comfortable">
            <div class="text-sm">
              <div class="font-semibold mb-1">Registration successful!</div>
              <div>Please check your email and click the verification link to activate your account.</div>
            </div>
          </v-alert>

          <v-form ref="formRef" class="mt-8" @submit.prevent="onSubmit" v-if="!success">
            <div class="space-y-5">
              <div>
                <div class="text-xs text-gray-400 mb-2">Email</div>
                <v-text-field
                  v-model="form.email"
                  label="Email"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.email]"
                  autocomplete="email"
                  hide-details="auto"
                />
              </div>

              <v-text-field
                v-model="form.nickname"
                label="Nickname (optional)"
                variant="outlined"
                density="comfortable"
                hide-details="auto"
                placeholder="If empty, we'll use your email prefix"
              />

              <v-text-field
                v-model="form.avatarUrl"
                label="Avatar URL (optional)"
                variant="outlined"
                density="comfortable"
                hide-details="auto"
                placeholder="Leave empty to use the default avatar"
              />

              <v-text-field
                v-model="form.password"
                label="Password"
                variant="outlined"
                density="comfortable"
                :type="showPassword ? 'text' : 'password'"
                :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
                @click:append-inner="showPassword = !showPassword"
                :rules="[rules.required, rules.min8]"
                autocomplete="new-password"
                hide-details="auto"
              />

              <v-text-field
                v-model="form.confirmPassword"
                label="Confirm Password"
                variant="outlined"
                density="comfortable"
                :type="showPassword ? 'text' : 'password'"
                :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
                @click:append-inner="showPassword = !showPassword"
                :rules="[rules.required, rules.match]"
                autocomplete="new-password"
                hide-details="auto"
              />

              <v-btn
                type="submit"
                block
                size="large"
                color="white"
                class="text-black font-semibold"
                :loading="loading"
              >
                Sign Up
              </v-btn>

              <div class="text-center text-sm text-gray-400">
                Already have an account?
                <NuxtLink to="/auth/login" class="text-gray-200 hover:text-white"> Log in </NuxtLink>
              </div>
            </div>
          </v-form>

          <div v-if="success" class="mt-8 text-center">
            <NuxtLink to="/auth/login" class="text-gray-200 hover:text-white text-sm">
              Go to Login →
            </NuxtLink>
          </div>
        </div>
      </section>

      <!-- Right: Hero Image Panel -->
      <aside class="relative hidden lg:block overflow-hidden">
        <v-carousel
          height="100%"
          show-arrows="hover"
          hide-delimiter-background
          cycle
          interval="5000"
          class="h-full"
        >
          <v-carousel-item v-for="(img, idx) in heroImages" :key="idx">
            <div class="relative h-full w-full">
              <img :src="img" alt="register hero" class="h-full w-full object-cover" />
              <div class="absolute inset-0 fade-edges pointer-events-none"></div>
              <div class="absolute inset-0 bg-gradient-to-r from-black via-black/40 to-transparent pointer-events-none"></div>
            </div>
          </v-carousel-item>
        </v-carousel>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { getApiErrorMessage } from '../../composables/useApiFetch'
import { useAuthStore } from '../../stores/auth'

const authStore = useAuthStore()
const heroImages = ['/轮播图1.jpeg', '/轮播图2.jpeg', '/轮播图3.jpeg']

const formRef = ref<any>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const success = ref(false)
const showPassword = ref(false)

const form = reactive({
  email: '',
  nickname: '',
  avatarUrl: '',
  password: '',
  confirmPassword: '',
})

const rules = {
  required: (v: string) => !!(v && v.trim()) || 'Required',
  email: (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((v || '').trim()) || 'Invalid email format',
  min8: (v: string) => (v || '').length >= 8 || 'At least 8 characters',
  match: () => form.password === form.confirmPassword || 'Passwords do not match',
}

async function onSubmit() {
  error.value = null
  success.value = false
  const r = await formRef.value?.validate?.()
  if (r && r.valid === false) return

  if (form.password !== form.confirmPassword) {
    error.value = 'Passwords do not match'
    return
  }

  loading.value = true
  try {
    await authStore.register(
      form.email,
      form.password,
      form.nickname || undefined,
      form.avatarUrl || undefined
    )
    success.value = true
  } catch (e: any) {
    error.value = getApiErrorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.fade-edges {
  background:
    linear-gradient(to right, rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0) 25%, rgba(0, 0, 0, 0) 75%, rgba(0, 0, 0, 0.6)),
    linear-gradient(to bottom, rgba(0, 0, 0, 0.45), rgba(0, 0, 0, 0));
  mix-blend-mode: multiply;
}
</style>

