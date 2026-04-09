<template>
  <v-app>
    <div class="main-view">
      <header class="app-header">
        <div class="header-left">
          <div class="brand" @click="router.push('/')">SOCIOGRAPH</div>
        </div>

        <div class="header-center">
          <div class="view-switcher">
            <button
              v-for="mode in ['graph', 'split', 'workbench']"
              :key="mode"
              class="switch-btn"
              :class="{ active: viewMode === mode }"
              @click="viewMode = mode"
            >
              {{ layoutLabelMap[mode as keyof typeof layoutLabelMap] }}
            </button>
          </div>
        </div>

        <div class="header-right">
          <div class="workflow-step">
            <span class="step-num">Step 1/5</span>
            <span class="step-name">Graph Build</span>
          </div>

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

      <main class="content-area">
        <div class="panel-wrapper left" :style="leftPanelStyle">
          <section class="graph-panel">
            <div class="panel-header">
              <div class="panel-title-group">
                <span class="panel-title">GRAPH PANEL</span>
                <div class="panel-subtitle-row">
                  <span class="panel-subtitle">
                    {{ selectedProject?.name || 'Waiting for project selection' }}
                  </span>
                  <span v-if="selectedProject" :class="statusMeta(selectedProject.status).class">
                    {{ statusMeta(selectedProject.status).label }}
                  </span>
                </div>
              </div>

              <div class="header-tools">
                <button
                  class="tool-btn"
                  :disabled="graphLoading || !selectedProject?.zep_graph_id"
                  title="Refresh graph"
                  @click="refreshGraphAssets"
                >
                  <span class="icon-refresh" :class="{ spinning: graphLoading }">↻</span>
                  <span class="btn-text">Refresh</span>
                </button>
                <button class="tool-btn" title="Toggle maximize" @click="toggleMaximize('graph')">
                  <span class="icon-maximize">⛶</span>
                </button>
              </div>
            </div>

            <div class="graph-container">
              <div v-if="graphLoading" class="graph-state">
                <div class="loading-spinner"></div>
                <p>Graph data loading...</p>
              </div>

              <div v-else-if="selectedProject?.zep_graph_id || graphData" class="graph-view-shell">
                <ClientOnly>
                  <GraphCanvas
                    :nodes="graphData?.nodes || []"
                    :edges="graphData?.edges || []"
                    :layout-name="graphLayout"
                    @select="onGraphSelect"
                  />
                </ClientOnly>

                <div v-if="currentPhase === 1" class="graph-building-hint">
                  <div class="memory-icon-wrapper">✦</div>
                  Real-time updating during graph build
                </div>

                <div v-if="graphError" class="graph-inline-error">
                  {{ graphError }}
                </div>

                <div v-if="selectedGraphItem" class="detail-panel">
                  <div class="detail-panel-header">
                    <span class="detail-title">
                      {{ selectedGraphItem.type === 'node' ? 'Node Details' : 'Relationship' }}
                    </span>
                    <button class="detail-close" @click="selectedGraphItem = null">×</button>
                  </div>

                  <div class="detail-content">
                    <template v-if="selectedGraphItem.type === 'node'">
                      <div class="detail-row">
                        <span class="detail-label">Name:</span>
                        <span class="detail-value">{{ selectedGraphItem.data.name }}</span>
                      </div>
                      <div class="detail-row">
                        <span class="detail-label">UUID:</span>
                        <span class="detail-value uuid-text">{{ selectedGraphItem.data.uuid }}</span>
                      </div>
                      <div class="detail-section" v-if="selectedGraphItem.data.summary">
                        <div class="section-title">Summary</div>
                        <div class="summary-text">{{ selectedGraphItem.data.summary }}</div>
                      </div>
                      <div
                        v-if="selectedGraphItem.data.attributes && Object.keys(selectedGraphItem.data.attributes).length"
                        class="detail-section"
                      >
                        <div class="section-title">Properties</div>
                        <div class="properties-list">
                          <div
                            v-for="(value, key) in selectedGraphItem.data.attributes"
                            :key="String(key)"
                            class="property-item"
                          >
                            <span class="property-key">{{ key }}:</span>
                            <span class="property-value">{{ value || 'None' }}</span>
                          </div>
                        </div>
                      </div>
                      <div class="detail-section" v-if="selectedGraphItem.data.labels.length">
                        <div class="section-title">Labels</div>
                        <div class="labels-list">
                          <span v-for="label in selectedGraphItem.data.labels" :key="label" class="label-tag">
                            {{ label }}
                          </span>
                        </div>
                      </div>
                    </template>

                    <template v-else>
                      <div class="edge-relation-header">
                        {{ selectedGraphItem.data.source_node_name }} →
                        {{ selectedGraphItem.data.name || selectedGraphItem.data.fact_type || 'RELATED_TO' }} →
                        {{ selectedGraphItem.data.target_node_name }}
                      </div>
                      <div class="detail-row">
                        <span class="detail-label">UUID:</span>
                        <span class="detail-value uuid-text">{{ selectedGraphItem.data.uuid }}</span>
                      </div>
                      <div class="detail-row">
                        <span class="detail-label">Type:</span>
                        <span class="detail-value">{{ selectedGraphItem.data.fact_type || 'Unknown' }}</span>
                      </div>
                      <div class="detail-row" v-if="selectedGraphItem.data.fact">
                        <span class="detail-label">Fact:</span>
                        <span class="detail-value fact-text">{{ selectedGraphItem.data.fact }}</span>
                      </div>
                      <div class="detail-section" v-if="selectedGraphItem.data.episodes?.length">
                        <div class="section-title">Episodes</div>
                        <div class="labels-list">
                          <span v-for="episode in selectedGraphItem.data.episodes" :key="episode" class="label-tag">
                            {{ episode }}
                          </span>
                        </div>
                      </div>
                    </template>
                  </div>
                </div>
              </div>

              <div v-else-if="graphError" class="graph-state">
                <div class="empty-icon">!</div>
                <p class="empty-text">{{ graphError }}</p>
              </div>

              <div v-else class="graph-state">
                <div class="empty-icon">❖</div>
                <p class="empty-text">{{ graphEmptyMessage }}</p>
              </div>
            </div>

            <div v-if="legendEntityTypes.length" class="graph-legend">
              <span class="legend-title">Entity Types</span>
              <div class="legend-items">
                <div v-for="entityType in legendEntityTypes" :key="entityType.name" class="legend-item">
                  <span class="legend-dot" :style="{ background: entityType.color }"></span>
                  <span class="legend-label">{{ entityType.name }}</span>
                </div>
              </div>
            </div>

            <div class="edge-labels-toggle">
              <span class="toggle-label">Layout</span>
              <select v-model="graphLayout" class="layout-select">
                <option value="cose">Organic</option>
                <option value="breadthfirst">Hierarchy</option>
                <option value="circle">Circle</option>
              </select>
            </div>
          </section>
        </div>

        <div class="panel-wrapper right" :style="rightPanelStyle">
          <div class="workbench-panel">
            <div class="scroll-container">
              <div class="step-card create-card active">
                <div class="card-header">
                  <div class="step-info">
                    <span class="step-num">00</span>
                    <span class="step-title">Task Module</span>
                  </div>
                  <div class="step-status">
                    <span class="badge accent">Workspace</span>
                  </div>
                </div>

                <div class="card-content">
                  <p class="api-note">GET /api/graph/projects · POST /api/graph/project</p>
                  <p class="description">
                    The top bar stays focused on layout, step, and status. Project selection and
                    creation stay inside this workbench card.
                  </p>

                  <div v-if="createError" class="inline-error">{{ createError }}</div>

                  <div class="task-module-toolbar">
                    <button class="action-btn secondary" :disabled="projectsLoading" @click="refreshProjects(selectedProjectId)">
                      {{ projectsLoading ? 'Refreshing...' : 'Refresh List' }}
                    </button>
                    <button class="action-btn" @click="showCreateProject = !showCreateProject">
                      {{ showCreateProject ? 'Close Form' : 'New Project' }}
                    </button>
                  </div>

                  <div v-if="projects.length" class="project-grid">
                    <button
                      v-for="project in projects"
                      :key="project.id"
                      class="project-card-button"
                      :class="{ active: selectedProjectId === project.id }"
                      @click="selectProject(project.id)"
                    >
                      <div class="project-card-top">
                        <span class="project-card-name">{{ project.name }}</span>
                        <span :class="statusMeta(project.status).class">{{ statusMeta(project.status).label }}</span>
                      </div>
                      <div class="project-card-desc">
                        {{ project.simulation_requirement || 'No simulation requirement.' }}
                      </div>
                      <div class="project-card-id mono">{{ project.id }}</div>
                    </button>
                  </div>

                  <div v-else class="empty-module-state">
                    No projects yet. Create one to begin Step 1.
                  </div>

                  <div v-if="showCreateProject" class="create-form-block">
                    <div class="field-grid">
                      <input
                        v-model="createForm.name"
                        class="input-field"
                        type="text"
                        placeholder="Project name"
                      />
                      <textarea
                        v-model="createForm.simulation_requirement"
                        class="input-field textarea-field"
                        rows="4"
                        placeholder="Simulation requirement"
                      ></textarea>
                    </div>

                    <button class="action-btn" :disabled="createLoading" @click="createProject">
                      <span v-if="createLoading" class="spinner-sm"></span>
                      {{ createLoading ? 'Creating...' : 'Create Project' }}
                    </button>
                  </div>
                </div>
              </div>

              <div class="step-card" :class="{ active: currentPhase === 0, completed: currentPhase > 0 }">
                <div class="card-header">
                  <div class="step-info">
                    <span class="step-num">01</span>
                    <span class="step-title">Ontology Generation</span>
                  </div>
                  <div class="step-status">
                    <span v-if="currentPhase > 0" class="badge success">Completed</span>
                    <span v-else-if="currentPhase === 0" class="badge processing">
                      {{ ontologyTask?.progress ?? 0 }}%
                    </span>
                    <span v-else class="badge pending">Pending</span>
                  </div>
                </div>

                <div class="card-content">
                  <p class="api-note">POST /api/graph/ontology/generate</p>
                  <p class="description">
                    Upload PDF / MD / TXT, extract text, and generate ontology for the selected project.
                  </p>

                  <div class="info-grid">
                    <div class="info-item">
                      <span class="info-label">Project</span>
                      <span class="info-value">{{ selectedProject?.name || 'None selected' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Status</span>
                      <span class="info-value">{{ selectedProject ? statusMeta(selectedProject.status).label : 'Idle' }}</span>
                    </div>
                    <div class="info-item full">
                      <span class="info-label">Requirement</span>
                      <span class="info-value">{{ selectedProject?.simulation_requirement || 'Create or select a project first.' }}</span>
                    </div>
                  </div>

                  <label class="upload-zone" :class="{ 'has-files': uploadFiles.length > 0 }">
                    <input
                      class="hidden-input"
                      type="file"
                      multiple
                      accept=".pdf,.md,.markdown,.txt"
                      @change="onUploadFilesChange"
                    />

                    <div v-if="uploadFiles.length === 0" class="upload-placeholder">
                      <div class="upload-icon">↑</div>
                      <div class="upload-title">Drag to upload</div>
                      <div class="upload-hint">or click to browse</div>
                    </div>

                    <div v-else class="files-summary">
                      <span v-for="file in uploadFiles" :key="file.name + file.lastModified" class="file-chip">
                        {{ file.name }}
                      </span>
                    </div>
                  </label>

                  <textarea
                    v-model="additionalContext"
                    class="input-field textarea-field"
                    rows="3"
                    placeholder="Additional context (optional)"
                  ></textarea>

                  <div v-if="ontologyTask" class="progress-section">
                    <div class="spinner-sm" v-if="ontologyTask.status === 'processing'"></div>
                    <span>{{ ontologyTask.message || 'Analyzing docs...' }}</span>
                    <span class="progress-number">{{ ontologyTask.progress }}%</span>
                  </div>

                  <div v-if="ontologyError || ontologyTask?.error" class="inline-error">
                    {{ summarizeError(ontologyError || ontologyTask?.error || '') }}
                  </div>

                  <div v-if="ontologyEntityTypes.length" class="tags-container">
                    <span class="tag-label">GENERATED ENTITY TYPES</span>
                    <div class="tags-list">
                      <span v-for="entityType in ontologyEntityTypes" :key="entityType" class="entity-tag">
                        {{ entityType }}
                      </span>
                    </div>
                  </div>

                  <div v-if="relationTypes.length" class="tags-container">
                    <span class="tag-label">GENERATED RELATION TYPES</span>
                    <div class="tags-list">
                      <span v-for="relation in relationTypes" :key="relation" class="entity-tag">
                        {{ relation }}
                      </span>
                    </div>
                  </div>

                  <button
                    class="action-btn"
                    :disabled="ontologySubmitting || !selectedProject || uploadFiles.length === 0"
                    @click="startOntologyTask"
                  >
                    <span v-if="ontologySubmitting" class="spinner-sm"></span>
                    {{ ontologySubmitting ? 'Generating...' : 'Generate Ontology' }}
                  </button>
                </div>
              </div>

              <div class="step-card" :class="{ active: currentPhase === 1, completed: currentPhase > 1 }">
                <div class="card-header">
                  <div class="step-info">
                    <span class="step-num">02</span>
                    <span class="step-title">Graph RAG Build</span>
                  </div>
                  <div class="step-status">
                    <span v-if="currentPhase > 1" class="badge success">Completed</span>
                    <span v-else-if="currentPhase === 1" class="badge processing">
                      {{ buildTask?.progress ?? 0 }}%
                    </span>
                    <span v-else class="badge pending">Pending</span>
                  </div>
                </div>

                <div class="card-content">
                  <p class="api-note">POST /api/graph/build</p>
                  <p class="description">
                    Push extracted text and ontology into Zep, then expose graph nodes and edges for browsing.
                  </p>

                  <div class="field-grid compact-grid">
                    <input
                      v-model="buildForm.graph_name"
                      class="input-field"
                      type="text"
                      placeholder="Graph name"
                    />
                    <div class="inline-grid">
                      <input
                        v-model.number="buildForm.chunk_size"
                        class="input-field"
                        type="number"
                        min="100"
                        placeholder="Chunk size"
                      />
                      <input
                        v-model.number="buildForm.chunk_overlap"
                        class="input-field"
                        type="number"
                        min="0"
                        placeholder="Overlap"
                      />
                      <input
                        v-model.number="buildForm.batch_size"
                        class="input-field"
                        type="number"
                        min="1"
                        placeholder="Batch"
                      />
                    </div>
                  </div>

                  <div class="stats-grid">
                    <div class="stat-card">
                      <span class="stat-value">{{ graphData?.node_count || 0 }}</span>
                      <span class="stat-label">ENTITY NODES</span>
                    </div>
                    <div class="stat-card">
                      <span class="stat-value">{{ graphData?.edge_count || 0 }}</span>
                      <span class="stat-label">RELATION EDGES</span>
                    </div>
                    <div class="stat-card">
                      <span class="stat-value">{{ ontologyEntityTypes.length }}</span>
                      <span class="stat-label">SCHEMA TYPES</span>
                    </div>
                  </div>

                  <div v-if="buildTask" class="progress-section">
                    <div class="spinner-sm" v-if="buildTask.status === 'processing'"></div>
                    <span>{{ buildTask.message || 'Starting build...' }}</span>
                    <span class="progress-number">{{ buildTask.progress }}%</span>
                  </div>

                  <div v-if="buildError || buildTask?.error" class="inline-error">
                    {{ summarizeError(buildError || buildTask?.error || '') }}
                  </div>

                  <div class="action-row">
                    <button
                      class="action-btn secondary"
                      :disabled="!selectedProject?.zep_graph_id"
                      @click="refreshGraphAssets"
                    >
                      Refresh Graph
                    </button>
                    <button
                      class="action-btn"
                      :disabled="buildSubmitting || !selectedProject?.ontology_path"
                      @click="startGraphBuildTask"
                    >
                      <span v-if="buildSubmitting" class="spinner-sm"></span>
                      {{ buildSubmitting ? 'Building...' : 'Build Graph' }}
                    </button>
                  </div>
                </div>
              </div>

              <div class="step-card" :class="{ active: currentPhase === 2, completed: currentPhase >= 2 }">
                <div class="card-header">
                  <div class="step-info">
                    <span class="step-num">03</span>
                    <span class="step-title">Build Complete</span>
                  </div>
                  <div class="step-status">
                    <span v-if="currentPhase >= 2" class="badge accent">Ready</span>
                    <span v-else class="badge pending">Waiting</span>
                  </div>
                </div>

                <div class="card-content">
                  <p class="api-note">NEXT → Task 9</p>
                  <p class="description">
                    Step 1 is done when project state, graph ID, and graph visualization can all be restored after refresh.
                  </p>

                  <div class="info-grid">
                    <div class="info-item">
                      <span class="info-label">Project ID</span>
                      <span class="info-value mono">{{ selectedProject?.id || 'N/A' }}</span>
                    </div>
                    <div class="info-item">
                      <span class="info-label">Graph ID</span>
                      <span class="info-value mono">{{ selectedProject?.zep_graph_id || 'N/A' }}</span>
                    </div>
                  </div>

                  <button
                    class="action-btn"
                    :disabled="currentPhase < 2 || !selectedProject"
                    @click="router.push({ path: '/simulation', query: selectedProject ? { project: selectedProject.id } : {} })"
                  >
                    Open Step 2 ➝
                  </button>
                </div>
              </div>
            </div>

            <div class="system-logs">
              <div class="log-header">
                <span class="log-title">SYSTEM DASHBOARD</span>
                <span class="log-id">{{ selectedProject?.id || 'NO_PROJECT' }}</span>
              </div>
              <div ref="logContentRef" class="log-content">
                <div v-for="(log, index) in systemLogs" :key="index" class="log-line">
                  <span class="log-time">{{ log.time }}</span>
                  <span class="log-msg">{{ log.msg }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </v-app>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useHead } from 'nuxt/app'
import { useRoute, useRouter } from 'vue-router'
import { getApiErrorMessage, useApiFetch } from '~/composables/useApiFetch'

type ProjectStatus = 'created' | 'ontology_generated' | 'graph_building' | 'graph_completed' | 'failed'
type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'
type GraphLayout = 'cose' | 'breadthfirst' | 'circle'
type ViewMode = 'graph' | 'split' | 'workbench'

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

type TaskRecord = {
  task_id: string
  task_type: string
  project_id: string | null
  simulation_id: string | null
  status: TaskStatus
  progress: number
  message: string
  result_json: Record<string, any> | null
  progress_detail_json: Record<string, any> | null
  error: string | null
  created_at: string
  updated_at: string
}

type TaskResponse = {
  task_id: string
}

type GraphDataNode = {
  uuid: string
  name: string
  labels: string[]
  summary: string
  attributes: Record<string, unknown>
}

type GraphDataEdge = {
  uuid: string
  name: string
  fact: string
  fact_type: string
  source_node_uuid: string
  target_node_uuid: string
  source_node_name: string
  target_node_name: string
  attributes: Record<string, unknown>
  episodes: string[]
}

type GraphDataResponse = {
  graph_id: string
  nodes: GraphDataNode[]
  edges: GraphDataEdge[]
  node_count: number
  edge_count: number
}

type PersistedWorkspaceState = {
  selectedProjectId: string | null
  ontologyTaskIds: Record<string, string>
  buildTaskIds: Record<string, string>
}

type GraphSelection =
  | {
      type: 'node'
      data: GraphDataNode
    }
  | {
      type: 'edge'
      data: GraphDataEdge
    }
  | null

type SystemLog = {
  time: string
  msg: string
}

const STORAGE_KEY = 'fyp.graph.workspace.v1'
const layoutLabelMap = {
  graph: 'Graph',
  split: 'Split',
  workbench: 'Workbench',
} as const

const apiFetch = useApiFetch()
const route = useRoute()
const router = useRouter()

useHead({
  title: 'SocioGraph Workspace',
})

const projects = ref<ProjectRecord[]>([])
const selectedProjectId = ref<string | null>(null)
const graphData = ref<GraphDataResponse | null>(null)
const ontologyTask = ref<TaskRecord | null>(null)
const buildTask = ref<TaskRecord | null>(null)
const selectedGraphItem = ref<GraphSelection>(null)
const uploadFiles = ref<File[]>([])
const additionalContext = ref('')
const viewMode = ref<ViewMode>('split')
const graphLayout = ref<GraphLayout>('cose')
const showCreateProject = ref(false)

const createLoading = ref(false)
const projectsLoading = ref(false)
const ontologySubmitting = ref(false)
const buildSubmitting = ref(false)
const graphLoading = ref(false)

const pageError = ref('')
const createError = ref('')
const ontologyError = ref('')
const buildError = ref('')
const graphError = ref('')

const systemLogs = ref<SystemLog[]>([])
const logContentRef = ref<HTMLDivElement | null>(null)
const lastOntologyMessage = ref('')
const lastBuildMessage = ref('')

const createForm = reactive({
  name: '',
  simulation_requirement: '',
})

const buildForm = reactive({
  graph_name: '',
  chunk_size: 500,
  chunk_overlap: 50,
  batch_size: 3,
})

const persistedState = reactive<PersistedWorkspaceState>({
  selectedProjectId: null,
  ontologyTaskIds: {},
  buildTaskIds: {},
})

let ontologyPollTimer: ReturnType<typeof window.setInterval> | null = null
let buildPollTimer: ReturnType<typeof window.setInterval> | null = null

const selectedProject = computed(() => {
  return projects.value.find((project) => project.id === selectedProjectId.value) || null
})

const graphEmptyMessage = computed(() => {
  if (!selectedProject.value) {
    return 'Select or create a project to begin.'
  }

  if (selectedProject.value.status === 'created') {
    return 'Project selected. Generate ontology in Step 01 first.'
  }

  if (selectedProject.value.status === 'ontology_generated') {
    return 'Ontology is ready. Run Build Graph in Step 02 to populate the panel.'
  }

  if (selectedProject.value.status === 'graph_building') {
    return 'Graph build is in progress. Refresh or wait for new nodes and edges.'
  }

  if (selectedProject.value.status === 'failed') {
    return 'This project is in a failed state. Retry ontology or graph build from the workbench.'
  }

  return 'Graph metadata exists. Refresh graph to load the latest nodes and edges.'
})

const currentPhase = computed(() => {
  if (buildTask.value?.status === 'processing' || selectedProject.value?.status === 'graph_building') {
    return 1
  }
  if (selectedProject.value?.status === 'graph_completed' || buildTask.value?.status === 'completed') {
    return 2
  }
  if (ontologyTask.value?.status === 'processing' || selectedProject.value?.status === 'ontology_generated') {
    return 0
  }
  return -1
})

const latestError = computed(() => {
  return (
    pageError.value ||
    createError.value ||
    ontologyError.value ||
    buildError.value ||
    graphError.value ||
    ontologyTask.value?.error ||
    buildTask.value?.error ||
    ''
  )
})

const statusClass = computed(() => {
  if (latestError.value) {
    return 'error'
  }
  if (currentPhase.value >= 2) {
    return 'completed'
  }
  return 'processing'
})

const statusText = computed(() => {
  if (latestError.value) {
    return 'Error'
  }
  if (currentPhase.value >= 2) {
    return 'Ready'
  }
  if (currentPhase.value === 1) {
    return 'Building Graph'
  }
  if (currentPhase.value === 0) {
    return 'Generating Ontology'
  }
  if (selectedProject.value) {
    return 'Project Loaded'
  }
  return 'Idle'
})

const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') {
    return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  }
  if (viewMode.value === 'workbench') {
    return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') {
    return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  }
  if (viewMode.value === 'graph') {
    return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const ontologyEntityTypes = computed(() => {
  const fromBuild = Array.isArray(buildTask.value?.result_json?.entity_types)
    ? (buildTask.value?.result_json?.entity_types as string[])
    : []
  const fromGraph = (graphData.value?.nodes || []).flatMap((node) =>
    node.labels.filter((label) => !['Entity', 'Node'].includes(label)),
  )
  return Array.from(new Set([...fromBuild, ...fromGraph])).filter(Boolean)
})

const relationTypes = computed(() => {
  const edgeTypes = (graphData.value?.edges || [])
    .map((edge) => edge.fact_type || edge.name)
    .filter(Boolean) as string[]
  return Array.from(new Set(edgeTypes)).slice(0, 24)
})

const legendEntityTypes = computed(() => {
  return ontologyEntityTypes.value.slice(0, 12).map((name) => ({
    name,
    color: entityTypeColor(name),
  }))
})

function entityTypeColor(name: string) {
  const palette: Record<string, string> = {
    Character: '#FF7043',
    Person: '#FF7043',
    Organization: '#42A5F5',
    Location: '#26A69A',
    Event: '#AB47BC',
    Concept: '#78909C',
  }
  return palette[name] || '#607D8B'
}

function addLog(msg: string) {
  const now = new Date()
  const time =
    now.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }) +
    '.' +
    now.getMilliseconds().toString().padStart(3, '0')

  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

function persistWorkspaceState() {
  if (!import.meta.client) {
    return
  }

  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      selectedProjectId: selectedProjectId.value,
      ontologyTaskIds: persistedState.ontologyTaskIds,
      buildTaskIds: persistedState.buildTaskIds,
    }),
  )
}

function loadWorkspaceState() {
  if (!import.meta.client) {
    return
  }

  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return
  }

  try {
    const parsed = JSON.parse(raw) as PersistedWorkspaceState
    persistedState.selectedProjectId = parsed.selectedProjectId || null
    persistedState.ontologyTaskIds = parsed.ontologyTaskIds || {}
    persistedState.buildTaskIds = parsed.buildTaskIds || {}
  } catch {
    window.localStorage.removeItem(STORAGE_KEY)
  }
}

function summarizeError(error: string | null | undefined) {
  if (!error) {
    return ''
  }
  return error.split('\n').slice(0, 3).join('\n')
}

function normalizeApiError(error: unknown) {
  const message = getApiErrorMessage(error)
  const lower = message.toLowerCase()

  if (
    lower.includes('not logged in') ||
    lower.includes('unauthorized') ||
    lower.includes('forbidden')
  ) {
    return 'Backend still needs a restart to load the latest API changes.'
  }

  return message
}

function statusMeta(status: ProjectStatus) {
  const meta: Record<ProjectStatus, { label: string; class: string }> = {
    created: { label: 'Created', class: 'badge pending' },
    ontology_generated: { label: 'Ontology Ready', class: 'badge success' },
    graph_building: { label: 'Building', class: 'badge processing' },
    graph_completed: { label: 'Graph Ready', class: 'badge accent' },
    failed: { label: 'Failed', class: 'badge danger' },
  }
  return meta[status]
}

function syncSelectedProjectQuery(projectId: string | null) {
  const currentProjectId = typeof route.query.project === 'string' ? route.query.project : null
  if (currentProjectId === projectId) {
    return
  }

  const nextQuery = { ...route.query }
  if (projectId) {
    nextQuery.project = projectId
  } else {
    delete nextQuery.project
  }

  void router.replace({ query: nextQuery })
}

function stopOntologyPolling() {
  if (ontologyPollTimer) {
    clearInterval(ontologyPollTimer)
    ontologyPollTimer = null
  }
}

function stopBuildPolling() {
  if (buildPollTimer) {
    clearInterval(buildPollTimer)
    buildPollTimer = null
  }
}

function clearGraphAssets() {
  graphData.value = null
  graphError.value = ''
  selectedGraphItem.value = null
}

async function fetchProjects() {
  projectsLoading.value = true
  try {
    const response = await apiFetch<ProjectListResponse>('/api/graph/projects', { method: 'GET' })
    projects.value = response.projects
  } finally {
    projectsLoading.value = false
  }
}

function resolveInitialProjectId(nextProjects: ProjectRecord[]) {
  const routeProjectId = typeof route.query.project === 'string' ? route.query.project : null
  const candidates = [routeProjectId, selectedProjectId.value, persistedState.selectedProjectId]

  for (const candidate of candidates) {
    if (candidate && nextProjects.some((project) => project.id === candidate)) {
      return candidate
    }
  }

  return nextProjects[0]?.id || null
}

async function refreshProjects(preferredProjectId?: string | null) {
  pageError.value = ''
  try {
    await fetchProjects()
    addLog(`Project list refreshed. Count: ${projects.value.length}`)
    if (projects.value.length === 0) {
      showCreateProject.value = true
    }
    const nextProjectId =
      preferredProjectId && projects.value.some((project) => project.id === preferredProjectId)
        ? preferredProjectId
        : resolveInitialProjectId(projects.value)
    await selectProject(nextProjectId)
  } catch (error) {
    pageError.value = normalizeApiError(error)
    addLog(`Error refreshing projects: ${pageError.value}`)
  }
}

async function selectProject(projectId: string | null) {
  selectedProjectId.value = projectId
  persistedState.selectedProjectId = projectId
  persistWorkspaceState()
  syncSelectedProjectQuery(projectId)

  ontologyError.value = ''
  buildError.value = ''
  selectedGraphItem.value = null
  lastOntologyMessage.value = ''
  lastBuildMessage.value = ''

  stopOntologyPolling()
  stopBuildPolling()

  if (!projectId) {
    ontologyTask.value = null
    buildTask.value = null
    clearGraphAssets()
    return
  }

  const project = projects.value.find((item) => item.id === projectId) || null
  buildForm.graph_name = project?.name || ''
  addLog(`Project selected: ${project?.name || projectId}`)

  await Promise.all([resumeTaskTracking(projectId), loadGraphAssetsForProject(projectId)])
}

function onUploadFilesChange(event: Event) {
  const input = event.target as HTMLInputElement
  uploadFiles.value = Array.from(input.files || [])
  if (uploadFiles.value.length) {
    addLog(`Files selected: ${uploadFiles.value.map((file) => file.name).join(', ')}`)
  }
}

async function createProject() {
  createError.value = ''

  if (!createForm.name.trim() || !createForm.simulation_requirement.trim()) {
    createError.value = 'Project name and simulation requirement are required.'
    return
  }

  createLoading.value = true
  try {
    const project = await apiFetch<ProjectRecord>('/api/graph/project', {
      method: 'POST',
      body: {
        name: createForm.name.trim(),
        simulation_requirement: createForm.simulation_requirement.trim(),
      },
    })

    addLog(`Project created: ${project.id}`)
    createForm.name = ''
    createForm.simulation_requirement = ''
    showCreateProject.value = false
    await refreshProjects(project.id)
  } catch (error) {
    createError.value = normalizeApiError(error)
    addLog(`Project create failed: ${createError.value}`)
  } finally {
    createLoading.value = false
  }
}

async function fetchTask(taskId: string) {
  return await apiFetch<TaskRecord>(`/api/graph/task/${taskId}`, { method: 'GET' })
}

async function pollTask(kind: 'ontology' | 'build', taskId: string, projectId: string) {
  try {
    const task = await fetchTask(taskId)

    if (selectedProjectId.value !== projectId) {
      return
    }

    if (kind === 'ontology') {
      const changed = task.message && task.message !== lastOntologyMessage.value
      ontologyTask.value = task
      if (changed) {
        lastOntologyMessage.value = task.message
        addLog(task.message)
      }
    } else {
      const changed = task.message && task.message !== lastBuildMessage.value
      buildTask.value = task
      if (changed) {
        lastBuildMessage.value = task.message
        addLog(task.message)
      }
    }

    if (task.status === 'completed' || task.status === 'failed') {
      if (kind === 'ontology') {
        stopOntologyPolling()
      } else {
        stopBuildPolling()
      }

      if (task.status === 'failed') {
        addLog(`${kind === 'ontology' ? 'Ontology' : 'Graph build'} failed.`)
      } else {
        addLog(`${kind === 'ontology' ? 'Ontology' : 'Graph build'} completed.`)
      }

      await refreshProjects(projectId)

      if (kind === 'build' && task.status === 'completed') {
        const graphId = task.result_json?.graph_id || selectedProject.value?.zep_graph_id
        if (graphId) {
          await loadGraphAssets(projectId, graphId)
        }
      }
    }
  } catch (error) {
    const message = getApiErrorMessage(error)
    if (kind === 'ontology') {
      stopOntologyPolling()
      ontologyError.value = message
    } else {
      stopBuildPolling()
      buildError.value = message
    }
    addLog(`${kind === 'ontology' ? 'Ontology' : 'Graph build'} polling failed: ${message}`)
  }
}

function startPolling(kind: 'ontology' | 'build', taskId: string, projectId: string) {
  if (!import.meta.client) {
    return
  }

  if (kind === 'ontology') {
    stopOntologyPolling()
  } else {
    stopBuildPolling()
  }

  void pollTask(kind, taskId, projectId)

  const timer = window.setInterval(() => {
    void pollTask(kind, taskId, projectId)
  }, 2500)

  if (kind === 'ontology') {
    ontologyPollTimer = timer
  } else {
    buildPollTimer = timer
  }
}

async function resumeTaskTracking(projectId: string) {
  ontologyTask.value = null
  buildTask.value = null

  const ontologyTaskId = persistedState.ontologyTaskIds[projectId]
  const buildTaskId = persistedState.buildTaskIds[projectId]

  if (ontologyTaskId) {
    try {
      const task = await fetchTask(ontologyTaskId)
      if (selectedProjectId.value === projectId) {
        ontologyTask.value = task
      }
      if (task.message) {
        lastOntologyMessage.value = task.message
      }
      if (task.status === 'processing') {
        startPolling('ontology', ontologyTaskId, projectId)
      }
    } catch {
      delete persistedState.ontologyTaskIds[projectId]
      persistWorkspaceState()
    }
  }

  if (buildTaskId) {
    try {
      const task = await fetchTask(buildTaskId)
      if (selectedProjectId.value === projectId) {
        buildTask.value = task
      }
      if (task.message) {
        lastBuildMessage.value = task.message
      }
      if (task.status === 'processing') {
        startPolling('build', buildTaskId, projectId)
      }
    } catch {
      delete persistedState.buildTaskIds[projectId]
      persistWorkspaceState()
    }
  }
}

async function startOntologyTask() {
  ontologyError.value = ''

  if (!selectedProject.value) {
    ontologyError.value = 'Select a project before uploading files.'
    return
  }

  if (!uploadFiles.value.length) {
    ontologyError.value = 'Choose at least one file.'
    return
  }

  const projectId = selectedProject.value.id
  const formData = new FormData()
  formData.append('project_id', projectId)
  for (const file of uploadFiles.value) {
    formData.append('files', file)
  }
  if (additionalContext.value.trim()) {
    formData.append('additional_context', additionalContext.value.trim())
  }

  ontologySubmitting.value = true
  addLog('Starting ontology generation.')
  try {
    const response = await apiFetch<TaskResponse>('/api/graph/ontology/generate', {
      method: 'POST',
      body: formData,
    })

    persistedState.ontologyTaskIds[projectId] = response.task_id
    persistWorkspaceState()
    addLog(`Ontology task started: ${response.task_id}`)
    startPolling('ontology', response.task_id, projectId)
  } catch (error) {
    ontologyError.value = normalizeApiError(error)
    addLog(`Ontology start failed: ${ontologyError.value}`)
  } finally {
    ontologySubmitting.value = false
  }
}

async function startGraphBuildTask() {
  buildError.value = ''

  if (!selectedProject.value) {
    buildError.value = 'Select a project before building the graph.'
    return
  }

  if (!selectedProject.value.ontology_path) {
    buildError.value = 'Generate ontology before starting graph build.'
    return
  }

  if (buildForm.chunk_overlap >= buildForm.chunk_size) {
    buildError.value = 'Chunk overlap must be smaller than chunk size.'
    return
  }

  const projectId = selectedProject.value.id
  buildSubmitting.value = true
  addLog('Initiating graph build.')
  try {
    const response = await apiFetch<TaskResponse>('/api/graph/build', {
      method: 'POST',
      body: {
        project_id: projectId,
        graph_name: buildForm.graph_name.trim() || selectedProject.value.name,
        chunk_size: Number(buildForm.chunk_size),
        chunk_overlap: Number(buildForm.chunk_overlap),
        batch_size: Number(buildForm.batch_size),
      },
    })

    persistedState.buildTaskIds[projectId] = response.task_id
    persistWorkspaceState()
    addLog(`Graph build task started: ${response.task_id}`)
    startPolling('build', response.task_id, projectId)
  } catch (error) {
    buildError.value = normalizeApiError(error)
    addLog(`Graph build start failed: ${buildError.value}`)
  } finally {
    buildSubmitting.value = false
  }
}

async function loadGraphAssets(projectId: string, graphId: string, options?: { refresh?: boolean }) {
  graphLoading.value = true
  graphError.value = ''

  try {
    const query = options?.refresh ? '?refresh=true' : ''
    const graphResponse = await apiFetch<GraphDataResponse>(`/api/graph/data/${graphId}${query}`, { method: 'GET' })

    if (selectedProjectId.value !== projectId) {
      return
    }

    graphData.value = graphResponse
    addLog(
      `Graph data refreshed. Nodes: ${graphResponse.node_count || graphResponse.nodes.length}, Edges: ${graphResponse.edge_count || graphResponse.edges.length}`,
    )
  } catch (error) {
    if (selectedProjectId.value === projectId) {
      graphError.value = normalizeApiError(error)
      graphData.value = null
    }
    addLog(`Graph load failed: ${graphError.value || normalizeApiError(error)}`)
  } finally {
    if (selectedProjectId.value === projectId) {
      graphLoading.value = false
    }
  }
}

async function loadGraphAssetsForProject(projectId: string) {
  const project = projects.value.find((item) => item.id === projectId) || null
  if (!project?.zep_graph_id) {
    if (selectedProjectId.value === projectId) {
      clearGraphAssets()
    }
    return
  }

  await loadGraphAssets(projectId, project.zep_graph_id)
}

async function refreshGraphAssets() {
  if (!selectedProject.value?.zep_graph_id) {
    graphError.value = 'This project does not have a graph yet.'
    return
  }

  addLog('Manual graph refresh triggered.')
  await loadGraphAssets(selectedProject.value.id, selectedProject.value.zep_graph_id, { refresh: true })
}

function onGraphSelect(selection: GraphSelection) {
  selectedGraphItem.value = selection
}

function toggleMaximize(target: 'graph' | 'workbench') {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

watch(
  () => systemLogs.value.length,
  () => {
    nextTick(() => {
      if (logContentRef.value) {
        logContentRef.value.scrollTop = logContentRef.value.scrollHeight
      }
    })
  },
)

onMounted(async () => {
  addLog('Project view initialized.')
  loadWorkspaceState()
  await refreshProjects()
})

onBeforeUnmount(() => {
  stopOntologyPolling()
  stopBuildPolling()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.app-header {
  height: 60px;
  border-bottom: 1px solid #eaeaea;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #fff;
  z-index: 20;
  position: relative;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 1px;
  cursor: pointer;
}

.view-switcher {
  display: flex;
  background: #f5f5f5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #fff;
  color: #000;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.project-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selector-label {
  font-size: 11px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.selector-control,
.layout-select {
  border: 1px solid #e3e3e3;
  background: #fff;
  color: #111;
  border-radius: 6px;
  font-size: 12px;
  padding: 8px 12px;
  min-width: 170px;
  outline: none;
}

.header-btn {
  border: 1px solid #111;
  background: #111;
  color: #fff;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.header-btn.subtle {
  background: #fff;
  color: #111;
  border-color: #ddd;
}

.header-btn:hover {
  opacity: 0.82;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
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
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}

.status-indicator.processing .dot {
  background: #ff5722;
  animation: pulse 1s infinite;
}

.status-indicator.completed .dot {
  background: #4caf50;
}

.status-indicator.error .dot {
  background: #f44336;
}

@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}

.page-error-banner {
  padding: 10px 24px;
  background: #fff1f0;
  border-bottom: 1px solid #ffd9d6;
  color: #c62828;
  font-size: 12px;
}

.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid #eaeaea;
}

.graph-panel {
  height: 100%;
  background: #fff;
  display: flex;
  flex-direction: column;
  position: relative;
}

.panel-header {
  height: 56px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eaeaea;
}

.panel-title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.panel-subtitle-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #000;
}

.panel-subtitle {
  font-size: 11px;
  color: #888;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-btn {
  border: 1px solid #e6e6e6;
  background: #fff;
  color: #333;
  border-radius: 6px;
  height: 34px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  cursor: pointer;
}

.tool-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.graph-container {
  flex: 1;
  position: relative;
  min-height: 0;
  background: #fafafa;
}

.graph-view-shell {
  position: relative;
  height: 100%;
}

.graph-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  color: #7a7a7a;
  font-size: 13px;
}

.loading-spinner {
  width: 26px;
  height: 26px;
  border: 2px solid #ffe0d5;
  border-top-color: #ff5722;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.empty-icon {
  font-size: 26px;
  color: #b0b0b0;
}

.empty-text {
  max-width: 280px;
  text-align: center;
  line-height: 1.6;
}

.graph-building-hint {
  position: absolute;
  top: 16px;
  left: 16px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid #ececec;
  font-size: 12px;
  color: #111;
}

.memory-icon-wrapper {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #111;
  color: #fff;
  font-size: 11px;
}

.graph-inline-error {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 241, 240, 0.95);
  border: 1px solid #ffd9d6;
  color: #c62828;
  font-size: 12px;
}

.detail-panel {
  position: absolute;
  top: 16px;
  right: 16px;
  width: min(360px, calc(100% - 32px));
  max-height: calc(100% - 32px);
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid #eaeaea;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #eaeaea;
  background: #fafafa;
}

.detail-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-close {
  border: none;
  background: none;
  font-size: 18px;
  color: #999;
  cursor: pointer;
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
}

.detail-row {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 12px;
  line-height: 1.5;
}

.detail-label {
  min-width: 56px;
  color: #888;
  font-weight: 600;
}

.detail-value {
  color: #111;
  word-break: break-word;
}

.uuid-text,
.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

.detail-section {
  margin-top: 14px;
}

.section-title {
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 8px;
  color: #666;
  text-transform: uppercase;
}

.summary-text {
  font-size: 12px;
  line-height: 1.6;
  color: #333;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-item {
  display: flex;
  gap: 8px;
  background: #f8f8f8;
  border-radius: 6px;
  padding: 8px;
  font-size: 11px;
  line-height: 1.5;
}

.property-key {
  font-weight: 700;
  color: #111;
}

.property-value,
.fact-text {
  color: #555;
}

.labels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.label-tag {
  font-size: 11px;
  background: #fff;
  border: 1px solid #e0e0e0;
  padding: 4px 8px;
  border-radius: 999px;
  color: #555;
}

.edge-relation-header {
  margin-bottom: 12px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.5;
}

.graph-legend {
  position: absolute;
  left: 16px;
  bottom: 16px;
  z-index: 4;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #eaeaea;
  border-radius: 8px;
  padding: 10px 12px;
  max-width: 240px;
}

.legend-title {
  display: block;
  font-size: 10px;
  font-weight: 700;
  color: #888;
  margin-bottom: 8px;
  text-transform: uppercase;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-label {
  color: #444;
}

.edge-labels-toggle {
  position: absolute;
  right: 16px;
  bottom: 16px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #eaeaea;
  background: rgba(255, 255, 255, 0.95);
  z-index: 4;
}

.toggle-label {
  font-size: 11px;
  color: #666;
  font-weight: 600;
}

.workbench-panel {
  height: 100%;
  background-color: #fafafa;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.step-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 1px solid #eaeaea;
  transition: all 0.3s ease;
}

.step-card.active {
  border-color: #ff5722;
  box-shadow: 0 4px 12px rgba(255, 87, 34, 0.08);
}

.step-card.completed {
  border-color: #ddd;
}

.create-card {
  background: #fffdf8;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.badge {
  font-size: 10px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.success {
  background: #e8f5e9;
  color: #2e7d32;
}

.badge.processing {
  background: #ff5722;
  color: #fff;
}

.badge.accent {
  background: #111;
  color: #fff;
}

.badge.pending {
  background: #f5f5f5;
  color: #999;
}

.badge.danger {
  background: #ffebee;
  color: #c62828;
}

.card-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.task-module-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.project-card-button {
  border: 1px solid #e4e4e4;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.project-card-button:hover {
  border-color: #d3d3d3;
  box-shadow: 0 8px 18px rgba(17, 17, 17, 0.05);
  transform: translateY(-1px);
}

.project-card-button.active {
  border-color: #ff5722;
  box-shadow: 0 6px 16px rgba(255, 87, 34, 0.12);
}

.project-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.project-card-name {
  font-size: 13px;
  font-weight: 700;
  color: #111;
}

.project-card-desc {
  font-size: 11px;
  color: #666;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.project-card-id {
  font-size: 10px;
  color: #9a9a9a;
}

.create-form-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 4px;
}

.empty-module-state {
  border: 1px dashed #d8d8d8;
  border-radius: 8px;
  padding: 18px;
  background: #fff;
  font-size: 12px;
  color: #777;
}

.api-note {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #999;
}

.description {
  font-size: 12px;
  color: #666;
  line-height: 1.6;
}

.field-grid,
.info-grid {
  display: grid;
  gap: 12px;
}

.compact-grid {
  gap: 10px;
}

.inline-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.info-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.info-item {
  background: #f9f9f9;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.info-item.full {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 10px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.info-value {
  font-size: 12px;
  color: #222;
  line-height: 1.6;
  word-break: break-word;
}

.input-field {
  width: 100%;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.5;
  outline: none;
  transition: border-color 0.2s;
  background: #fff;
}

.input-field:focus {
  border-color: #111;
}

.textarea-field {
  resize: vertical;
  min-height: 92px;
}

.upload-zone {
  border: 1px dashed #d7d7d7;
  border-radius: 8px;
  background: #fafafa;
  min-height: 132px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.upload-zone:hover {
  border-color: #111;
  background: #fff;
}

.upload-zone.has-files {
  justify-content: flex-start;
}

.hidden-input {
  display: none;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.upload-icon {
  font-size: 24px;
  color: #111;
}

.upload-title {
  font-size: 13px;
  font-weight: 700;
  color: #111;
}

.upload-hint {
  font-size: 11px;
  color: #999;
}

.files-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.file-chip {
  border: 1px solid #e0e0e0;
  background: #fff;
  color: #333;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #ff5722;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid #ffccbc;
  border-top-color: #ff5722;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.progress-number {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace;
  color: #666;
}

.inline-error {
  padding: 10px 12px;
  border-radius: 6px;
  background: #fff1f0;
  border: 1px solid #ffd9d6;
  color: #c62828;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-line;
}

.tags-container {
  transition: opacity 0.3s;
}

.tag-label {
  display: block;
  font-size: 10px;
  color: #aaa;
  margin-bottom: 8px;
  font-weight: 600;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-tag {
  background: #f5f5f5;
  border: 1px solid #eee;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  color: #333;
  font-family: 'JetBrains Mono', monospace;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  background: #f9f9f9;
  padding: 16px;
  border-radius: 6px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #000;
  font-family: 'JetBrains Mono', monospace;
}

.stat-label {
  font-size: 9px;
  color: #999;
  text-transform: uppercase;
  margin-top: 4px;
  display: block;
}

.action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.action-btn {
  width: 100%;
  background: #111;
  color: #fff;
  border: none;
  padding: 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.action-btn.secondary {
  background: #fff;
  color: #111;
  border: 1px solid #ddd;
}

.action-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.action-btn:disabled {
  background: #ccc;
  border-color: #ccc;
  color: #fff;
  cursor: not-allowed;
}

.system-logs {
  background: #000;
  color: #ddd;
  padding: 16px;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px solid #222;
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #333;
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 10px;
  color: #888;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 84px;
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time {
  color: #666;
  min-width: 75px;
}

.log-msg {
  color: #ccc;
  word-break: break-all;
}

@media (max-width: 1200px) {
  .header-center {
    display: none;
  }

  .header-right {
    gap: 10px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .selector-control {
    min-width: 140px;
  }
}

@media (max-width: 960px) {
  .main-view {
    height: auto;
    min-height: 100vh;
  }

  .app-header {
    height: auto;
    min-height: 60px;
    padding: 12px 16px;
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .header-center {
    position: static;
    transform: none;
    display: block;
    width: 100%;
  }

  .header-right {
    width: 100%;
    justify-content: flex-start;
  }

  .content-area {
    flex-direction: column;
  }

  .panel-wrapper,
  .panel-wrapper.left,
  .panel-wrapper.right {
    width: 100% !important;
    opacity: 1 !important;
    transform: none !important;
    border-right: none;
  }

  .panel-wrapper.left {
    border-bottom: 1px solid #eaeaea;
  }

  .graph-legend,
  .edge-labels-toggle {
    position: static;
    margin: 12px 16px 0;
  }

  .graph-container {
    min-height: 420px;
  }

  .detail-panel {
    left: 16px;
    right: 16px;
    width: auto;
  }

  .inline-grid,
  .stats-grid,
  .action-row,
  .info-grid,
  .project-grid {
    grid-template-columns: 1fr;
  }

  .task-module-toolbar,
  .card-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
