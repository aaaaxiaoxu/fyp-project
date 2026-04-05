<template>
  <div class="min-h-screen bg-black text-white flex items-center justify-center px-4">
    <div class="w-full max-w-md text-center">
      <div class="mb-8 flex justify-center">
        <div class="w-20 h-20 rounded-md bg-black/70 border border-white/10 flex items-center justify-center">
          <span class="font-semibold tracking-wide">GraphRAG</span>
        </div>
      </div>

      <div v-if="loading" class="space-y-4">
        <v-progress-circular indeterminate color="purple" size="64" />
        <h2 class="text-2xl font-semibold">Verifying your email...</h2>
        <p class="text-gray-400">Please wait a moment</p>
      </div>

      <div v-else-if="success" class="space-y-4">
        <v-icon icon="mdi-check-circle" size="64" color="green" />
        <h2 class="text-2xl font-semibold">Email Verified!</h2>
        <p class="text-gray-400">Your email has been successfully verified.</p>
        <v-btn
          color="white"
          class="text-black font-semibold mt-6"
          size="large"
          @click="goToLogin"
        >
          Go to Login
        </v-btn>
      </div>

      <div v-else-if="error" class="space-y-4">
        <v-icon icon="mdi-alert-circle" size="64" color="red" />
        <h2 class="text-2xl font-semibold">Verification Failed</h2>
        <p class="text-gray-400">{{ error }}</p>
        <v-btn
          variant="outlined"
          color="white"
          class="mt-6"
          size="large"
          @click="goToLogin"
        >
          Back to Login
        </v-btn>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApiFetch, getApiErrorMessage } from '../../composables/useApiFetch'

const route = useRoute()
const router = useRouter()
const apiFetch = useApiFetch()

const loading = ref(true)
const success = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  const token = route.query.token as string
  if (!token) {
    error.value = 'Missing verification token'
    loading.value = false
    return
  }

  try {
    await apiFetch(`/auth/verify?token=${encodeURIComponent(token)}`, {
      method: 'GET',
    })
    success.value = true
  } catch (e: any) {
    error.value = getApiErrorMessage(e)
  } finally {
    loading.value = false
  }
})

function goToLogin() {
  router.push('/auth/login')
}
</script>

