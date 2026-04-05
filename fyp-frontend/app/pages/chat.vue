<template>
  <div class="h-screen flex bg-gray-50">
    <!-- 左侧会话列表 -->
    <div class="w-64 bg-gray-900 text-white flex flex-col">
      <!-- New Chat 按钮 -->
      <div class="p-4 border-b border-gray-700">
        <button
          @click="createNewChat"
          :disabled="loading"
          class="w-full py-2.5 px-4 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          <span class="font-medium">New Chat</span>
        </button>
      </div>

      <!-- 会话列表 -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="loadingConversations" class="p-4 text-center text-gray-400">
          Loading conversations...
        </div>
        <div v-else-if="conversations.length === 0" class="p-4 text-center text-gray-400">
          No conversations yet
        </div>
        <div v-else class="py-2">
          <button
            v-for="conv in conversations"
            :key="conv.conversation_id"
            @click="selectConversation(conv.conversation_id)"
            :class="[
              'w-full px-4 py-3 text-left hover:bg-gray-800 transition-colors border-l-4',
              currentConversationId === conv.conversation_id
                ? 'bg-gray-800 border-blue-500'
                : 'border-transparent'
            ]"
          >
            <div class="font-medium truncate">{{ conv.title || 'New Conversation' }}</div>
            <div class="text-xs text-gray-400 mt-1">
              {{ formatDate(conv.updated_at) }}
            </div>
          </button>
        </div>
      </div>

      <!-- 用户信息/登出 -->
      <div class="p-4 border-t border-gray-700">
        <div class="text-sm text-gray-400 truncate">
          {{ userEmail || 'Not logged in' }}
        </div>
      </div>
    </div>

    <!-- 右侧聊天区 -->
    <div class="flex-1 flex flex-col bg-white">
      <!-- 顶部标题栏 - 简化版 -->
      <div class="bg-white border-b border-gray-100 px-6 py-3">
        <div class="max-w-3xl mx-auto">
          <h1 class="text-lg font-semibold text-gray-800">
            {{ currentConversationTitle || 'Select or create a conversation' }}
          </h1>
        </div>
      </div>

      <!-- 消息列表 -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto">
        <!-- 未选择会话提示 -->
        <div v-if="!currentConversationId" class="h-full flex items-center justify-center bg-white">
          <div class="text-center text-gray-400 px-6">
            <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p class="text-lg font-medium text-gray-600">How can I help you today?</p>
            <p class="text-sm mt-2">Select a conversation or create a new one</p>
          </div>
        </div>

        <!-- ChatGPT 风格消息列表 -->
        <div v-else>
          <div v-if="loadingMessages" class="text-center text-gray-400 py-8">
            Loading messages...
          </div>
          
          <!-- 用户和助手消息 -->
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            :class="[
              'w-full',
              msg.role === 'user' ? 'bg-white' : 'bg-gray-50/50'
            ]"
          >
            <div class="max-w-3xl mx-auto px-6 py-6">
              <div class="flex gap-6">
                <!-- 头像 -->
                <div class="flex-shrink-0">
                  <div
                    :class="[
                      'w-8 h-8 rounded-sm flex items-center justify-center text-white font-semibold text-sm',
                      msg.role === 'user' ? 'bg-blue-500' : 'bg-green-600'
                    ]"
                  >
                    {{ msg.role === 'user' ? 'U' : 'AI' }}
                  </div>
                </div>
                <!-- 消息内容 -->
                <div class="flex-1 pt-1">
                  <div class="whitespace-pre-wrap break-words text-gray-800 leading-7">
                    {{ msg.content }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 流式消息（助手正在输出） -->
          <div v-if="streamingMessage" class="w-full bg-gray-50/50">
            <div class="max-w-3xl mx-auto px-6 py-6">
              <div class="flex gap-6">
                <!-- 头像 -->
                <div class="flex-shrink-0">
                  <div class="w-8 h-8 rounded-sm flex items-center justify-center bg-green-600 text-white font-semibold text-sm">
                    AI
                  </div>
                </div>
                <!-- 消息内容 -->
                <div class="flex-1 pt-1">
                  <div class="whitespace-pre-wrap break-words text-gray-800 leading-7">
                    {{ streamingMessage }}
                    <span class="inline-block w-1.5 h-5 bg-gray-800 animate-pulse ml-0.5"></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 自动滚动提示按钮 -->
      <div v-if="showScrollToBottom" class="px-6 pb-2 flex justify-center">
        <button
          @click="scrollToBottom(true)"
          class="px-4 py-2 bg-white border border-gray-300 rounded-full shadow-lg hover:bg-gray-50 transition-colors flex items-center gap-2"
        >
          <span class="text-sm">Jump to latest</span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      </div>

      <!-- 输入框 - ChatGPT 风格 -->
      <div class="bg-white pt-6 pb-4 border-t border-gray-100">
        <div class="max-w-3xl mx-auto px-6">
          <div v-if="error" class="mb-3 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-start gap-2">
            <svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            <span>{{ error }}</span>
          </div>

          <div class="relative flex items-center bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition-shadow">
            <input
              v-model="inputMessage"
              @keydown.enter.exact.prevent="handleSendMessage"
              :disabled="sending || !currentConversationId"
              placeholder="Send a message..."
              class="flex-1 px-4 py-3.5 bg-transparent focus:outline-none disabled:cursor-not-allowed text-gray-800"
            />
            <button
              @click="handleSendMessage"
              :disabled="sending || !inputMessage.trim() || !currentConversationId"
              class="mr-2 p-2 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 transition-colors"
              :class="inputMessage.trim() && !sending ? 'text-blue-500' : 'text-gray-400'"
            >
              <svg v-if="!sending" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
              <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </button>
          </div>
          
          <div class="text-center text-xs text-gray-500 mt-2">
            Press Enter to send, Shift+Enter for new line
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRuntimeConfig, useRouter } from 'nuxt/app'
import { useAuthStore } from '../stores/auth'
import { useApiFetch } from '../composables/useApiFetch'

// ========== Types ==========
interface Conversation {
  conversation_id: string
  title: string
  created_at: string
  updated_at: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

// ========== Reactive State ==========
const config = useRuntimeConfig()
const apiBase = config.public.apiBase || 'http://localhost:8000'
const router = useRouter()
const authStore = useAuthStore()
const apiFetch = useApiFetch()

const conversations = ref<Conversation[]>([])
const currentConversationId = ref<string | null>(null)
const messages = ref<Message[]>([])
const inputMessage = ref('')
const streamingMessage = ref('')

const loading = ref(false)
const loadingConversations = ref(false)
const loadingMessages = ref(false)
const sending = ref(false)
const error = ref('')

const messagesContainer = ref<HTMLElement | null>(null)
const showScrollToBottom = ref(false)
const userScrolling = ref(false)

const userEmail = computed(() => authStore.user?.email || null)

// ========== Computed ==========
const currentConversationTitle = computed(() => {
  if (!currentConversationId.value) return ''
  const conv = conversations.value.find(c => c.conversation_id === currentConversationId.value)
  return conv?.title || 'New Conversation'
})

// ========== Auth Helper ==========
function getAuthHeaders(): HeadersInit {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }
  
  // 优先使用 Authorization Bearer Token
  if (authStore.accessToken) {
    headers['Authorization'] = `Bearer ${authStore.accessToken}`
  }
  
  return headers
}

// ========== API Calls ==========
async function fetchConversations() {
  loadingConversations.value = true
  error.value = ''
  try {
    const response = await apiFetch<Conversation[]>('/conversations', {
      method: 'GET',
      headers: getAuthHeaders(),
    })
    conversations.value = response.sort((a, b) => 
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
  } catch (e: any) {
    error.value = e?.data?.detail || e?.message || 'Failed to load conversations'
    console.error('Error fetching conversations:', e)
  } finally {
    loadingConversations.value = false
  }
}

async function createNewChat() {
  loading.value = true
  error.value = ''
  try {
    const response = await apiFetch<Conversation>('/conversations', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: { title: null },
    })
    
    conversations.value.unshift(response)
    currentConversationId.value = response.conversation_id
    messages.value = []
    inputMessage.value = ''
    
    await nextTick()
    scrollToBottom(true)
  } catch (e: any) {
    error.value = e?.data?.detail || e?.message || 'Failed to create conversation'
    console.error('Error creating conversation:', e)
  } finally {
    loading.value = false
  }
}

async function selectConversation(conversationId: string) {
  if (currentConversationId.value === conversationId) return
  
  currentConversationId.value = conversationId
  messages.value = []
  streamingMessage.value = ''
  error.value = ''
  
  await loadMessages(conversationId)
  await nextTick()
  scrollToBottom(true)
}

async function loadMessages(conversationId: string) {
  loadingMessages.value = true
  try {
    const response = await apiFetch<{ messages: Message[] }>(
      `/conversations/${conversationId}/messages`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      }
    )
    messages.value = response.messages || []
  } catch (e: any) {
    error.value = e?.data?.detail || e?.message || 'Failed to load messages'
    console.error('Error loading messages:', e)
  } finally {
    loadingMessages.value = false
  }
}

async function handleSendMessage() {
  if (!inputMessage.value.trim() || !currentConversationId.value || sending.value) return
  
  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  error.value = ''
  sending.value = true
  
  // 添加用户消息到界面
  messages.value.push({
    role: 'user',
    content: userMessage,
  })
  
  await nextTick()
  scrollToBottom(true)
  
  // 开始 SSE 流式请求
  streamingMessage.value = ''
  
  try {
    const headers = getAuthHeaders()
    
    const response = await fetch(
      `${apiBase}/conversations/${currentConversationId.value}/chat`,
      {
        method: 'POST',
        headers: headers,
        credentials: 'include',
        body: JSON.stringify({
          content: userMessage,
          stream: true,
          max_length: 2,
          top_k_chunks: 5,
          max_hops: 2,
          history_len: 20,
        }),
      }
    )
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }
    
    if (!response.body) {
      throw new Error('Response body is null')
    }
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''
    
    console.log('[SSE] Starting to read stream...')
    
    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        console.log('[SSE] Stream done')
        break
      }
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) {
          // 空行表示事件结束，重置 currentEvent
          currentEvent = ''
          continue
        }
        
        console.log('[SSE] Received line:', line)
        
        // 解析 event: 行
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
          console.log('[SSE] Event type:', currentEvent)
          continue
        }
        
        // 解析 data: 行
        if (!line.startsWith('data: ')) continue
        
        const data = line.slice(6).trim()
        console.log('[SSE] Data:', data)
        
        if (data === '[DONE]') {
          console.log('[SSE] Received [DONE]')
          // 流式结束，将 streamingMessage 添加到 messages
          if (streamingMessage.value) {
            messages.value.push({
              role: 'assistant',
              content: streamingMessage.value,
            })
          }
          streamingMessage.value = ''
          
          // 刷新会话列表（更新 updated_at）
          await fetchConversations()
          continue
        }
        
        try {
          const parsed = JSON.parse(data)
          console.log('[SSE] Event:', currentEvent, 'Parsed:', parsed)
          
          // 根据 event 类型处理数据
          if (currentEvent === 'token' && parsed.delta) {
            streamingMessage.value += parsed.delta
            console.log('[SSE] Streaming message:', streamingMessage.value)
            
            // 如果用户没有手动滚动，自动滚动到底部
            if (!userScrolling.value) {
              await nextTick()
              scrollToBottom(false)
            }
          } else if (currentEvent === 'done') {
            console.log('[SSE] Received done event')
            if (streamingMessage.value) {
              messages.value.push({
                role: 'assistant',
                content: streamingMessage.value,
              })
            }
            streamingMessage.value = ''
            await fetchConversations()
          } else if (currentEvent === 'error') {
            console.error('[SSE] Error event:', parsed)
            error.value = parsed.message || 'An error occurred'
            streamingMessage.value = ''
          } else if (currentEvent === 'meta') {
            console.log('[SSE] Meta event (ignored):', parsed)
          }
        } catch (e) {
          console.warn('[SSE] Failed to parse data:', data, e)
        }
      }
    }
    
    console.log('[SSE] Finished reading stream')
  } catch (e: any) {
    error.value = e?.message || 'Failed to send message'
    console.error('Error sending message:', e)
    streamingMessage.value = ''
  } finally {
    sending.value = false
  }
}

// ========== Scroll Management ==========
function scrollToBottom(force: boolean) {
  if (!messagesContainer.value) return
  
  if (force) {
    userScrolling.value = false
  }
  
  messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  showScrollToBottom.value = false
}

function handleScroll() {
  if (!messagesContainer.value) return
  
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  const isAtBottom = scrollHeight - scrollTop - clientHeight < 100
  
  if (isAtBottom) {
    userScrolling.value = false
    showScrollToBottom.value = false
  } else {
    userScrolling.value = true
    showScrollToBottom.value = true
  }
}

// ========== Utility ==========
function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString()
}

// ========== Lifecycle ==========
onMounted(async () => {
  // 监听滚动
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', handleScroll)
  }
  
  console.log('[Chat] Before ensureMe, user:', authStore.user, 'fetched:', authStore.fetched)
  
  // 确保用户状态已加载
  await authStore.ensureMe()
  
  // 等待一个 tick 确保状态已更新
  await nextTick()
  
  console.log('[Chat] After ensureMe, user:', authStore.user, 'fetched:', authStore.fetched)
  
  // 检查登录状态
  if (!authStore.user) {
    console.log('[Chat] No user found, showing error')
    error.value = 'Not logged in. Please login first.'
    setTimeout(() => {
      router.push('/auth/login')
    }, 2000)
    return
  }
  
  // 已登录，清除错误并加载会话列表
  console.log('[Chat] User logged in:', authStore.user.email)
  error.value = ''
  await fetchConversations()
  
  // 如果有会话，自动选择第一个
  if (conversations.value.length > 0 && conversations.value[0]) {
    await selectConversation(conversations.value[0].conversation_id)
  }
})

// 监听 currentConversationId 变化时重置滚动状态
watch(currentConversationId, () => {
  userScrolling.value = false
  showScrollToBottom.value = false
})
</script>

<style scoped>
/* 自定义滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 动画 */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.animate-pulse {
  animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
</style>

