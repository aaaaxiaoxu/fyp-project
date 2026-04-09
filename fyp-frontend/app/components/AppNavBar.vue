<template>
  <v-app-bar
    flat
    :color="transparent ? 'transparent' : '#000000'"
    :class="['border-b border-white/10 px-6', transparent ? '' : 'bg-black']"
    height="80"
  >
    <div class="brand-block" @click="goHome">
      <v-icon icon="mdi-graph-outline" color="deep-orange-lighten-1"></v-icon>
      <span class="brand-text">SOCIOGRAPH</span>
    </div>

    <v-spacer></v-spacer>

    <div class="hidden md:flex gap-6 text-sm font-medium text-gray-300">
      <button
        type="button"
        class="nav-link"
        :class="{ active: currentRoute === '/graph-explorer' }"
        @click="onProtectedClick(() => router.push('/graph-explorer'))"
      >
        Graph Explorer
      </button>
      <button
        type="button"
        class="nav-link"
        :class="{ active: currentRoute === '/graph' }"
        @click="onProtectedClick(() => router.push('/graph'))"
      >
        Graph Workspace
      </button>
      <button
        type="button"
        class="nav-link"
        :class="{ active: currentRoute === '/chat' }"
        @click="onProtectedClick(() => router.push('/chat'))"
      >
        Chat Model
      </button>
      <button type="button" class="nav-link" @click="showComingSoon('About')">About</button>
    </div>

    <v-spacer></v-spacer>

    <button class="entry-btn hidden md:inline-flex" @click="onProtectedClick(() => router.push('/graph'))">
      Open Workspace
    </button>

    <v-app-bar-nav-icon
      class="md:hidden ml-2"
      color="white"
      @click="drawer = !drawer"
    ></v-app-bar-nav-icon>
  </v-app-bar>

  <v-navigation-drawer
    v-model="drawer"
    temporary
    location="right"
    class="bg-black/95 backdrop-blur-md"
  >
    <v-list class="text-white">
      <v-list-item
        prepend-icon="mdi-graph-outline"
        title="Graph Explorer"
        @click="onProtectedClick(() => { router.push('/graph-explorer'); drawer = false })"
      ></v-list-item>

      <v-list-item
        prepend-icon="mdi-graph"
        title="Graph Workspace"
        @click="onProtectedClick(() => { router.push('/graph'); drawer = false })"
      ></v-list-item>

      <v-list-item
        prepend-icon="mdi-chat-processing-outline"
        title="Chat Model"
        @click="onProtectedClick(() => { router.push('/chat'); drawer = false })"
      ></v-list-item>

      <v-list-item
        prepend-icon="mdi-information-outline"
        title="About"
        @click="showComingSoon('About')"
      ></v-list-item>
    </v-list>
  </v-navigation-drawer>

  <v-snackbar
    v-model="snackbar"
    :timeout="3000"
    color="deep-orange"
    location="top"
  >
    {{ snackbarText }}
    <template #actions>
      <v-btn color="white" variant="text" @click="snackbar = false">关闭</v-btn>
    </template>
  </v-snackbar>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

interface Props {
  transparent?: boolean
}

withDefaults(defineProps<Props>(), {
  transparent: false,
})

const router = useRouter()
const route = useRoute()

const drawer = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')

const currentRoute = computed(() => route.path)

function goHome() {
  router.push('/')
}

function onProtectedClick(cb?: () => void) {
  if (typeof cb === 'function') {
    cb()
  }
}

function showComingSoon(feature: string) {
  drawer.value = false
  snackbarText.value = `${feature} 功能即将上线，敬请期待！`
  snackbar.value = true
}
</script>

<style scoped>
.brand-block {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.brand-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 1px;
  color: #fff;
}

.nav-link {
  color: #d4d4d4;
  transition: color 0.2s ease;
}

.nav-link:hover,
.nav-link.active {
  color: #fff;
}

.entry-btn {
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  padding: 10px 18px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  transition: background 0.2s ease, transform 0.2s ease;
}

.entry-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  transform: translateY(-1px);
}
</style>
