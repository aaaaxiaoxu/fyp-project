<template>
    <v-app theme="dark" class="bg-black text-white font-sans selection:bg-purple-500 selection:text-white">
      <AppNavBar :transparent="true" />
  
      <v-main class="relative overflow-hidden">
        <div class="absolute inset-0 z-0 pointer-events-none">
          <div class="absolute top-20 left-20 w-96 h-96 bg-purple-600/20 rounded-full blur-[120px] animate-pulse"></div>
          <div class="absolute bottom-20 right-20 w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[100px]"></div>
        </div>
        <div v-if="!user" class="absolute inset-0 z-20 cursor-pointer" @click="goLogin"></div>
  
        <v-container class="h-[85vh] flex flex-col justify-center items-center text-center relative z-10">
          
          <div 
            v-motion
            :initial="{ opacity: 0, y: 50 }"
            :enter="{ opacity: 1, y: 0, transition: { duration: 1000, type: 'spring' } }"
            class="max-w-4xl mx-auto"
          >
            <div class="inline-block px-4 py-1.5 mb-6 border border-white/10 rounded-full bg-white/5 backdrop-blur-sm text-xs font-mono text-purple-300">
              Based on Neo4j & LLM Integration
            </div>
            
            <h1 class="text-6xl md:text-8xl font-bold tracking-tight leading-tight mb-6">
              Bring Fictional Worlds<br />
              <span class="bg-clip-text text-transparent bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400">
                Within Your Reach
              </span>
            </h1>
            
            <p class="text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
              Upload your novels and automatically extract entities and relationships using LLMs.
              <br class="hidden md:block" />
              Roam through a <strong>Neo4j-powered</strong> knowledge graph and converse with characters across time and space.
            </p>
  
            <div class="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <v-btn 
                size="x-large" 
                color="white" 
                class="text-black font-bold px-10 tracking-wide hover:scale-105 transition-transform"
                elevation="0"
                rounded="lg"
                @click="onPrimaryClick"
              >
                Build Graph
                <v-icon end icon="mdi-arrow-right" class="ml-2"></v-icon>
              </v-btn>
              <v-btn 
                size="x-large" 
                variant="text" 
                class="text-gray-300 hover:text-white"
                @click="onSecondaryClick"
              >
                Try Chat
                <v-icon end icon="mdi-message-text" class="ml-2"></v-icon>
              </v-btn>
            </div>
          </div>
        </v-container>
  
        <v-container class="py-20 relative z-10">
          <v-row>
            <v-col cols="12" md="6">
              <div 
                v-motion-slide-visible-bottom
                class="group relative h-full bg-neutral-900/50 border border-white/10 rounded-3xl p-8 overflow-hidden hover:border-purple-500/50 transition-colors duration-500"
              >
                <div class="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                
                <v-icon icon="mdi-molecule" size="48" class="text-purple-400 mb-6"></v-icon>
                <h3 class="text-3xl font-bold mb-4">Graph Visualization</h3>
                <p class="text-gray-400 mb-8 h-24">
                  Deeply reconstruct complex character relationships in masterpieces like <em>The Ordinary World</em>. Nodes, events, and family trees—all in a Neo4j-driven interactive 3D canvas.
                </p>
                
                <div class="w-full h-48 bg-black/50 rounded-xl border border-white/5 relative overflow-hidden flex items-center justify-center">
                   <div class="absolute inset-0 flex items-center justify-center opacity-30">
                      <svg class="w-full h-full animate-spin-slow" viewBox="0 0 100 100" style="animation-duration: 20s">
                        <circle cx="50" cy="50" r="20" stroke="currentColor" stroke-width="0.5" fill="none" class="text-purple-500"/>
                        <circle cx="50" cy="50" r="35" stroke="currentColor" stroke-width="0.5" fill="none" class="text-blue-500" style="stroke-dasharray: 4 4"/>
                        <line x1="50" y1="50" x2="80" y2="20" stroke="currentColor" stroke-width="0.5" class="text-gray-600" />
                        <circle cx="80" cy="20" r="2" fill="currentColor" class="text-white"/>
                      </svg>
                   </div>
                   <span class="text-sm font-mono text-purple-300 bg-purple-900/30 px-3 py-1 rounded border border-purple-500/30">MATCH (n:Person) RETURN n</span>
                </div>
              </div>
            </v-col>
  
            <v-col cols="12" md="6">
              <div 
                v-motion-slide-visible-bottom
                :delay="200"
                class="group relative h-full bg-neutral-900/50 border border-white/10 rounded-3xl p-8 overflow-hidden hover:border-blue-500/50 transition-colors duration-500"
              >
                 <div class="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
  
                <v-icon icon="mdi-chat-processing-outline" size="48" class="text-blue-400 mb-6"></v-icon>
                <h3 class="text-3xl font-bold mb-4">GraphRAG Intelligence</h3>
                <p class="text-gray-400 mb-8 h-24">
                  Beyond simple keyword search. Based on graph path retrieval (GraphRAG), accurately answer complex logical questions like "How did their relationship evolve?"
                </p>

                <div class="w-full h-48 flex flex-col gap-3 justify-center px-4">
                  <div class="self-end bg-blue-600/20 text-blue-100 px-4 py-2 rounded-2xl rounded-tr-sm text-sm border border-blue-500/20 max-w-[80%]">
                    Where did Sun Shaoping end up?
                  </div>
                  <div class="self-start bg-neutral-800 text-gray-300 px-4 py-2 rounded-2xl rounded-tl-sm text-sm border border-white/5 max-w-[90%]">
                    <span class="text-purple-400 text-xs mb-1 block">Thinking (Graph Search)...</span>
                    Based on entity relationship extraction, he eventually became a miner at the Dayawan Coal Mine...
                  </div>
                </div>

                <div class="mt-6">
                  <v-btn 
                    variant="outlined" 
                    color="blue" 
                    class="w-full"
                    @click="onProtectedClick(() => router.push('/chat'))"
                  >
                    Try Chat Now
                    <v-icon end icon="mdi-arrow-right"></v-icon>
                  </v-btn>
                </div>
              </div>
            </v-col>
          </v-row>
        </v-container>
  
        <footer class="border-t border-white/10 py-12 text-center text-gray-500 text-sm">
          <p>© 2024 GraphRAG Project. Powered by Nuxt 3, Neo4j & LLM.</p>
        </footer>
  
      </v-main>
    </v-app>
  </template>
  
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const user = computed(() => authStore.user)

onMounted(() => {
  authStore.ensureMe()
})

function goLogin() {
  router.push('/auth/login')
}

function onProtectedClick(cb?: () => void) {
  if (!authStore.user) {
    router.push('/auth/login')
    return
  }
  if (typeof cb === 'function') cb()
}

function onPrimaryClick() {
  onProtectedClick(() => router.push('/graph-explorer'))
}

function onSecondaryClick() {
  onProtectedClick(() => router.push('/chat'))
}
  </script>
  
  <style scoped>
  /* Slow Spin Animation */
  .animate-spin-slow {
    animation: spin 30s linear infinite;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  </style>