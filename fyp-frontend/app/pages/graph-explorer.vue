<template>
  <v-app theme="dark" class="bg-black text-white">
    <AppNavBar />
    
    <!-- 左侧栏：目录 -->
    <v-navigation-drawer
      v-model="leftDrawer"
      app
      width="320"
      :permanent="$vuetify.display.mdAndUp"
      class="bg-grey-darken-4"
    >
      <v-card flat class="bg-transparent">
        <v-card-title class="text-h6 pa-4">
          <v-icon class="mr-2">mdi-folder-open</v-icon>
          实体目录
        </v-card-title>

        <!-- 统计信息 -->
        <v-card-text v-if="catalog" class="pb-2">
          <v-chip size="small" class="mr-2">
            <v-icon start size="small">mdi-account</v-icon>
            {{ catalog.person_count }}
          </v-chip>
          <v-chip size="small">
            <v-icon start size="small">mdi-calendar-star</v-icon>
            {{ catalog.event_count }}
          </v-chip>
        </v-card-text>

        <v-divider></v-divider>

        <!-- Tab 切换 -->
        <v-tabs v-model="activeTab" bg-color="transparent" grow>
          <v-tab value="Person">
            <v-icon start>mdi-account</v-icon>
            人物
          </v-tab>
          <v-tab value="Event">
            <v-icon start>mdi-calendar-star</v-icon>
            事件
          </v-tab>
        </v-tabs>

        <v-divider></v-divider>

        <!-- 搜索框 -->
        <v-card-text class="pb-2">
          <v-text-field
            v-model="searchQuery"
            label="搜索"
            prepend-inner-icon="mdi-magnify"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          ></v-text-field>
        </v-card-text>

        <!-- 排序 -->
        <v-card-text class="pt-2">
          <v-select
            v-model="sortBy"
            :items="sortOptions"
            label="排序"
            variant="outlined"
            density="compact"
            hide-details
          ></v-select>
        </v-card-text>

        <v-divider></v-divider>

        <!-- 实体列表 -->
        <v-list
          class="bg-transparent"
          style="max-height: calc(100vh - 400px); overflow-y: auto;"
        >
          <template v-if="loadingEntities && entities.length === 0">
            <v-list-item>
              <v-progress-circular indeterminate size="24"></v-progress-circular>
              <span class="ml-3">加载中...</span>
            </v-list-item>
          </template>

          <template v-else-if="entities.length === 0">
            <v-list-item>
              <v-list-item-title class="text-grey">暂无数据</v-list-item-title>
            </v-list-item>
          </template>

          <template v-else>
            <v-list-item
              v-for="entity in entities"
              :key="entity.eid"
              @click="loadSubgraphFromEntity(entity.eid)"
              :active="selectedEntityEid === entity.eid"
              class="cursor-pointer"
            >
              <v-list-item-title>{{ entity.name }}</v-list-item-title>
              <v-list-item-subtitle class="text-caption">
                <v-chip size="x-small" class="mr-1">{{ entity.score }}</v-chip>
                <span v-if="entity.first_seen_chapter">{{ entity.first_seen_chapter }}</span>
              </v-list-item-subtitle>
            </v-list-item>
          </template>
        </v-list>

        <!-- 加载更多 -->
        <v-card-actions v-if="entities.length > 0">
          <v-btn
            block
            variant="text"
            @click="loadMoreEntities(activeTab, searchQuery, sortBy)"
            :loading="loadingEntities"
            :disabled="!hasMoreEntities"
          >
            {{ hasMoreEntities ? '加载更多' : '没有更多了' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-navigation-drawer>

    <!-- 右侧栏：详情面板 -->
    <v-navigation-drawer
      v-model="rightDrawer"
      app
      location="right"
      width="400"
      temporary
      class="bg-grey-darken-4"
    >
      <v-card flat class="bg-transparent">
        <v-card-title class="d-flex justify-space-between align-center">
          <span>节点详情</span>
          <v-btn icon variant="text" @click="rightDrawer = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <v-divider></v-divider>

        <v-card-text v-if="selectedNodeDetail">
          <!-- 标签 -->
          <div class="mb-3">
            <v-chip
              v-for="label in selectedNodeDetail.labels"
              :key="label"
              size="small"
              class="mr-1"
              :color="label === 'Person' ? 'red' : label === 'Event' ? 'orange' : 'cyan'"
            >
              {{ label }}
            </v-chip>
          </div>

          <!-- 属性 -->
          <v-expansion-panels>
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon start>mdi-information</v-icon>
                属性
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-list density="compact" class="bg-transparent">
                  <v-list-item
                    v-for="(value, key) in selectedNodeDetail.properties"
                    :key="key"
                  >
                    <v-list-item-title class="text-caption font-weight-bold">
                      {{ key }}
                    </v-list-item-title>
                    <v-list-item-subtitle class="text-caption">
                      {{ value }}
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <!-- Evidence 列表 -->
          <div class="mt-4">
            <div class="text-subtitle-2 mb-2 d-flex align-center">
              <v-icon start size="small">mdi-text-box-multiple</v-icon>
              证据列表
            </div>

            <template v-if="loadingEvidence">
              <v-progress-circular indeterminate size="24"></v-progress-circular>
            </template>

            <template v-else-if="evidenceList.length === 0">
              <div class="text-caption text-grey">暂无证据</div>
            </template>

            <template v-else>
              <v-list density="compact" class="bg-transparent">
                <v-list-item
                  v-for="evidence in evidenceList"
                  :key="evidence.chunk_eid"
                  @click="viewChunkText(evidence.chunk_eid)"
                  class="cursor-pointer mb-2 rounded bg-grey-darken-3"
                >
                  <v-list-item-title class="text-caption mb-1">
                    <v-chip size="x-small" class="mr-1">{{ evidence.chapter_id }}</v-chip>
                  </v-list-item-title>
                  <v-list-item-subtitle class="text-caption">
                    {{ evidence.snippet }}...
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </template>
          </div>

          <!-- 展开节点按钮 -->
          <v-btn
            block
            color="primary"
            class="mt-4"
            @click="expandNode(selectedNodeDetail.eid)"
          >
            <v-icon start>mdi-graph-outline</v-icon>
            展开此节点
          </v-btn>
        </v-card-text>
      </v-card>
    </v-navigation-drawer>

    <!-- 主内容区：Cytoscape 画布 -->
    <v-main class="bg-black">
      <div class="graph-container">
        <!-- 工具栏 -->
        <div class="graph-toolbar">
          <v-btn-group density="compact">
            <v-btn @click="fitGraph" size="small" title="适应画布">
              <v-icon>mdi-fit-to-screen</v-icon>
            </v-btn>
            <v-btn @click="centerGraph" size="small" title="居中">
              <v-icon>mdi-target</v-icon>
            </v-btn>
            <v-btn @click="resetGraph" size="small" title="重置">
              <v-icon>mdi-refresh</v-icon>
            </v-btn>
          </v-btn-group>

          <v-btn-group density="compact" class="ml-2">
            <v-btn @click="zoomIn" size="small" title="放大">
              <v-icon>mdi-magnify-plus</v-icon>
            </v-btn>
            <v-btn @click="zoomOut" size="small" title="缩小">
              <v-icon>mdi-magnify-minus</v-icon>
            </v-btn>
          </v-btn-group>

          <v-chip v-if="loadingGraph" class="ml-4" size="small">
            <v-progress-circular indeterminate size="16" width="2" class="mr-2"></v-progress-circular>
            加载中...
          </v-chip>

          <v-chip v-if="graphStats.nodes > 0" class="ml-4" size="small">
            节点: {{ graphStats.nodes }} | 边: {{ graphStats.edges }}
          </v-chip>
        </div>

        <!-- Cytoscape 容器 -->
        <div ref="cytoscapeContainer" class="cytoscape-container"></div>

        <!-- 空状态 -->
        <div v-if="!loadingGraph && graphStats.nodes === 0" class="empty-state">
          <v-icon size="64" color="grey-darken-1">mdi-graph-outline</v-icon>
          <div class="text-h6 mt-4 text-grey-darken-1">点击左侧实体开始探索图谱</div>
        </div>
      </div>
    </v-main>

    <!-- Chunk 全文弹窗 -->
    <v-dialog v-model="chunkDialog" max-width="800" scrollable>
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center">
          <span>文本详情</span>
          <v-btn icon variant="text" @click="chunkDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <v-divider></v-divider>

        <v-card-text style="max-height: 600px;">
          <template v-if="loadingChunk">
            <v-progress-circular indeterminate></v-progress-circular>
          </template>

          <template v-else-if="chunkDetail">
            <div class="mb-3">
              <v-chip size="small" class="mr-2">{{ chunkDetail.book_title }}</v-chip>
              <v-chip size="small">{{ chunkDetail.chapter_id }}</v-chip>
            </div>
            <div class="text-body-2 pa-3 bg-grey-lighten-4 rounded" style="white-space: pre-wrap;">
              {{ chunkDetail.text }}
            </div>
          </template>

          <template v-else-if="chunkError">
            <v-alert type="error">{{ chunkError }}</v-alert>
          </template>
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-app>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import cytoscape from 'cytoscape'
import type { Core } from 'cytoscape'

// ==================== 类型定义 ====================
interface Catalog {
  person_count: number
  event_count: number
}

interface Entity {
  eid: string
  label: string
  name: string
  score?: number
  first_seen_chapter?: string
}

interface GraphNode {
  id: string
  labels: string[]
  properties: Record<string, any>
}

interface GraphEdge {
  id: string
  type: string
  source: string
  target: string
  properties: Record<string, any>
}

interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

interface NodeDetail {
  eid: string
  labels: string[]
  properties: Record<string, any>
}

interface Evidence {
  chunk_eid: string
  chunk_id: string
  chapter_id: string
  start_char: number
  end_char: number
  snippet: string
}

interface ChunkDetail {
  chunk_id: string
  book_title: string
  chapter_id: string
  text: string
}

// ==================== Composables ====================

// 1. useCatalog - 获取统计信息
function useCatalog() {
  const catalog = ref<Catalog | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchCatalog = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await $fetch<Catalog>(`${apiBase}/graph/catalog`, {
        credentials: 'include'
      })
      catalog.value = response
    } catch (e: any) {
      error.value = e.message || '获取目录失败'
      console.error('获取目录失败:', e)
    } finally {
      loading.value = false
    }
  }

  return { catalog, loading, error, fetchCatalog }
}

// 2. useEntityList - 实体列表
function useEntityList() {
  const entities = ref<Entity[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const offset = ref(0)
  const limit = 50
  const hasMore = ref(true)

  const fetchEntities = async (
    label: string,
    query: string,
    sort: string,
    reset = false
  ) => {
    if (reset) {
      offset.value = 0
      entities.value = []
      hasMore.value = true
    }

    loading.value = true
    error.value = null
    try {
      const params: any = {
        label,
        limit,
        offset: offset.value,
        sort,
      }
      if (query) {
        params.q = query
      }

      const response = await $fetch<{ items: Entity[] }>(
        `${apiBase}/graph/entities`,
        {
          params,
          credentials: 'include'
        }
      )

      if (reset) {
        entities.value = response.items
      } else {
        entities.value.push(...response.items)
      }

      hasMore.value = response.items.length === limit
      offset.value += response.items.length
    } catch (e: any) {
      error.value = e.message || '获取实体列表失败'
      console.error('获取实体列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  const loadMore = async (label: string, query: string, sort: string) => {
    if (!hasMore.value || loading.value) return
    await fetchEntities(label, query, sort, false)
  }

  return { entities, loading, error, hasMore, fetchEntities, loadMore }
}

// 3. useGraph - Cytoscape 图谱
function useGraph(container: Ref<HTMLElement | null>) {
  const cy = ref<Core | null>(null)
  const nodes = ref<GraphNode[]>([])
  const edges = ref<GraphEdge[]>([])
  const selectedNode = ref<string | null>(null)
  const loading = ref(false)

  const initCytoscape = async () => {
    await nextTick()
    if (!container.value) return

    cy.value = cytoscape({
      container: container.value,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#4A90E2',
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#fff',
            'text-outline-color': '#000',
            'text-outline-width': 2,
            'font-size': '12px',
            'font-weight': 'bold',
            'width': '60px',
            'height': '60px',
            'text-wrap': 'wrap',
            'text-max-width': '80px',
          }
        },
        {
          selector: 'node[labels *= "Person"]',
          style: {
            'background-color': '#FF6B6B',
            'shape': 'ellipse',
          }
        },
        {
          selector: 'node[labels *= "Event"]',
          style: {
            'background-color': '#FFA500',
            'shape': 'round-diamond',
          }
        },
        {
          selector: 'node[labels *= "Chunk"]',
          style: {
            'background-color': '#4ECDC4',
            'shape': 'round-rectangle',
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#FFD700',
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#999',
            'target-arrow-color': '#999',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '10px',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'color': '#fff',
            'text-outline-color': '#000',
            'text-outline-width': 1,
          }
        },
      ],
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    })
  }

  const mergeElements = (newNodes: GraphNode[], newEdges: GraphEdge[]) => {
    if (!cy.value) return

    const nodeMap = new Map(nodes.value.map(n => [n.id, n]))
    const edgeMap = new Map(edges.value.map(e => [e.id, e]))

    // 合并节点
    newNodes.forEach(node => {
      if (!nodeMap.has(node.id)) {
        nodeMap.set(node.id, node)
      }
    })

    // 合并边
    newEdges.forEach(edge => {
      if (!edgeMap.has(edge.id)) {
        edgeMap.set(edge.id, edge)
      }
    })

    nodes.value = Array.from(nodeMap.values())
    edges.value = Array.from(edgeMap.values())

    // 渲染
    renderGraph()
  }

  const renderGraph = () => {
    if (!cy.value) return

    const elements = [
      ...nodes.value.map(node => ({
        data: {
          ...node,
          id: node.id,
          label: getNodeLabel(node),
        }
      })),
      ...edges.value.map(edge => ({
        data: {
          ...edge,
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.type,
        }
      }))
    ]

    cy.value.elements().remove()
    cy.value.add(elements)

    cy.value.layout({
      name: 'cose',
      animate: true,
      animationDuration: 500,
      nodeRepulsion: 8000,
      idealEdgeLength: 100,
      edgeElasticity: 100,
      gravity: 80,
      numIter: 1000,
      padding: 30,
    }).run()

    setTimeout(() => {
      cy.value?.fit(undefined, 50)
    }, 600)
  }

  const getNodeLabel = (node: GraphNode): string => {
    if (node.properties.name) return node.properties.name
    if (node.properties.title) return node.properties.title
    if (node.labels && node.labels.length > 0) {
      const eidParts = node.id.split(':')
      const shortId = eidParts[eidParts.length - 1]
      return `${node.labels[0]}:${shortId}`
    }
    return node.id
  }

  const fetchSubgraph = async (seedEid: string, merge = true) => {
    loading.value = true
    try {
      const response = await $fetch<GraphResponse>(`${apiBase}/graph/subgraph`, {
        method: 'POST',
        body: {
          seed_eid: seedEid,
          depth: 1,
          direction: 'both',
          limit_paths: 200,
          include_snippet: true,
        },
        credentials: 'include'
      })

      if (merge) {
        mergeElements(response.nodes, response.edges)
      } else {
        nodes.value = response.nodes
        edges.value = response.edges
        renderGraph()
      }
    } catch (e: any) {
      console.error('加载子图失败:', e)
      alert('加载子图失败: ' + (e.message || '未知错误'))
    } finally {
      loading.value = false
    }
  }

  const fit = () => cy.value?.fit(undefined, 50)
  const center = () => cy.value?.center()
  const reset = () => {
    nodes.value = []
    edges.value = []
    cy.value?.elements().remove()
  }
  const zoomIn = () => {
    if (!cy.value) return
    cy.value.zoom({
      level: cy.value.zoom() * 1.2,
      renderedPosition: { x: cy.value.width() / 2, y: cy.value.height() / 2 }
    })
  }
  const zoomOut = () => {
    if (!cy.value) return
    cy.value.zoom({
      level: cy.value.zoom() * 0.8,
      renderedPosition: { x: cy.value.width() / 2, y: cy.value.height() / 2 }
    })
  }

  return {
    cy,
    nodes,
    edges,
    selectedNode,
    loading,
    initCytoscape,
    fetchSubgraph,
    fit,
    center,
    reset,
    zoomIn,
    zoomOut,
  }
}

// 4. useNodeDetail - 节点详情和 evidence
function useNodeDetail() {
  const detail = ref<NodeDetail | null>(null)
  const evidence = ref<Evidence[]>([])
  const loadingDetail = ref(false)
  const loadingEvidence = ref(false)
  const error = ref<string | null>(null)

  const fetchNodeDetail = async (eid: string) => {
    loadingDetail.value = true
    error.value = null
    try {
      const response = await $fetch<NodeDetail>(`${apiBase}/graph/node/by-eid/${eid}`, {
        credentials: 'include'
      })
      detail.value = response
    } catch (e: any) {
      error.value = e.message || '获取节点详情失败'
      console.error('获取节点详情失败:', e)
    } finally {
      loadingDetail.value = false
    }
  }

  const fetchEvidence = async (eid: string) => {
    loadingEvidence.value = true
    try {
      const response = await $fetch<{ items: Evidence[] }>(
        `${apiBase}/graph/evidence`,
        {
          params: { eid, limit: 100, snippet_len: 120 },
          credentials: 'include'
        }
      )
      evidence.value = response.items
    } catch (e: any) {
      console.error('获取 evidence 失败:', e)
      evidence.value = []
    } finally {
      loadingEvidence.value = false
    }
  }

  const loadNodeAndEvidence = async (eid: string) => {
    await Promise.all([
      fetchNodeDetail(eid),
      fetchEvidence(eid)
    ])
  }

  return {
    detail,
    evidence,
    loadingDetail,
    loadingEvidence,
    error,
    loadNodeAndEvidence,
  }
}

// ==================== 页面状态 ====================
const apiBase = 'http://127.0.0.1:8000'

// UI 状态
const leftDrawer = ref(true)
const rightDrawer = ref(false)
const chunkDialog = ref(false)

// Tab 和筛选
const activeTab = ref('Person')
const searchQuery = ref('')
const sortBy = ref('score')
const sortOptions = [
  { title: '评分', value: 'score' },
  { title: '名称', value: 'name' },
  { title: '首次出现', value: 'first_seen' },
]

// Cytoscape
const cytoscapeContainer = ref<HTMLElement | null>(null)
const graphStats = ref({ nodes: 0, edges: 0 })
const selectedEntityEid = ref<string | null>(null)

// Chunk 详情
const chunkDetail = ref<ChunkDetail | null>(null)
const loadingChunk = ref(false)
const chunkError = ref<string | null>(null)

// 使用 composables
const { catalog, fetchCatalog } = useCatalog()
const {
  entities,
  loading: loadingEntities,
  hasMore: hasMoreEntities,
  fetchEntities,
  loadMore: loadMoreEntities,
} = useEntityList()

const {
  cy,
  nodes: graphNodes,
  edges: graphEdges,
  loading: loadingGraph,
  initCytoscape,
  fetchSubgraph,
  fit: fitGraph,
  center: centerGraph,
  reset: resetGraph,
  zoomIn,
  zoomOut,
} = useGraph(cytoscapeContainer)

const {
  detail: selectedNodeDetail,
  evidence: evidenceList,
  loadingDetail: loadingNodeDetail,
  loadingEvidence,
  loadNodeAndEvidence,
} = useNodeDetail()

// ==================== 方法 ====================

// 搜索防抖
let searchDebounceTimer: any = null
watch([activeTab, searchQuery, sortBy], () => {
  clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => {
    fetchEntities(activeTab.value, searchQuery.value, sortBy.value, true)
  }, 300)
})

// 从实体列表加载子图
const loadSubgraphFromEntity = async (eid: string) => {
  selectedEntityEid.value = eid
  await fetchSubgraph(eid, false)
}

// 查看 Chunk 全文
const viewChunkText = async (chunkEid: string) => {
  chunkDialog.value = true
  loadingChunk.value = true
  chunkError.value = null
  chunkDetail.value = null

  try {
    const response = await $fetch<ChunkDetail>(
      `${apiBase}/graph/chunks/by-eid/${chunkEid}`,
      { credentials: 'include' }
    )
    chunkDetail.value = response
  } catch (e: any) {
    chunkError.value = e.message || '加载文本失败'
    console.error('加载 chunk 失败:', e)
  } finally {
    loadingChunk.value = false
  }
}

// 展开节点（双击或按钮）
const expandNode = async (eid: string) => {
  const confirmed = confirm('确认要展开此节点吗？这将合并新的节点和边到当前图谱中。')
  if (!confirmed) return
  await fetchSubgraph(eid, true)
}

// 更新图谱统计
watch([graphNodes, graphEdges], () => {
  graphStats.value = {
    nodes: graphNodes.value.length,
    edges: graphEdges.value.length,
  }
})

// ==================== 生命周期 ====================
onMounted(async () => {
  // 初始化
  await fetchCatalog()
  await fetchEntities(activeTab.value, searchQuery.value, sortBy.value, true)
  await initCytoscape()

  // 绑定 Cytoscape 事件
  if (cy.value) {
    // 单击节点：显示详情
    cy.value.on('tap', 'node', async (event) => {
      const node = event.target
      const eid = node.data('id')
      await loadNodeAndEvidence(eid)
      rightDrawer.value = true
    })

    // 双击节点：展开
    cy.value.on('dbltap', 'node', async (event) => {
      const node = event.target
      const eid = node.data('id')
      await expandNode(eid)
    })
  }
})

onBeforeUnmount(() => {
  if (cy.value) {
    cy.value.destroy()
  }
})
</script>

<style scoped>
.graph-container {
  position: relative;
  width: 100%;
  height: 100vh;
  background: #0a0a0a;
}

.graph-toolbar {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 10;
  display: flex;
  align-items: center;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
  padding: 8px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.cytoscape-container {
  width: 100%;
  height: 100%;
}

.empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}

.cursor-pointer {
  cursor: pointer;
}
</style>

