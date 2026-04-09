<script setup lang="ts">
import { navigateTo, useHead } from 'nuxt/app'

useHead({
  title: 'SocioGraph',
})

await navigateTo('/graph', { replace: true })
</script>

<template>
  <div class="redirect-shell">
    <div class="redirect-mark">SOCIOGRAPH</div>
    <div class="redirect-text">Opening workspace...</div>
  </div>
</template>

<style scoped>
.redirect-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #ffffff;
  color: #111;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.redirect-mark {
  font-family: 'JetBrains Mono', monospace;
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.24em;
}

.redirect-text {
  margin-top: 10px;
  font-size: 12px;
  color: #777;
  text-align: center;
}
</style>
