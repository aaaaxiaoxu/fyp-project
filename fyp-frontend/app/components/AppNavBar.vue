<template>
  <v-app-bar 
    flat 
    :color="transparent ? 'transparent' : 'rgba(0, 0, 0, 0.8)'" 
    :class="['backdrop-blur-md border-b border-white/10 px-6', transparent ? '' : 'bg-black/80']" 
    height="80"
  >
    <!-- Logo -->
    <div class="text-2xl font-bold tracking-tighter flex items-center gap-2 cursor-pointer" @click="goHome">
      <v-icon icon="mdi-graph-outline" color="purple-accent-2"></v-icon>
      <span>Graph<span class="text-purple-400">RAG</span>.io</span>
    </div>

    <v-spacer></v-spacer>

    <!-- 导航链接 -->
    <div class="hidden md:flex gap-6 text-sm font-medium text-gray-300">
      <button 
        type="button" 
        class="hover:text-white transition-colors"
        :class="{ 'text-purple-400': currentRoute === '/graph-explorer' }"
        @click="onProtectedClick(() => router.push('/graph-explorer'))"
      >
        Graph Explorer
      </button>
      <button 
        type="button" 
        class="hover:text-white transition-colors"
        :class="{ 'text-purple-400': currentRoute === '/graph' }"
        @click="onProtectedClick(() => router.push('/graph'))"
      >
        Graph (Simple)
      </button>
      <button 
        type="button" 
        class="hover:text-white transition-colors"
        :class="{ 'text-purple-400': currentRoute === '/chat' }"
        @click="onProtectedClick(() => router.push('/chat'))"
      >
        Chat Model
      </button>
      <button 
        type="button" 
        class="hover:text-white transition-colors"
        @click="onProtectedClick(() => showComingSoon('About'))"
      >
        About
      </button>
    </div>

    <v-spacer></v-spacer>

    <!-- 用户信息/登录按钮 -->
    <div class="flex items-center gap-3">
      <template v-if="user">
        <div class="hidden md:flex flex-col items-end text-right leading-tight">
          <span class="text-sm text-gray-100">{{ user.nickname || 'Signed in' }}</span>
          <span class="text-xs text-gray-400">{{ user.email }}</span>
        </div>
        <v-menu location="bottom end">
          <template #activator="{ props }">
            <v-avatar v-bind="props" size="42" class="cursor-pointer ring-1 ring-white/20" color="purple">
              <v-img v-if="avatarSrc" :src="avatarSrc" alt="avatar" cover></v-img>
              <span v-else class="text-lg font-bold">{{ user?.nickname?.charAt(0) || user?.email?.charAt(0) || 'U' }}</span>
            </v-avatar>
          </template>
          <v-list density="compact">
            <v-list-item :title="user.nickname || user.email" :subtitle="user.email" />
            <v-divider />
            <v-list-item title="Profile" @click="goProfile" />
            <v-list-item title="Sign out" @click="onLogout" />
          </v-list>
        </v-menu>
      </template>
      <template v-else>
        <v-btn variant="text" rounded="xl" color="white" class="text-gray-200" @click="goLogin">
          Sign in
        </v-btn>
        <v-btn
          variant="outlined"
          rounded="xl"
          color="white"
          class="px-6 border-white/20 hover:bg-white hover:text-black transition-all"
          @click="goRegister"
        >
          Sign up
        </v-btn>
      </template>
    </div>

    <!-- 移动端菜单 -->
    <v-app-bar-nav-icon 
      class="md:hidden ml-2" 
      @click="drawer = !drawer"
      color="white"
    ></v-app-bar-nav-icon>
  </v-app-bar>

  <!-- 移动端抽屉 -->
  <v-navigation-drawer
    v-model="drawer"
    temporary
    location="right"
    class="bg-black/95 backdrop-blur-md"
  >
    <v-list class="text-white">
      <v-list-item 
        v-if="user"
        :title="user.nickname || user.email" 
        :subtitle="user.email"
        class="mb-4"
      >
        <template #prepend>
          <v-avatar size="40" color="purple">
            <v-img v-if="avatarSrc" :src="avatarSrc" alt="avatar" cover></v-img>
            <span v-else class="text-sm font-bold">{{ user?.nickname?.charAt(0) || user?.email?.charAt(0) || 'U' }}</span>
          </v-avatar>
        </template>
      </v-list-item>

      <v-divider v-if="user" class="mb-2"></v-divider>

      <v-list-item 
        prepend-icon="mdi-graph-outline"
        title="Graph Explorer"
        @click="onProtectedClick(() => { router.push('/graph-explorer'); drawer = false })"
      ></v-list-item>

      <v-list-item 
        prepend-icon="mdi-graph"
        title="Graph (Simple)"
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
        @click="onProtectedClick(() => { showComingSoon('About'); drawer = false })"
      ></v-list-item>

      <v-divider class="my-2"></v-divider>

      <template v-if="user">
        <v-list-item 
          prepend-icon="mdi-account"
          title="Profile"
          @click="goProfile"
        ></v-list-item>
        <v-list-item 
          prepend-icon="mdi-logout"
          title="Sign out"
          @click="onLogout"
        ></v-list-item>
      </template>
      <template v-else>
        <v-list-item 
          prepend-icon="mdi-login"
          title="Sign in"
          @click="goLogin"
        ></v-list-item>
        <v-list-item 
          prepend-icon="mdi-account-plus"
          title="Sign up"
          @click="goRegister"
        ></v-list-item>
      </template>
    </v-list>
  </v-navigation-drawer>

  <!-- Coming Soon 提示 -->
  <v-snackbar
    v-model="snackbar"
    :timeout="3000"
    color="purple"
    location="top"
  >
    {{ snackbarText }}
    <template #actions>
      <v-btn
        color="white"
        variant="text"
        @click="snackbar = false"
      >
        关闭
      </v-btn>
    </template>
  </v-snackbar>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

interface Props {
  transparent?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  transparent: false
})

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const drawer = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')

const user = computed(() => authStore.user)
const avatarSrc = computed(() => {
  if (authStore.user?.avatar_url) {
    return authStore.user.avatar_url
  }
  // 如果没有头像URL，返回空，使用 v-avatar 的默认行为（显示首字母）
  return undefined
})
const currentRoute = computed(() => route.path)

function goHome() {
  router.push('/')
}

function goLogin() {
  router.push('/auth/login')
}

function goRegister() {
  router.push('/auth/register')
}

function goProfile() {
  showComingSoon('Profile')
  drawer.value = false
}

async function onLogout() {
  await authStore.logout()
  drawer.value = false
  goLogin()
}

function onProtectedClick(cb?: () => void) {
  if (!authStore.user) {
    goLogin()
    return
  }
  if (typeof cb === 'function') cb()
}

function showComingSoon(feature: string) {
  snackbarText.value = `${feature} 功能即将上线，敬请期待！`
  snackbar.value = true
}
</script>

<style scoped>
.v-app-bar {
  backdrop-filter: blur(12px);
}
</style>

