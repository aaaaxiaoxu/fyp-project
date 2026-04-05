<template>
  <v-app theme="dark">
    <AppNavBar />
    <v-main>
      <v-container class="h-screen flex flex-col justify-center items-center text-center">
        <h1 class="text-4xl font-bold mb-4">Welcome</h1>
        <p class="text-gray-400 mb-8">Coming soon.</p>
        <v-btn color="white" class="text-black" @click="router.push('/auth/login')">
          Get Started
        </v-btn>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>
