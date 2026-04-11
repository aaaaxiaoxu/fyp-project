<template>
  <v-app>
    <div class="main-view">
      <header class="app-header">
        <div class="header-left">
          <div class="brand" @click="goToGraph">SOCIOGRAPH</div>
          <div class="header-nav">
            <button class="header-btn subtle" @click="goToGraph">Back To Graph</button>
            <button class="header-btn subtle" @click="goToSimulation">Back To Simulation</button>
          </div>
        </div>

        <div class="header-center">
          <div class="workflow-step">
            <span class="step-num">Step 4/5</span>
            <span class="step-name">Explorer Agent</span>
          </div>
        </div>

        <div class="header-right">
          <button class="header-btn subtle" :disabled="pageLoading || !selectedSimulationId" @click="refreshExplorerState">
            {{ pageLoading ? 'Refreshing...' : 'Refresh Context' }}
          </button>
          <div class="step-divider"></div>
          <span class="status-indicator" :class="statusClass">
            <span class="dot"></span>
            {{ statusText }}
          </span>
        </div>
      </header>

      <div v-if="pageError" class="page-error-banner">
        {{ pageError }}
      </div>

      <main class="explorer-layout">
        <section class="context-panel">
          <div class="panel-header">
            <div class="panel-title-group">
              <span class="panel-title">WORLD CONTEXT</span>
              <span class="panel-subtitle">{{ selectedProject?.name || 'Restore a simulation to begin' }}</span>
            </div>
            <span v-if="selectedSimulationId" class="badge accent mono">{{ shortenId(selectedSimulationId) }}</span>
          </div>

          <div class="context-body">
            <div class="restore-card">
              <span class="section-kicker">Route Recovery</span>
              <p>
                Opened from <span class="mono">/simulation</span> with query state, or restored from the last local workspace.
              </p>
              <form class="restore-form" @submit.prevent="restoreSimulationFromInput">
                <input v-model="restoreSimulationId" class="restore-input" type="text" placeholder="sim_..." />
                <button class="mini-btn" :disabled="pageLoading || !restoreSimulationId.trim()">Restore</button>
              </form>
            </div>

            <div class="metric-grid">
              <div class="metric-card">
                <span class="metric-value">{{ profiles.length }}</span>
                <span class="metric-label">Agents</span>
              </div>
              <div class="metric-card">
                <span class="metric-value">{{ historyTurnCount }}</span>
                <span class="metric-label">Turns</span>
              </div>
              <div class="metric-card">
                <span class="metric-value">{{ totalActionCount }}</span>
                <span class="metric-label">Actions</span>
              </div>
              <div class="metric-card">
                <span class="metric-value">{{ runtimeStatus?.current_round ?? 0 }}</span>
                <span class="metric-label">Round</span>
              </div>
            </div>

            <div class="status-card">
              <div class="status-row">
                <span>Simulation</span>
                <strong class="mono">{{ selectedSimulationId || 'not selected' }}</strong>
              </div>
              <div class="status-row">
                <span>Runtime</span>
                <strong>{{ runtimeMeta(runtimeStatus?.status || 'created').label }}</strong>
              </div>
              <div class="status-row">
                <span>Interactive</span>
                <strong>{{ runtimeStatus?.interactive_ready ? 'Ready for interview' : 'Ask only' }}</strong>
              </div>
              <div class="status-row">
                <span>Graph</span>
                <strong class="mono">{{ selectedProject?.zep_graph_id ? shortenId(selectedProject.zep_graph_id) : 'pending' }}</strong>
              </div>
            </div>

            <div v-if="projects.length" class="project-stack">
              <div class="stack-head">
                <span class="section-kicker">Projects</span>
                <span>{{ projects.length }}</span>
              </div>
              <button
                v-for="project in projects.slice(0, 8)"
                :key="project.id"
                class="project-row"
                :class="{ active: project.id === selectedProjectId }"
                @click="selectProject(project.id)"
              >
                <span>{{ project.name }}</span>
                <small>{{ statusMeta(project.status).label }}</small>
              </button>
            </div>

            <div class="agent-stack">
              <div class="stack-head">
                <span class="section-kicker">Interview Agents</span>
                <span>{{ filteredProfiles.length }} / {{ profiles.length }}</span>
              </div>
              <div v-if="profilesError" class="inline-note danger">
                {{ profilesError }}
              </div>
              <input
                v-model.trim="agentSearch"
                type="search"
                class="agent-search"
                placeholder="Search name, @username, role, topic, type"
              />
              <div class="agent-list">
                <button
                  v-for="profile in filteredProfiles"
                  :key="profile.user_id"
                  class="agent-row"
                  :class="{ active: profile.user_id === selectedAgentId }"
                  @click="selectAgent(profile.user_id)"
                >
                  <span class="agent-avatar mono">{{ profile.user_id }}</span>
                  <span class="agent-copy">
                    <strong>{{ profile.name || profile.username || `Agent ${profile.user_id}` }}</strong>
                    <small>{{ profile.source_entity_type || profile.profession || 'simulation persona' }}</small>
                  </span>
                </button>
              </div>
              <div v-if="agentSearch && !filteredProfiles.length" class="inline-note">
                No agents match "{{ agentSearch }}".
              </div>
            </div>
          </div>
        </section>

        <section class="conversation-panel">
          <div class="interaction-header">
            <div>
              <span class="panel-title">EXPLORER DIALOG</span>
              <p>
                Ask graph-grounded questions or interview an OASIS agent once the runtime is interactive.
              </p>
            </div>
            <div class="session-pill mono">
              {{ activeSessionId || 'new session' }}
            </div>
          </div>

          <div class="mode-bar">
            <button
              v-for="option in modeOptions"
              :key="option.value"
              class="mode-tab"
              :class="{ active: mode === option.value }"
              @click="mode = option.value"
            >
              {{ option.label }}
            </button>
            <select v-model.number="selectedAgentId" class="agent-select" :disabled="mode !== 'interview' || !profiles.length">
              <option :value="null">Select agent</option>
              <option v-for="profile in profiles" :key="profile.user_id" :value="profile.user_id">
                Agent {{ profile.user_id }} - {{ profile.name || profile.username }}
              </option>
            </select>
          </div>

          <div class="tool-strip" aria-label="Explorer tools">
            <span v-for="tool in toolCards" :key="tool.name" class="tool-chip">
              <span>{{ tool.name }}</span>
              <small>{{ tool.description }}</small>
            </span>
          </div>

          <div v-if="streamError" class="inline-error">
            {{ streamError }}
          </div>

          <div ref="transcriptRef" class="transcript" aria-live="polite">
            <div v-if="!messages.length" class="empty-dialog">
              <span class="empty-label">Explorer Ready</span>
              <h2>Query the simulation world.</h2>
              <p>
                Start with a broad graph question, then switch to interview mode to ask a specific agent about their persona and recent actions.
              </p>
            </div>

            <article v-for="message in messages" :key="message.id" class="message-card" :class="message.role">
              <div class="message-meta">
                <span>{{ message.role === 'user' ? 'Operator' : 'Explorer Agent' }}</span>
                <span>{{ formatTime(message.createdAt) }}</span>
              </div>
              <p v-if="message.role === 'user'" class="message-content">
                {{ message.content || (message.status === 'streaming' ? 'Streaming response...' : '') }}
              </p>
              <div v-else-if="message.answerSections" class="message-content sectioned-answer">
                <section
                  v-for="section in answerSectionOrder"
                  :key="section.key"
                  class="answer-section"
                >
                  <h3>{{ section.label }}</h3>
                  <ul v-if="message.answerSections[section.key].length">
                    <li v-for="item in message.answerSections[section.key]" :key="`${section.key}:${item}`">
                      {{ item }}
                    </li>
                  </ul>
                  <p v-else>No evidence returned.</p>
                </section>
              </div>
              <div
                v-else
                class="message-content markdown-body"
                v-html="renderAssistantContent(message.content || (message.status === 'streaming' ? 'Streaming response...' : ''))"
              ></div>

              <div v-if="message.events.length" class="event-timeline">
                <div v-for="event in message.events" :key="event.key" class="event-chip" :class="event.event">
                  <span>{{ eventLabel(event.event) }}</span>
                  <small>{{ eventSummary(event) }}</small>
                </div>
              </div>
            </article>
          </div>

          <form class="composer" @submit.prevent="submitExplorerMessage">
            <textarea
              v-model="question"
              :placeholder="composerPlaceholder"
              :disabled="streaming || !selectedSimulationId"
              rows="3"
              @keydown.meta.enter.prevent="submitExplorerMessage"
              @keydown.ctrl.enter.prevent="submitExplorerMessage"
            ></textarea>
            <div class="composer-footer">
              <span class="composer-hint">
                {{ composerHint }}
              </span>
              <button class="send-btn" :disabled="!canSend">
                <span v-if="streaming" class="spinner-sm"></span>
                {{ streaming ? 'Streaming...' : submitLabel }}
              </button>
            </div>
          </form>
        </section>

        <aside class="history-panel">
          <div class="panel-header compact">
            <div class="panel-title-group">
              <span class="panel-title">SESSION HISTORY</span>
              <span class="panel-subtitle">{{ historySessions.length }} sessions</span>
            </div>
            <button class="mini-btn" :disabled="historyLoading || !selectedSimulationId" @click="loadHistory">
              {{ historyLoading ? 'Syncing' : 'Sync' }}
            </button>
          </div>

          <div class="history-body">
            <button class="new-session-btn" :disabled="streaming || !selectedSimulationId" @click="startNewSession">
              New Explorer Session
            </button>

            <div v-if="historyError" class="inline-note danger">
              {{ historyError }}
            </div>

            <button
              v-for="session in historySessions"
              :key="session.session_id"
              class="history-row"
              :class="{ active: session.session_id === activeSessionId }"
              @click="selectHistorySession(session)"
            >
              <span>{{ session.title || session.session_id }}</span>
              <small>{{ session.turns.length }} turns - {{ formatDate(session.updated_at) }}</small>
            </button>

            <div v-if="selectedHistorySession" class="session-detail">
              <span class="section-kicker">Selected Log</span>
              <p class="mono">{{ selectedHistorySession.log_path || 'log pending' }}</p>
              <div class="turn-list">
                <div v-for="turn in selectedHistorySession.turns" :key="turn.turn_id" class="turn-row">
                  <span>{{ turn.mode }}</span>
                  <p>{{ turn.question }}</p>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </main>
    </div>
  </v-app>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useHead, useRuntimeConfig } from 'nuxt/app'
import { useRoute, useRouter } from 'vue-router'
import { getApiErrorMessage, useApiFetch } from '~/composables/useApiFetch'
import { createExplorerSessionId, parseSseBuffer, type ExplorerSseEvent } from '~/utils/explorerSse'
import { buildGraphRouteQuery, buildSimulationRouteQuery } from '~/utils/workspaceRoutes'

type ProjectStatus = 'created' | 'ontology_generated' | 'graph_building' | 'graph_completed' | 'failed'
type RuntimeStatus = 'created' | 'preparing' | 'ready' | 'running' | 'completed' | 'stopped' | 'failed'
type ExplorerMode = 'ask' | 'interview'

type ProjectRecord = {
  id: string
  name: string
  status: ProjectStatus
  zep_graph_id: string | null
  simulation_requirement: string
  ontology_path: string | null
  extracted_text_path: string | null
  created_at: string
  updated_at: string
}

type ProjectListResponse = {
  projects: ProjectRecord[]
}

type SimulationProfile = {
  user_id: number
  username?: string
  name?: string
  bio?: string
  persona?: string
  profession?: string | null
  interested_topics?: string[]
  source_entity_uuid?: string | null
  source_entity_type?: string | null
}

type SimulationProfilesResponse = {
  simulation_id: string
  count: number
  profiles: SimulationProfile[]
}

type SimulationStatusResponse = {
  simulation_id: string
  project_id: string
  status: RuntimeStatus
  total_rounds: number | null
  current_round: number
  twitter_enabled: boolean
  reddit_enabled: boolean
  twitter_actions_count: number
  reddit_actions_count: number
  recent_actions: Record<string, unknown>[]
  interactive_ready: boolean
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

type ExplorerTurn = {
  turn_id: string
  session_id: string
  simulation_id: string
  mode: ExplorerMode | string
  question: string
  answer: string
  answer_sections?: AnswerSections | null
  agent_id: number | null
  tool_name: string
  created_at: string
}

type ExplorerHistorySession = {
  session_id: string
  simulation_id: string
  title: string
  status: string
  log_path: string | null
  created_at: string
  updated_at: string
  turns: ExplorerTurn[]
}

type ExplorerHistoryResponse = {
  simulation_id: string
  count: number
  sessions: ExplorerHistorySession[]
}

type PersistedWorkspaceState = {
  selectedProjectId: string | null
  prepareTaskIds: Record<string, string>
  simulationIds: Record<string, string>
}

type ChatEvent = ExplorerSseEvent & {
  key: string
}

type AnswerSectionKey = 'confirmed' | 'inference' | 'uncertainty'

type AnswerSections = Record<AnswerSectionKey, string[]>

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  answerSections: AnswerSections | null
  createdAt: string
  status: 'done' | 'streaming' | 'error'
  events: ChatEvent[]
}

const STORAGE_KEY = 'fyp.simulation.workspace.v1'

const apiFetch = useApiFetch()
const config = useRuntimeConfig()
const route = useRoute()
const router = useRouter()

useHead({
  title: 'Explorer Agent Workspace',
})

const projects = ref<ProjectRecord[]>([])
const selectedProjectId = ref<string | null>(null)
const selectedSimulationId = ref<string | null>(null)
const restoreSimulationId = ref('')
const runtimeStatus = ref<SimulationStatusResponse | null>(null)
const profiles = ref<SimulationProfile[]>([])
const historySessions = ref<ExplorerHistorySession[]>([])
const activeSessionId = ref<string | null>(null)
const selectedAgentId = ref<number | null>(null)
const mode = ref<ExplorerMode>('ask')
const question = ref('What are the most important relationships in this simulation?')
const messages = ref<ChatMessage[]>([])

const pageLoading = ref(false)
const historyLoading = ref(false)
const streaming = ref(false)
const pageError = ref('')
const profilesError = ref('')
const historyError = ref('')
const streamError = ref('')
const transcriptRef = ref<HTMLDivElement | null>(null)

let streamAbortController: AbortController | null = null

const modeOptions: Array<{ label: string; value: ExplorerMode }> = [
  { label: 'Ask Explorer', value: 'ask' },
  { label: 'Interview Agent', value: 'interview' },
]

const toolCards = [
  { name: 'quick_search', description: 'targeted graph facts' },
  { name: 'panorama_search', description: 'broad active and historical view' },
  { name: 'insight_forge', description: 'impact and cause analysis' },
  { name: 'interview_agents', description: 'persona-grounded agent answer' },
]

const answerSectionOrder: Array<{ key: AnswerSectionKey; label: string }> = [
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'inference', label: 'Inference' },
  { key: 'uncertainty', label: 'Uncertainty' },
]

const selectedProject = computed(() => {
  return projects.value.find((project) => project.id === selectedProjectId.value) || null
})

const selectedAgent = computed(() => {
  return profiles.value.find((profile) => profile.user_id === selectedAgentId.value) || null
})

const agentSearch = ref('')

const filteredProfiles = computed(() => {
  const query = agentSearch.value.trim().toLowerCase()
  if (!query) {
    return profiles.value
  }

  return profiles.value.filter((profile) => {
    const haystack = [
      String(profile.user_id),
      profile.name,
      profile.username,
      profile.profession,
      profile.source_entity_type,
      profile.bio,
      profile.persona,
      ...(profile.interested_topics || []),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()

    return haystack.includes(query)
  })
})

const selectedHistorySession = computed(() => {
  return historySessions.value.find((session) => session.session_id === activeSessionId.value) || null
})

const historyTurnCount = computed(() => {
  return historySessions.value.reduce((count, session) => count + session.turns.length, 0)
})

const totalActionCount = computed(() => {
  return (runtimeStatus.value?.twitter_actions_count || 0) + (runtimeStatus.value?.reddit_actions_count || 0)
})

const statusClass = computed(() => {
  if (pageError.value || streamError.value) {
    return 'error'
  }
  if (streaming.value) {
    return 'processing'
  }
  if (runtimeStatus.value?.interactive_ready) {
    return 'completed'
  }
  if (selectedSimulationId.value) {
    return 'idle'
  }
  return 'idle'
})

const statusText = computed(() => {
  if (pageError.value || streamError.value) {
    return 'Error'
  }
  if (streaming.value) {
    return 'Streaming'
  }
  if (runtimeStatus.value?.interactive_ready) {
    return 'Explorer Ready'
  }
  if (selectedSimulationId.value) {
    return 'Ask Ready'
  }
  return 'Idle'
})

const composerPlaceholder = computed(() => {
  if (mode.value === 'interview') {
    return selectedAgent.value
      ? `Ask Agent ${selectedAgent.value.user_id} about their observations...`
      : 'Select an agent before interviewing.'
  }
  return 'Ask about relationships, causes, outcomes, or broad graph context.'
})

const composerHint = computed(() => {
  if (!selectedSimulationId.value) {
    return 'Restore a simulation id first.'
  }
  if (mode.value === 'interview' && !runtimeStatus.value?.interactive_ready) {
    return 'Interview requires interactive_ready=true. Ask mode can still inspect the graph.'
  }
  return 'Cmd/Ctrl + Enter sends. Responses stream as SSE events.'
})

const submitLabel = computed(() => {
  return mode.value === 'interview' ? 'Interview Agent' : 'Ask Explorer'
})

const canSend = computed(() => {
  if (streaming.value || !selectedSimulationId.value || !question.value.trim()) {
    return false
  }
  if (mode.value === 'interview') {
    return Boolean(selectedAgentId.value && runtimeStatus.value?.interactive_ready)
  }
  return true
})

onMounted(async () => {
  await initializeExplorer()
})

onBeforeUnmount(() => {
  streamAbortController?.abort()
})

async function initializeExplorer() {
  pageLoading.value = true
  pageError.value = ''
  try {
    const workspace = readWorkspaceState()
    await loadProjects()

    const routeProjectId = typeof route.query.project === 'string' ? route.query.project : null
    const routeSimulationId = typeof route.query.simulation === 'string' ? route.query.simulation : null
    const routeSessionId = typeof route.query.session === 'string' ? route.query.session : null

    selectedProjectId.value = resolveProjectId(routeProjectId, workspace)
    activeSessionId.value = routeSessionId

    const simulationId =
      routeSimulationId ||
      (selectedProjectId.value ? workspace.simulationIds[selectedProjectId.value] : null) ||
      resolveFirstPersistedSimulation(workspace)

    if (simulationId) {
      await selectSimulation(simulationId, { preserveMessages: false })
    } else {
      syncExplorerQuery()
    }
  } catch (error) {
    pageError.value = normalizeApiError(error)
  } finally {
    pageLoading.value = false
  }
}

async function refreshExplorerState() {
  if (!selectedSimulationId.value) {
    pageError.value = 'No simulation is selected.'
    return
  }
  pageLoading.value = true
  pageError.value = ''
  try {
    await loadSimulationContext(selectedSimulationId.value)
  } catch (error) {
    pageError.value = normalizeApiError(error)
  } finally {
    pageLoading.value = false
  }
}

async function loadProjects() {
  const response = await apiFetch<ProjectListResponse>('/api/graph/projects', { method: 'GET' })
  projects.value = response.projects
}

async function loadSimulationContext(simulationId: string) {
  await loadRuntimeStatus(simulationId)
  await Promise.all([loadProfiles(simulationId), loadHistory()])
}

async function loadRuntimeStatus(simulationId: string) {
  const response = await apiFetch<SimulationStatusResponse>(`/api/simulation/status/${simulationId}?recent_limit=20`, {
    method: 'GET',
  })
  runtimeStatus.value = response
  selectedProjectId.value = response.project_id
  selectedSimulationId.value = response.simulation_id
  restoreSimulationId.value = response.simulation_id
  persistSimulation(response.project_id, response.simulation_id)
  syncExplorerQuery()
}

async function loadProfiles(simulationId: string) {
  profilesError.value = ''
  try {
    const response = await apiFetch<SimulationProfilesResponse>(`/api/simulation/${simulationId}/profiles`, { method: 'GET' })
    profiles.value = response.profiles
    if (!profiles.value.some((profile) => profile.user_id === selectedAgentId.value)) {
      selectedAgentId.value = profiles.value[0]?.user_id ?? null
    }
  } catch (error) {
    profiles.value = []
    profilesError.value = normalizeApiError(error)
  }
}

async function loadHistory() {
  if (!selectedSimulationId.value) {
    return
  }

  historyLoading.value = true
  historyError.value = ''
  try {
    const response = await apiFetch<ExplorerHistoryResponse>(`/api/explorer/history/${selectedSimulationId.value}`, {
      method: 'GET',
    })
    historySessions.value = response.sessions
    if (activeSessionId.value) {
      const session = historySessions.value.find((item) => item.session_id === activeSessionId.value)
      if (session && !streaming.value) {
        loadSessionMessages(session)
      }
    }
  } catch (error) {
    historyError.value = normalizeApiError(error)
  } finally {
    historyLoading.value = false
  }
}

async function selectSimulation(simulationId: string, options: { preserveMessages?: boolean } = {}) {
  const normalized = simulationId.trim()
  if (!normalized) {
    return
  }
  pageError.value = ''
  if (!options.preserveMessages) {
    messages.value = []
  }
  streamError.value = ''
  selectedSimulationId.value = normalized
  restoreSimulationId.value = normalized
  await loadSimulationContext(normalized)
}

async function selectProject(projectId: string) {
  pageError.value = ''
  selectedProjectId.value = projectId
  const workspace = readWorkspaceState()
  const simulationId = workspace.simulationIds[projectId]
  if (!simulationId) {
    selectedSimulationId.value = null
    runtimeStatus.value = null
    profiles.value = []
    historySessions.value = []
    messages.value = []
    pageError.value = 'This project has no saved simulation id yet. Prepare a simulation first or paste one above.'
    syncExplorerQuery()
    return
  }
  await selectSimulation(simulationId)
}

function selectAgent(agentId: number) {
  selectedAgentId.value = agentId
  mode.value = 'interview'
}

async function restoreSimulationFromInput() {
  await selectSimulation(restoreSimulationId.value)
}

function selectHistorySession(session: ExplorerHistorySession) {
  activeSessionId.value = session.session_id
  loadSessionMessages(session)
  syncExplorerQuery()
}

function startNewSession() {
  activeSessionId.value = null
  messages.value = []
  streamError.value = ''
  syncExplorerQuery()
}

function loadSessionMessages(session: ExplorerHistorySession) {
  messages.value = session.turns.flatMap((turn) => [
    {
      id: `${turn.turn_id}:question`,
      role: 'user' as const,
      content: turn.question,
      answerSections: null,
      createdAt: turn.created_at,
      status: 'done' as const,
      events: [],
    },
    {
      id: `${turn.turn_id}:answer`,
      role: 'assistant' as const,
      content: turn.answer,
      answerSections: normalizeAnswerSections(turn.answer_sections),
      createdAt: turn.created_at,
      status: 'done' as const,
      events: [
        {
          key: `${turn.turn_id}:tool`,
          event: 'tool_result',
          data: { tool_name: turn.tool_name, mode: turn.mode, agent_id: turn.agent_id },
        },
      ],
    },
  ])
  scrollTranscript()
}

async function submitExplorerMessage() {
  if (!canSend.value || !selectedSimulationId.value) {
    return
  }

  const text = question.value.trim()
  const sessionId = activeSessionId.value || createExplorerSessionId()
  activeSessionId.value = sessionId
  syncExplorerQuery()

  const userMessage: ChatMessage = {
    id: `user:${Date.now()}`,
    role: 'user',
    content: text,
    answerSections: null,
    createdAt: new Date().toISOString(),
    status: 'done',
    events: [],
  }
  const assistantMessage: ChatMessage = {
    id: `assistant:${Date.now()}`,
    role: 'assistant',
    content: '',
    answerSections: null,
    createdAt: new Date().toISOString(),
    status: 'streaming',
    events: [],
  }

  messages.value.push(userMessage, assistantMessage)
  question.value = ''
  streamError.value = ''
  streaming.value = true
  streamAbortController = new AbortController()
  scrollTranscript()

  try {
    await streamExplorerResponse({
      assistantMessageId: assistantMessage.id,
      sessionId,
      simulationId: selectedSimulationId.value,
      text,
    })
    assistantMessage.status = assistantMessage.status === 'streaming' ? 'done' : assistantMessage.status
    await loadHistory()
  } catch (error) {
    const message = normalizeApiError(error)
    assistantMessage.status = 'error'
    assistantMessage.content = assistantMessage.content || message
    streamError.value = message
  } finally {
    streaming.value = false
    streamAbortController = null
    scrollTranscript()
  }
}

async function streamExplorerResponse(args: {
  assistantMessageId: string
  sessionId: string
  simulationId: string
  text: string
}) {
  const endpoint =
    mode.value === 'interview' ? `/api/explorer/interview/${selectedAgentId.value}` : '/api/explorer/ask'
  const response = await fetch(apiUrl(endpoint), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      simulation_id: args.simulationId,
      question: args.text,
      session_id: args.sessionId,
    }),
    signal: streamAbortController?.signal,
  })

  if (!response.ok) {
    throw new Error(await readFetchError(response))
  }
  if (!response.body) {
    throw new Error('Explorer stream did not include a response body.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseSseBuffer(buffer)
    buffer = parsed.rest
    for (const event of parsed.events) {
      handleStreamEvent(args.assistantMessageId, event)
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    const parsed = parseSseBuffer(`${buffer}\n\n`)
    for (const event of parsed.events) {
      handleStreamEvent(args.assistantMessageId, event)
    }
  }
}

function handleStreamEvent(messageId: string, event: ExplorerSseEvent) {
  const message = messages.value.find((item) => item.id === messageId)
  if (!message) {
    return
  }

  const chatEvent: ChatEvent = {
    ...event,
    key: `${messageId}:${message.events.length}:${event.event}`,
  }
  message.events.push(chatEvent)

  if (event.event === 'answer_chunk') {
    message.content += stringField(event.data, 'chunk')
  } else if (event.event === 'final_answer') {
    message.content = stringField(event.data, 'answer') || message.content
    message.answerSections = normalizeAnswerSections(event.data.answer_sections)
    message.status = 'done'
  } else if (event.event === 'error') {
    message.status = 'error'
    message.content = stringField(event.data, 'message') || 'Explorer failed.'
    message.answerSections = null
    streamError.value = message.content
  }

  scrollTranscript()
}

function apiUrl(path: string) {
  const base = String(config.public.apiBase || '').replace(/\/$/, '')
  return `${base}${path}`
}

async function readFetchError(response: Response) {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const payload = await response.json().catch(() => null)
    if (payload && typeof payload === 'object' && 'detail' in payload) {
      return String(payload.detail)
    }
  }
  return (await response.text().catch(() => '')) || `Request failed with status ${response.status}`
}

function goToGraph() {
  void router.push({ path: '/graph', query: buildGraphRouteQuery(selectedProjectId.value) })
}

function goToSimulation() {
  void router.push({
    path: '/simulation',
    query: buildSimulationRouteQuery(selectedProjectId.value, selectedSimulationId.value),
  })
}

function syncExplorerQuery() {
  const nextQuery = { ...route.query }
  if (selectedProjectId.value) {
    nextQuery.project = selectedProjectId.value
  } else {
    delete nextQuery.project
  }
  if (selectedSimulationId.value) {
    nextQuery.simulation = selectedSimulationId.value
  } else {
    delete nextQuery.simulation
  }
  if (activeSessionId.value) {
    nextQuery.session = activeSessionId.value
  } else {
    delete nextQuery.session
  }
  void router.replace({ query: nextQuery })
}

function readWorkspaceState(): PersistedWorkspaceState {
  if (!import.meta.client) {
    return emptyWorkspaceState()
  }
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return emptyWorkspaceState()
  }
  try {
    const parsed = JSON.parse(raw) as PersistedWorkspaceState
    return {
      selectedProjectId: parsed.selectedProjectId || null,
      prepareTaskIds: parsed.prepareTaskIds || {},
      simulationIds: parsed.simulationIds || {},
    }
  } catch {
    window.localStorage.removeItem(STORAGE_KEY)
    return emptyWorkspaceState()
  }
}

function persistSimulation(projectId: string, simulationId: string) {
  if (!import.meta.client) {
    return
  }
  const workspace = readWorkspaceState()
  workspace.selectedProjectId = projectId
  workspace.simulationIds[projectId] = simulationId
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(workspace))
}

function emptyWorkspaceState(): PersistedWorkspaceState {
  return {
    selectedProjectId: null,
    prepareTaskIds: {},
    simulationIds: {},
  }
}

function resolveProjectId(routeProjectId: string | null, workspace: PersistedWorkspaceState) {
  const candidates = [routeProjectId, workspace.selectedProjectId]
  for (const candidate of candidates) {
    if (candidate && projects.value.some((project) => project.id === candidate)) {
      return candidate
    }
  }
  return projects.value[0]?.id || null
}

function resolveFirstPersistedSimulation(workspace: PersistedWorkspaceState) {
  const firstProjectId = selectedProjectId.value || workspace.selectedProjectId
  if (firstProjectId && workspace.simulationIds[firstProjectId]) {
    return workspace.simulationIds[firstProjectId]
  }
  return Object.values(workspace.simulationIds)[0] || null
}

function scrollTranscript() {
  void nextTick(() => {
    if (transcriptRef.value) {
      transcriptRef.value.scrollTop = transcriptRef.value.scrollHeight
    }
  })
}

function renderAssistantContent(content: string) {
  return renderMarkdown(content)
}

function renderMarkdown(content: string) {
  const normalized = content.replace(/\r\n/g, '\n').trim()
  if (!normalized) {
    return '<p></p>'
  }

  const codeBlocks: string[] = []
  const source = normalized.replace(/```(?:[\w-]+)?\n?([\s\S]*?)```/g, (_, code: string) => {
    codeBlocks.push(`<pre><code>${escapeHtml(code.trimEnd())}</code></pre>`)
    return `@@CODEBLOCK_${codeBlocks.length - 1}@@`
  })

  const lines = source.split('\n')
  const blocks: string[] = []
  let index = 0

  while (index < lines.length) {
    const trimmed = lines[index].trim()
    if (!trimmed) {
      index += 1
      continue
    }

    const codeMatch = trimmed.match(/^@@CODEBLOCK_(\d+)@@$/)
    if (codeMatch) {
      blocks.push(codeBlocks[Number(codeMatch[1])] || '')
      index += 1
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/)
    if (headingMatch) {
      const level = Math.min(headingMatch[1].length, 3)
      blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`)
      index += 1
      continue
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = []
      while (index < lines.length) {
        const match = lines[index].trim().match(/^[-*]\s+(.*)$/)
        if (!match) {
          break
        }
        items.push(`<li>${renderInlineMarkdown(match[1])}</li>`)
        index += 1
      }
      blocks.push(`<ul>${items.join('')}</ul>`)
      continue
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = []
      while (index < lines.length) {
        const match = lines[index].trim().match(/^\d+\.\s+(.*)$/)
        if (!match) {
          break
        }
        items.push(`<li>${renderInlineMarkdown(match[1])}</li>`)
        index += 1
      }
      blocks.push(`<ol>${items.join('')}</ol>`)
      continue
    }

    if (/^>\s?/.test(trimmed)) {
      const quoteLines: string[] = []
      while (index < lines.length) {
        const match = lines[index].trim().match(/^>\s?(.*)$/)
        if (!match) {
          break
        }
        quoteLines.push(renderInlineMarkdown(match[1]))
        index += 1
      }
      blocks.push(`<blockquote><p>${quoteLines.join('<br>')}</p></blockquote>`)
      continue
    }

    const paragraphLines: string[] = []
    while (index < lines.length) {
      const current = lines[index].trim()
      if (
        !current ||
        /^@@CODEBLOCK_\d+@@$/.test(current) ||
        /^(#{1,3})\s+/.test(current) ||
        /^[-*]\s+/.test(current) ||
        /^\d+\.\s+/.test(current) ||
        /^>\s?/.test(current)
      ) {
        break
      }
      paragraphLines.push(lines[index].trim())
      index += 1
    }
    blocks.push(`<p>${renderInlineMarkdown(paragraphLines.join(' '))}</p>`)
  }

  return blocks.join('')
}

function renderInlineMarkdown(content: string) {
  let escaped = escapeHtml(content)
  escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>')
  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  escaped = escaped.replace(/__([^_]+)__/g, '<strong>$1</strong>')
  escaped = escaped.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  escaped = escaped.replace(/_([^_\n]+)_/g, '<em>$1</em>')
  return escaped
}

function escapeHtml(content: string) {
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function normalizeApiError(error: unknown) {
  if (error instanceof Error) {
    return error.message
  }
  return getApiErrorMessage(error)
}

function statusMeta(status: ProjectStatus | string) {
  const meta: Record<string, { label: string; class: string }> = {
    created: { label: 'Created', class: 'badge pending' },
    ontology_generated: { label: 'Ontology Ready', class: 'badge success' },
    graph_building: { label: 'Building', class: 'badge processing' },
    graph_completed: { label: 'Graph Ready', class: 'badge accent' },
    failed: { label: 'Failed', class: 'badge danger' },
  }
  return meta[status] ?? { label: status, class: 'badge pending' }
}

function runtimeMeta(status: RuntimeStatus | string) {
  const meta: Record<string, { label: string; class: string }> = {
    created: { label: 'Not Prepared', class: 'badge pending' },
    preparing: { label: 'Preparing', class: 'badge processing' },
    ready: { label: 'Ready', class: 'badge accent' },
    running: { label: 'Running', class: 'badge processing' },
    completed: { label: 'Completed', class: 'badge success' },
    stopped: { label: 'Stopped', class: 'badge success' },
    failed: { label: 'Failed', class: 'badge danger' },
  }
  return meta[status] ?? { label: status, class: 'badge pending' }
}

function eventLabel(eventName: string) {
  const labels: Record<string, string> = {
    status: 'Status',
    tool_call: 'Tool Call',
    tool_result: 'Tool Result',
    answer_chunk: 'Chunk',
    final_answer: 'Final',
    error: 'Error',
  }
  return labels[eventName] || eventName
}

function eventSummary(event: ChatEvent) {
  if (event.event === 'tool_call') {
    return stringField(event.data, 'tool_name') || 'calling tool'
  }
  if (event.event === 'tool_result') {
    const result = event.data.result
    if (isRecord(result)) {
      const facts = Array.isArray(result.facts) ? result.facts.length : 0
      const activeFacts = Array.isArray(result.active_facts) ? result.active_facts.length : 0
      const historicalFacts = Array.isArray(result.historical_facts) ? result.historical_facts.length : 0
      return `${stringField(event.data, 'tool_name') || 'tool'} returned ${facts + activeFacts + historicalFacts} facts`
    }
    return stringField(event.data, 'tool_name') || 'stored result'
  }
  if (event.event === 'answer_chunk') {
    return `${stringField(event.data, 'chunk').length} chars`
  }
  if (event.event === 'final_answer') {
    return 'answer committed to session log'
  }
  if (event.event === 'error') {
    return stringField(event.data, 'message') || 'stream error'
  }
  return stringField(event.data, 'status') || 'event received'
}

function stringField(data: Record<string, unknown>, key: string) {
  const value = data[key]
  return typeof value === 'string' ? value : ''
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function normalizeAnswerSections(value: unknown): AnswerSections | null {
  if (!isRecord(value)) {
    return null
  }

  const readSection = (key: AnswerSectionKey) => {
    const raw = value[key]
    if (!Array.isArray(raw)) {
      return []
    }
    return raw.map((item) => String(item).trim()).filter(Boolean)
  }

  const sections: AnswerSections = {
    confirmed: readSection('confirmed'),
    inference: readSection('inference'),
    uncertainty: readSection('uncertainty'),
  }

  if (!sections.confirmed.length && !sections.inference.length && !sections.uncertainty.length) {
    return null
  }
  return sections
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('en-US', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function shortenId(value: string) {
  return value.length <= 16 ? value : `${value.slice(0, 8)}...${value.slice(-5)}`
}
</script>

<style scoped>
.main-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  color: #111;
  font-family: "Space Grotesk", "Noto Sans SC", system-ui, sans-serif;
}

.app-header {
  height: 60px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eaeaea;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 20;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  justify-content: flex-end;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: "JetBrains Mono", monospace;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 1px;
  cursor: pointer;
}

.header-btn,
.mini-btn,
.send-btn {
  border: 1px solid #111;
  background: #111;
  color: #fff;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: uppercase;
  transition: transform 0.18s ease, opacity 0.18s ease, background 0.18s ease;
}

.header-btn:hover:not(:disabled),
.mini-btn:hover:not(:disabled),
.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.header-btn:disabled,
.mini-btn:disabled,
.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.header-btn.subtle,
.mini-btn {
  background: #fff;
  color: #111;
  border-color: #dedede;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-num {
  font-family: "JetBrains Mono", monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #000;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #e0e0e0;
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #666;
  font-size: 12px;
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}

.status-indicator.processing .dot {
  background: #ff6f3d;
  animation: pulse 1s ease-in-out infinite;
}

.status-indicator.completed .dot {
  background: #43a047;
}

.status-indicator.error .dot {
  background: #d32f2f;
}

.page-error-banner,
.inline-error,
.inline-note.danger {
  margin: 0;
  border: 0;
  border-bottom: 1px solid #ffd9d6;
  background: #fff1f0;
  color: #c62828;
  border-radius: 0;
  padding: 10px 24px;
  font-size: 12px;
  font-weight: 600;
}

.inline-error {
  border: 1px solid #ffd9d6;
  border-radius: 8px;
}

.inline-note {
  color: #777;
  font-size: 0.8rem;
}

.inline-note.danger {
  margin: 0;
  padding: 10px 12px;
}

.explorer-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(520px, 1.65fr) minmax(260px, 0.75fr);
  gap: 0;
  flex: 1;
  min-height: calc(100vh - 60px);
  overflow: hidden;
}

.context-panel,
.conversation-panel,
.history-panel {
  background: #fff;
  border: 0;
  border-right: 1px solid #eaeaea;
  border-radius: 0;
  box-shadow: none;
  min-height: 0;
}

.history-panel {
  border-right: 0;
  border-left: 1px solid #eaeaea;
}

.context-panel,
.history-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.conversation-panel {
  display: grid;
  grid-template-rows: auto auto auto auto 1fr auto;
  overflow: hidden;
}

.panel-header,
.interaction-header {
  min-height: 62px;
  padding: 0 20px;
  border-bottom: 1px solid #eaeaea;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.panel-header.compact {
  align-items: center;
}

.panel-title-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.panel-title,
.section-kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.panel-subtitle,
.interaction-header p,
.restore-card p,
.tool-chip small,
.agent-copy small,
.history-row small {
  color: #888;
  font-size: 11px;
  line-height: 1.45;
}

.context-body,
.history-body {
  padding: 18px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.restore-card,
.status-card,
.project-stack,
.agent-stack,
.session-detail {
  border: 1px solid #eaeaea;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.restore-form {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.restore-input,
.agent-search,
.agent-select,
.composer textarea {
  width: 100%;
  border: 1px solid #dedede;
  border-radius: 8px;
  background: #fff;
  color: #111;
  outline: none;
}

.restore-input {
  padding: 10px 12px;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.78rem;
}

.agent-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric-card {
  border: 1px solid #ececec;
  border-radius: 8px;
  background: #fff;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-value {
  font-size: 1.7rem;
  font-weight: 900;
}

.metric-label,
.status-row span {
  color: #777;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: uppercase;
}

.status-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.stack-head {
  display: flex;
  justify-content: space-between;
  color: #777;
  font-size: 0.78rem;
  font-weight: 800;
}

.agent-search {
  padding: 10px 12px;
  font-size: 0.84rem;
}

.agent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: clamp(320px, 44vh, 760px);
  overflow: auto;
  padding-right: 4px;
}

.project-row,
.agent-row,
.history-row,
.new-session-btn {
  width: 100%;
  border: 1px solid #e6e6e6;
  border-radius: 8px;
  background: #fff;
  color: #111;
  text-align: left;
  padding: 12px;
  transition: border 0.18s ease, background 0.18s ease, transform 0.18s ease;
}

.project-row:hover,
.agent-row:hover,
.history-row:hover,
.new-session-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: #111;
}

.project-row.active,
.agent-row.active,
.history-row.active {
  background: #111;
  color: #fff;
}

.project-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.project-row small,
.history-row small {
  display: block;
  margin-top: 4px;
}

.agent-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-avatar {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: rgba(28, 28, 28, 0.08);
  font-weight: 900;
}

.agent-row.active .agent-avatar {
  background: rgba(255, 255, 255, 0.18);
}

.agent-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.interaction-header {
  align-items: center;
}

.session-pill,
.badge {
  border: 1px solid #dedede;
  border-radius: 8px;
  padding: 8px 12px;
  background: #fff;
  font-size: 11px;
  font-weight: 700;
}

.badge.accent {
  background: #111;
  border-color: #111;
  color: #fff;
}

.mode-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 22px;
  border-bottom: 1px solid #eaeaea;
}

.mode-tab {
  border: 1px solid #dedede;
  background: transparent;
  color: #111;
  border-radius: 8px;
  padding: 9px 14px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.mode-tab.active {
  background: #111;
  color: #fff;
  border-color: #111;
}

.agent-select {
  margin-left: auto;
  max-width: 260px;
  padding: 9px 12px;
  font-weight: 800;
}

.tool-strip {
  padding: 12px 22px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #eaeaea;
}

.tool-chip {
  border: 1px solid #ececec;
  background: #fff;
  border-radius: 8px;
  padding: 8px 10px;
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  max-width: 100%;
}

.tool-chip span {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.76rem;
  font-weight: 900;
  white-space: nowrap;
}

.tool-chip small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.transcript {
  overflow: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty-dialog {
  min-height: 320px;
  border: 1px dashed #d8d8d8;
  border-radius: 8px;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 32px;
}

.empty-label {
  font-size: 0.74rem;
  font-weight: 900;
  letter-spacing: 0;
  text-transform: uppercase;
  color: #ff6f3d;
}

.empty-dialog h2 {
  font-size: 3.5rem;
  line-height: 1;
  letter-spacing: 0;
  max-width: 680px;
  margin: 12px 0;
}

.empty-dialog p {
  max-width: 620px;
  color: #666;
  line-height: 1.6;
}

.message-card {
  max-width: 88%;
  border: 1px solid #e6e6e6;
  border-radius: 8px;
  padding: 16px;
  background: #fff;
}

.message-card.user {
  margin-left: auto;
  background: #111;
  color: #fff;
}

.message-card.assistant {
  margin-right: auto;
}

.message-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0;
  text-transform: uppercase;
  opacity: 0.74;
}

.message-content {
  line-height: 1.58;
  margin: 0;
}

.sectioned-answer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.answer-section h3 {
  margin: 0 0 8px;
  font-size: 0.92rem;
  font-weight: 900;
}

.answer-section ul {
  margin: 0;
  padding-left: 18px;
}

.answer-section li + li {
  margin-top: 6px;
}

.answer-section p {
  margin: 0;
  color: #666;
}

.markdown-body > :first-child {
  margin-top: 0;
}

.markdown-body > :last-child {
  margin-bottom: 0;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3 {
  margin: 0 0 10px;
  font-size: 1rem;
  line-height: 1.35;
}

.markdown-body p {
  margin: 0 0 12px;
}

.markdown-body ul,
.markdown-body ol {
  margin: 0 0 12px;
  padding-left: 20px;
}

.markdown-body li + li {
  margin-top: 6px;
}

.markdown-body strong {
  font-weight: 800;
}

.markdown-body em {
  font-style: italic;
}

.markdown-body code {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.85em;
  background: rgba(17, 17, 17, 0.06);
  border-radius: 4px;
  padding: 1px 5px;
}

.markdown-body pre {
  margin: 0 0 12px;
  padding: 12px;
  border: 1px solid #ececec;
  border-radius: 8px;
  background: #fafafa;
  overflow: auto;
}

.markdown-body pre code {
  background: transparent;
  border-radius: 0;
  padding: 0;
}

.markdown-body blockquote {
  margin: 0 0 12px;
  padding-left: 12px;
  border-left: 3px solid #d8d8d8;
  color: #555;
}

.event-timeline {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.event-chip {
  border: 1px solid #e6e6e6;
  background: #fff;
  color: #111;
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.event-chip span {
  font-size: 0.7rem;
  font-weight: 900;
  letter-spacing: 0;
  text-transform: uppercase;
}

.event-chip small {
  color: #666;
}

.event-chip.error {
  border-color: #ffd9d6;
}

.composer {
  border-top: 1px solid #eaeaea;
  padding: 18px 22px 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #fff;
}

.composer textarea {
  resize: vertical;
  min-height: 92px;
  padding: 14px 16px;
  line-height: 1.55;
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.composer-hint {
  color: #666;
  font-size: 0.82rem;
}

.spinner-sm {
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  display: inline-block;
  margin-right: 8px;
  animation: spin 0.8s linear infinite;
}

.new-session-btn {
  font-weight: 900;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 0;
}

.history-row span {
  display: block;
  font-weight: 900;
}

.session-detail {
  margin-top: auto;
}

.turn-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.turn-row {
  border-top: 1px solid #eaeaea;
  padding-top: 8px;
}

.turn-row span {
  font-size: 0.68rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0;
  color: #ff6f3d;
}

.turn-row p {
  margin: 4px 0 0;
  color: #555;
  line-height: 1.45;
}

.mono {
  font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  50% {
    opacity: 0.4;
  }
}

@media (max-width: 1280px) {
  .explorer-layout {
    grid-template-columns: minmax(260px, 0.9fr) minmax(480px, 1.4fr);
  }

  .history-panel {
    grid-column: 1 / -1;
    min-height: 260px;
  }

  .history-body {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    align-items: start;
  }

  .session-detail {
    margin-top: 0;
  }
}

@media (max-width: 860px) {
  .app-header {
    height: auto;
    min-height: 60px;
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
  }

  .header-left,
  .header-right {
    justify-content: space-between;
    width: 100%;
  }

  .header-center {
    position: static;
    transform: none;
    display: block;
    width: 100%;
  }

  .explorer-layout {
    grid-template-columns: 1fr;
    padding: 16px;
    overflow: visible;
  }

  .history-body {
    grid-template-columns: 1fr;
  }

  .tool-strip {
    align-items: stretch;
  }

  .tool-chip {
    width: 100%;
    justify-content: space-between;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .mode-bar,
  .composer-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .agent-select {
    max-width: none;
    margin-left: 0;
  }

  .message-card {
    max-width: 100%;
  }
}
</style>
