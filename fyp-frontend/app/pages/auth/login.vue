<template>
    <div class="min-h-screen bg-black text-white">
      <div class="min-h-screen relative overflow-hidden grid grid-cols-1 lg:grid-cols-2">
        <div
          class="pointer-events-none absolute inset-y-0 left-1/2 w-40 -translate-x-1/2 bg-gradient-to-r from-transparent via-black/60 to-transparent hidden lg:block"
        ></div>
        <!-- Left: Login Panel -->
        <section class="relative flex items-center justify-center px-8 py-10">
          <!-- subtle background -->
          <div class="absolute inset-0 bg-gradient-to-b from-neutral-950 to-neutral-900"></div>
          <div class="absolute inset-y-0 right-0 w-24 bg-gradient-to-r from-transparent to-black/40"></div>
  
          <div class="relative w-full max-w-sm">
            <!-- Logo -->
            <div class="mb-8 flex justify-center">
              <div
                class="w-20 h-20 rounded-md bg-black/70 border border-white/10 flex items-center justify-center"
              >
                <span class="font-semibold tracking-wide">GraphRAG</span>
              </div>
            </div>
  
            <h1 class="text-3xl font-semibold tracking-tight">Welcome back</h1>
            <p class="text-sm text-gray-400 mt-2">Sign in to continue</p>
  
            <v-alert
              v-if="successMessage"
              type="success"
              variant="tonal"
              class="mt-6"
              density="comfortable"
            >
              {{ successMessage }}
            </v-alert>

            <v-alert
              v-if="error"
              type="error"
              variant="tonal"
              class="mt-6"
              density="comfortable"
            >
              <div class="text-sm">
                <div>{{ error }}</div>
                <div v-if="showVerifyHint" class="mt-2 text-xs">
                  Please check your email for the verification link. Didn't receive it? Contact support.
                </div>
              </div>
            </v-alert>
  
            <v-form ref="formRef" class="mt-8" @submit.prevent="onSubmit">
              <div class="space-y-5">
                <div>
                  <div class="text-xs text-gray-400 mb-2">Sign in with your email</div>
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
                  v-model="form.password"
                  label="Password"
                  variant="outlined"
                  density="comfortable"
                  :type="showPassword ? 'text' : 'password'"
                  :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
                  @click:append-inner="showPassword = !showPassword"
                  :rules="[rules.required, rules.min8]"
                  autocomplete="current-password"
                  hide-details="auto"
                />
  
                <div class="flex items-center justify-between">
                  <v-checkbox
                    v-model="form.remember"
                    label="Remember me?"
                    density="compact"
                    hide-details
                  />
                  <button
                    type="button"
                    class="text-sm text-blue-300 hover:text-blue-200 transition-colors"
                    @click="onForgot"
                  >
                    Forgot password?
                  </button>
                </div>
  
                <v-btn
                  type="submit"
                  block
                  size="large"
                  color="white"
                  class="text-black font-semibold"
                  :loading="loading"
                >
                  Sign in
                </v-btn>
  
                <div class="text-center text-sm text-gray-400">
                  New here?
                  <NuxtLink to="/auth/register" class="text-gray-200 hover:text-white">
                    Sign up
                  </NuxtLink>
                </div>
              </div>
            </v-form>
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
                <img :src="img" alt="login hero" class="h-full w-full object-cover" />
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
import { ref, reactive, computed } from "vue";
import { navigateTo, useRoute } from "nuxt/app";
import { getApiErrorMessage } from "../../composables/useApiFetch";
import { useAuthStore } from "../../stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const heroImages = ["/轮播图1.jpeg", "/轮播图2.jpeg", "/轮播图3.jpeg"];

const formRef = ref<any>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const showVerifyHint = ref(false);
const successMessage = computed(() => {
  return route.query.registered ? "Registration successful! Please verify your email before logging in." : null;
});

const form = reactive({
  email: "",
  password: "",
  remember: true,
});

const showPassword = ref(false);

const rules = {
  required: (v: string) => !!(v && v.trim()) || "Required",
  email: (v: string) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((v || "").trim()) || "Invalid email format",
  min8: (v: string) => (v || "").length >= 8 || "At least 8 characters",
};

async function onSubmit() {
  error.value = null;
  showVerifyHint.value = false;
  const r = await formRef.value?.validate?.();
  if (r && r.valid === false) return;

  loading.value = true;
  try {
    await authStore.login(form.email, form.password);
    // On success, backend sets cookie, then redirect
    await navigateTo("/");
  } catch (e: any) {
    const errorMsg = getApiErrorMessage(e);
    error.value = errorMsg;
    
    // Check if it's an email verification error (403 or contains "not verified")
    if (errorMsg.toLowerCase().includes("not verified") || errorMsg.toLowerCase().includes("verify")) {
      showVerifyHint.value = true;
    }
  } finally {
    loading.value = false;
  }
}

function onForgot() {
  // Backend has no /forgot-password yet; placeholder for now
  error.value = "Forgot password flow not implemented (backend needs /auth/forgot-password).";
  showVerifyHint.value = false;
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
  