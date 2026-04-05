<template>
  <v-app theme="dark" class="bg-black text-white">
    <AppNavBar />
    
    <v-navigation-drawer
      v-model="drawer"
      app
      width="350"
      :permanent="$vuetify.display.mdAndUp"
    >
      <v-card flat>
        <v-card-title class="bg-primary">
          <v-icon class="mr-2">mdi-graph</v-icon>
          知识图谱浏览器
        </v-card-title>

        <v-divider></v-divider>

        <!-- 搜索人物 -->
        <v-card-text>
          <v-text-field
            v-model="searchQuery"
            label="搜索人物"
            prepend-inner-icon="mdi-magnify"
            variant="outlined"
            density="compact"
            clearable
            @keyup.enter="searchPerson"
          ></v-text-field>

          <v-btn
            color="primary"
            block
            @click="searchPerson"
            :loading="searching"
            :disabled="!searchQuery"
          >
            搜索
          </v-btn>

          <!-- 搜索结果 -->
          <v-list v-if="searchResults.length > 0" class="mt-3">
            <v-list-subheader>搜索结果</v-list-subheader>
            <v-list-item
              v-for="(person, index) in searchResults"
              :key="index"
              @click="loadSubgraph(person.eid)"
              :class="{ 'bg-blue-50': selectedSeed === person.eid }"
            >
              <v-list-item-title>{{ person.name }}</v-list-item-title>
              <v-list-item-subtitle class="text-truncate">{{ person.eid }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>

        <v-divider></v-divider>

        <!-- 图谱控制参数 -->
        <v-card-text>
          <v-expansion-panels>
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon class="mr-2">mdi-tune</v-icon>
                图谱参数
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-select
                  v-model="direction"
                  label="方向"
                  :items="directionOptions"
                  item-title="text"
                  item-value="value"
                  variant="outlined"
                  density="compact"
                ></v-select>

                <v-slider
                  v-model="depth"
                  label="深度"
                  :min="1"
                  :max="3"
                  :step="1"
                  thumb-label
                  show-ticks="always"
                  class="mt-3"
                ></v-slider>

                <v-slider
                  v-model="limitPaths"
                  label="路径限制"
                  :min="10"
                  :max="500"
                  :step="10"
                  thumb-label
                  show-ticks="always"
                  class="mt-3"
                ></v-slider>

                <v-switch
                  v-model="includeSnippet"
                  label="包含文本片段"
                  color="primary"
                  density="compact"
                ></v-switch>

                <v-btn
                  v-if="selectedSeed"
                  color="primary"
                  block
                  @click="loadSubgraph(selectedSeed)"
                  :loading="loading"
                  class="mt-2"
                >
                  重新加载
                </v-btn>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>

        <v-divider></v-divider>

        <!-- 图谱统计 -->
        <v-card-text v-if="graphStats.nodes > 0">
          <v-list density="compact">
            <v-list-subheader>图谱统计</v-list-subheader>
            <v-list-item>
              <v-list-item-title>节点数: {{ graphStats.nodes }}</v-list-item-title>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>边数: {{ graphStats.edges }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>
    </v-navigation-drawer>

    <!-- 右侧详情面板 -->
    <v-navigation-drawer
      v-model="detailDrawer"
      app
      location="right"
      width="400"
      temporary
    >
      <v-card flat>
        <v-card-title class="d-flex justify-space-between align-center">
          <span>节点详情</span>
          <v-btn icon="mdi-close" variant="text" @click="detailDrawer = false"></v-btn>
        </v-card-title>

        <v-divider></v-divider>

        <v-card-text v-if="selectedNode">
          <!-- Person 节点 -->
          <div v-if="selectedNode.labels.includes('Person')">
            <v-chip color="primary" class="mb-3">
              <v-icon start>mdi-account</v-icon>
              Person
            </v-chip>

            <v-list density="compact">
              <v-list-item
                v-for="(value, propKey) in selectedNode.properties"
                :key="propKey"
              >
                <v-list-item-title class="font-weight-bold">{{ propKey }}</v-list-item-title>
                <v-list-item-subtitle>{{ value }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>

            <v-btn
              color="primary"
              block
              class="mt-3"
              @click="expandNode(selectedNode.id)"
            >
              <v-icon start>mdi-graph-outline</v-icon>
              展开此节点
            </v-btn>
          </div>

          <!-- Chunk 节点 -->
          <div v-if="selectedNode.labels.includes('Chunk')">
            <v-chip color="secondary" class="mb-3">
              <v-icon start>mdi-text-box</v-icon>
              Chunk
            </v-chip>

            <v-list density="compact">
              <template v-for="(value, propKey2) in selectedNode.properties" :key="propKey2">
                <v-list-item v-if="propKey2 !== 'snippet'">
                  <v-list-item-title class="font-weight-bold">{{ propKey2 }}</v-list-item-title>
                  <v-list-item-subtitle>{{ value }}</v-list-item-subtitle>
                </v-list-item>
              </template>
            </v-list>

            <v-divider class="my-3"></v-divider>

            <!-- 文本片段 -->
            <div v-if="selectedNode.properties.snippet">
              <div class="text-subtitle-2 mb-2">文本片段:</div>
              <div class="text-body-2 pa-3 bg-grey-lighten-4 rounded">
                {{ selectedNode.properties.snippet }}...
              </div>
            </div>

            <v-btn
              color="primary"
              block
              class="mt-3"
              @click="loadChunkDetail(selectedNode.id)"
              :loading="loadingChunkDetail"
            >
              <v-icon start>mdi-text</v-icon>
              查看完整文本
            </v-btn>

            <!-- 完整文本 -->
            <div v-if="chunkDetail" class="mt-3">
              <v-divider class="mb-3"></v-divider>
              <div class="text-subtitle-2 mb-2">完整文本:</div>
              <div class="text-body-2 pa-3 bg-grey-lighten-4 rounded" style="max-height: 400px; overflow-y: auto;">
                {{ chunkDetail.text }}
              </div>
            </div>

            <v-btn
              color="secondary"
              block
              class="mt-3"
              @click="expandNode(selectedNode.id)"
            >
              <v-icon start>mdi-graph-outline</v-icon>
              展开此节点
            </v-btn>
          </div>
        </v-card-text>
      </v-card>
    </v-navigation-drawer>

    <!-- 主内容区域 -->
    <v-main>
      <div class="graph-container">
        <!-- 工具栏 -->
        <div class="graph-toolbar">
          <v-btn-group density="compact">
            <v-btn @click="fitGraph" title="适应画布">
              <v-icon>mdi-fit-to-screen</v-icon>
            </v-btn>
            <v-btn @click="centerGraph" title="居中">
              <v-icon>mdi-target</v-icon>
            </v-btn>
            <v-btn @click="resetGraph" title="重置">
              <v-icon>mdi-refresh</v-icon>
            </v-btn>
          </v-btn-group>

          <v-btn-group density="compact" class="ml-2">
            <v-btn @click="zoomIn" title="放大">
              <v-icon>mdi-magnify-plus</v-icon>
            </v-btn>
            <v-btn @click="zoomOut" title="缩小">
              <v-icon>mdi-magnify-minus</v-icon>
            </v-btn>
          </v-btn-group>

          <v-chip class="ml-4" v-if="loading">
            <v-progress-circular
              indeterminate
              size="16"
              width="2"
              class="mr-2"
            ></v-progress-circular>
            加载中...
          </v-chip>
        </div>

        <!-- Cytoscape 容器 -->
        <div ref="cytoscapeContainer" class="cytoscape-container"></div>

        <!-- 空状态 -->
        <div v-if="!loading && graphStats.nodes === 0" class="empty-state">
          <v-icon size="64" color="grey">mdi-graph-outline</v-icon>
          <div class="text-h6 mt-4 text-grey">请搜索人物开始探索知识图谱</div>
        </div>
      </div>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import cytoscape from 'cytoscape'
import type { Core, NodeSingular, EdgeSingular } from 'cytoscape'

// 类型定义
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

interface SearchResult {
  eid: string
  name: string
}

// 状态
const drawer = ref(true)
const detailDrawer = ref(false)
const searchQuery = ref('')
const searchResults = ref<SearchResult[]>([])
const searching = ref(false)
const loading = ref(false)
const loadingChunkDetail = ref(false)

// 图谱参数
const selectedSeed = ref<string>('')
const direction = ref('both')
const depth = ref(1)
const limitPaths = ref(200)
const includeSnippet = ref(true)

const directionOptions = [
  { text: '双向', value: 'both' },
  { text: '出边', value: 'out' },
  { text: '入边', value: 'in' },
]

// 图谱数据
const graphStats = ref({ nodes: 0, edges: 0 })
const selectedNode = ref<GraphNode | null>(null)
const chunkDetail = ref<any>(null)

// Cytoscape 实例
const cytoscapeContainer = ref<HTMLElement | null>(null)
let cy: Core | null = null

// API - 直接使用环境变量
const apiBase = 'http://127.0.0.1:8000'

// 搜索人物
const searchPerson = async () => {
  if (!searchQuery.value.trim()) return

  searching.value = true
  try {
    const response = await $fetch<SearchResult[]>(`${apiBase}/graph/search/person`, {
      params: { q: searchQuery.value, limit: 20 },
      credentials: 'include'
    })
    searchResults.value = response
  } catch (error: any) {
    console.error('搜索失败:', error)
    console.error('错误详情:', error.data || error.message)
    const errorMsg = error.data?.detail || error.message || '未知错误'
    alert(`搜索失败: ${errorMsg}`)
  } finally {
    searching.value = false
  }
}

// 加载子图
const loadSubgraph = async (seedEid: string) => {
  if (!seedEid) {
    alert('无效的节点 ID')
    return
  }

  selectedSeed.value = seedEid
  loading.value = true

  const requestBody = {
    seed_eid: seedEid,
    depth: depth.value,
    direction: direction.value,
    limit_paths: limitPaths.value,
    include_snippet: includeSnippet.value,
    snippet_len: 120,
  }

  console.log('请求子图参数:', requestBody)

  try {
    const response = await $fetch<GraphResponse>(`${apiBase}/graph/subgraph`, {
      method: 'POST',
      body: requestBody,
      credentials: 'include'
    })

    graphStats.value = {
      nodes: response.nodes.length,
      edges: response.edges.length,
    }

    renderGraph(response)
  } catch (error: any) {
    console.error('加载子图失败:', error)
    console.error('错误详情:', error.data || error.message)
    const errorMsg = error.data?.detail || error.message || '未知错误'
    alert(`加载子图失败: ${errorMsg}`)
  } finally {
    loading.value = false
  }
}

// 渲染图谱
const renderGraph = (data: GraphResponse) => {
  if (!cy) return

  // 转换数据格式为 Cytoscape 格式
  const elements = [
    ...data.nodes.map(node => ({
      data: {
        ...node,
        id: node.id,
        label: getNodeLabel(node),
      }
    })),
    ...data.edges.map(edge => ({
      data: {
        ...edge,
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.type,
      }
    }))
  ]

  cy.elements().remove()
  cy.add(elements)

  // 应用布局
  const layout = cy.layout({
    name: 'cose',
    animate: true,
    animationDuration: 500,
    nodeRepulsion: 8000,
    idealEdgeLength: 100,
    edgeElasticity: 100,
    nestingFactor: 5,
    gravity: 80,
    numIter: 1000,
    randomize: false,
    padding: 30,
  })
  
  layout.run()

  // 适应画布
  setTimeout(() => {
    cy?.fit(undefined, 50)
  }, 600)
}

// 获取节点标签
const getNodeLabel = (node: GraphNode): string => {
  if (node.labels.includes('Person')) {
    return node.properties.name || node.id
  } else if (node.labels.includes('Chunk')) {
    return `${node.properties.book_title || 'Chunk'}\n${node.properties.chapter_id || ''}`
  }
  return node.id
}

// 加载 Chunk 详情（现在使用 node.id 即 elementId）
const loadChunkDetail = async (nodeId: string) => {
  loadingChunkDetail.value = true
  try {
    const response = await $fetch<any>(`${apiBase}/graph/chunks/by-eid/${nodeId}`, {
      credentials: 'include'
    })
    chunkDetail.value = response
  } catch (error: any) {
    console.error('加载 Chunk 详情失败:', error)
    console.error('错误详情:', error.data || error.message)
    const errorMsg = error.data?.detail || error.message || '未知错误'
    alert(`加载详情失败: ${errorMsg}`)
  } finally {
    loadingChunkDetail.value = false
  }
}

// 展开节点（使用 elementId）
const expandNode = (nodeEid: string) => {
  loadSubgraph(nodeEid)
}

// 图谱控制
const fitGraph = () => {
  cy?.fit(undefined, 50)
}

const centerGraph = () => {
  cy?.center()
}

const resetGraph = () => {
  if (selectedSeed.value) {
    loadSubgraph(selectedSeed.value)
  }
}

const zoomIn = () => {
  cy?.zoom({
    level: cy.zoom() * 1.2,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
  })
}

const zoomOut = () => {
  cy?.zoom({
    level: cy.zoom() * 0.8,
    renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
  })
}

// 初始化 Cytoscape
onMounted(async () => {
  await nextTick()

  if (!cytoscapeContainer.value) return

  cy = cytoscape({
    container: cytoscapeContainer.value,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#0A7AFF',
          'label': 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'color': '#333',
          'text-outline-color': '#fff',
          'text-outline-width': 2,
          'font-size': '12px',
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
          'border-color': '#FFA500',
          'background-color': '#FFD700',
        }
      },
      {
        selector: 'node:active',
        style: {
          'overlay-opacity': 0.2,
          'overlay-color': '#000',
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
          'color': '#666',
          'text-outline-color': '#fff',
          'text-outline-width': 1,
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'line-color': '#FFA500',
          'target-arrow-color': '#FFA500',
          'width': 3,
        }
      }
    ],
    minZoom: 0.1,
    maxZoom: 3,
    wheelSensitivity: 0.2,
  })

  // 节点点击事件
  cy.on('tap', 'node', (event) => {
    const node = event.target
    const nodeData = node.data() as GraphNode
    selectedNode.value = nodeData
    chunkDetail.value = null
    detailDrawer.value = true
  })

  // 双击节点展开
  cy.on('dbltap', 'node', (event) => {
    const node = event.target
    const nodeId = node.data('id')
    expandNode(nodeId)
  })

  // 边点击事件
  cy.on('tap', 'edge', (event) => {
    const edge = event.target
    console.log('Edge clicked:', edge.data())
  })

  // 悬停效果
  cy.on('mouseover', 'node', (event) => {
    const node = event.target
    node.style('cursor', 'pointer')
  })

  cy.on('mouseout', 'node', (event) => {
    const node = event.target
    node.style('cursor', 'default')
  })
})

// 清理
onBeforeUnmount(() => {
  if (cy) {
    cy.destroy()
  }
})
</script>

<style scoped>
.graph-container {
  position: relative;
  width: 100%;
  height: 100vh;
  background: #f5f5f5;
}

.graph-toolbar {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 10;
  display: flex;
  align-items: center;
  background: white;
  padding: 8px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
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
</style>

