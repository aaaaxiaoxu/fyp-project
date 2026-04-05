<template>
  <v-app theme="dark" class="bg-black text-white">
    <AppNavBar />
    
    <v-banner
      color="purple-darken-1"
      icon="mdi-information"
      sticky
      class="mt-2"
    >
      <template #text>
        <span class="font-weight-bold">演示模式</span> - 使用模拟数据，无需后端连接
        <v-btn
          variant="text"
          size="small"
          class="ml-2"
          @click="$router.push('/graph')"
        >
          切换到真实版本
        </v-btn>
      </template>
    </v-banner>

    <v-main class="bg-black">
      <div class="graph-container">
        <!-- 工具栏 -->
        <div class="graph-toolbar">
          <v-btn-group density="compact">
            <v-btn @click="loadMockData" title="加载示例数据">
              <v-icon>mdi-database-refresh</v-icon>
            </v-btn>
            <v-btn @click="fitGraph" title="适应画布">
              <v-icon>mdi-fit-to-screen</v-icon>
            </v-btn>
            <v-btn @click="centerGraph" title="居中">
              <v-icon>mdi-target</v-icon>
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

          <v-chip class="ml-4">
            节点: {{ stats.nodes }} | 边: {{ stats.edges }}
          </v-chip>
        </div>

        <!-- Cytoscape 容器 -->
        <div ref="cytoscapeContainer" class="cytoscape-container"></div>

        <!-- 提示信息 -->
        <div class="demo-hint">
          <v-card class="pa-3">
            <v-card-text>
              <div class="text-subtitle-2 mb-2">📌 演示说明</div>
              <ul class="text-caption">
                <li>这是一个使用模拟数据的演示页面</li>
                <li>点击"加载示例数据"按钮加载示例图谱</li>
                <li>可以拖动节点、缩放画布</li>
                <li>双击节点可以高亮相邻节点</li>
              </ul>
            </v-card-text>
          </v-card>
        </div>
      </div>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import cytoscape from 'cytoscape'
import type { Core } from 'cytoscape'

const cytoscapeContainer = ref<HTMLElement | null>(null)
const stats = ref({ nodes: 0, edges: 0 })
let cy: Core | null = null

// 模拟数据
const getMockData = () => {
  return {
    nodes: [
      {
        id: 'Person:1',
        labels: ['Person'],
        properties: { id: 1, name: '孙少平', age: 23, gender: '男' }
      },
      {
        id: 'Person:2',
        labels: ['Person'],
        properties: { id: 2, name: '田晓霞', age: 22, gender: '女' }
      },
      {
        id: 'Person:3',
        labels: ['Person'],
        properties: { id: 3, name: '孙少安', age: 28, gender: '男' }
      },
      {
        id: 'Person:4',
        labels: ['Person'],
        properties: { id: 4, name: '田润叶', age: 25, gender: '女' }
      },
      {
        id: 'Person:5',
        labels: ['Person'],
        properties: { id: 5, name: '金波', age: 23, gender: '男' }
      },
      {
        id: 'Chunk:ch001',
        labels: ['Chunk'],
        properties: {
          chunk_id: 'ch001',
          chapter_id: '第一章',
          book_title: '平凡的世界',
          snippet: '孙少平是一个贫困的农村青年，在高中时期...'
        }
      },
      {
        id: 'Chunk:ch002',
        labels: ['Chunk'],
        properties: {
          chunk_id: 'ch002',
          chapter_id: '第二章',
          book_title: '平凡的世界',
          snippet: '田晓霞是一个热情开朗的城市姑娘，与孙少平在学校相识...'
        }
      },
      {
        id: 'Chunk:ch003',
        labels: ['Chunk'],
        properties: {
          chunk_id: 'ch003',
          chapter_id: '第三章',
          book_title: '平凡的世界',
          snippet: '孙少安是孙少平的哥哥，早早辍学回家务农...'
        }
      },
    ],
    edges: [
      {
        id: 'edge1',
        type: '恋人',
        source: 'Person:1',
        target: 'Person:2',
        properties: { since: '1975' }
      },
      {
        id: 'edge2',
        type: '兄弟',
        source: 'Person:1',
        target: 'Person:3',
        properties: { relation: '血缘' }
      },
      {
        id: 'edge3',
        type: '朋友',
        source: 'Person:1',
        target: 'Person:5',
        properties: { closeness: '高' }
      },
      {
        id: 'edge4',
        type: '暗恋',
        source: 'Person:4',
        target: 'Person:3',
        properties: { unrequited: true }
      },
      {
        id: 'edge5',
        type: '出现在',
        source: 'Person:1',
        target: 'Chunk:ch001',
        properties: {}
      },
      {
        id: 'edge6',
        type: '出现在',
        source: 'Person:2',
        target: 'Chunk:ch002',
        properties: {}
      },
      {
        id: 'edge7',
        type: '出现在',
        source: 'Person:3',
        target: 'Chunk:ch003',
        properties: {}
      },
      {
        id: 'edge8',
        type: '提及',
        source: 'Chunk:ch001',
        target: 'Person:3',
        properties: {}
      },
    ]
  }
}

// 加载模拟数据
const loadMockData = () => {
  if (!cy) return

  const data = getMockData()
  
  const elements = [
    ...data.nodes.map(node => ({
      data: {
        id: node.id,
        label: getNodeLabel(node),
        ...node,
      }
    })),
    ...data.edges.map(edge => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.type,
        ...edge,
      }
    }))
  ]

  cy.elements().remove()
  cy.add(elements)

  stats.value = {
    nodes: data.nodes.length,
    edges: data.edges.length,
  }

  // 应用布局
  cy.layout({
    name: 'cose',
    animate: true,
    animationDuration: 500,
    nodeRepulsion: 8000,
    idealEdgeLength: 120,
    edgeElasticity: 100,
    nestingFactor: 5,
    gravity: 80,
    numIter: 1000,
    randomize: false,
    padding: 50,
  }).run()

  setTimeout(() => {
    cy?.fit(undefined, 50)
  }, 600)
}

// 获取节点标签
const getNodeLabel = (node: any): string => {
  if (node.labels.includes('Person')) {
    return node.properties.name || node.id
  } else if (node.labels.includes('Chunk')) {
    return `${node.properties.book_title}\n${node.properties.chapter_id}`
  }
  return node.id
}

// 图谱控制
const fitGraph = () => {
  cy?.fit(undefined, 50)
}

const centerGraph = () => {
  cy?.center()
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
          'color': '#fff',
          'text-outline-color': '#000',
          'text-outline-width': 2,
          'font-size': '14px',
          'font-weight': 'bold',
          'width': '70px',
          'height': '70px',
          'text-wrap': 'wrap',
          'text-max-width': '90px',
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
          'border-width': 4,
          'border-color': '#FFA500',
          'background-color': '#FFD700',
        }
      },
      {
        selector: 'node.highlighted',
        style: {
          'border-width': 3,
          'border-color': '#00FF00',
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 3,
          'line-color': '#999',
          'target-arrow-color': '#999',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '12px',
          'text-rotation': 'autorotate',
          'text-margin-y': -12,
          'color': '#fff',
          'text-outline-color': '#000',
          'text-outline-width': 2,
          'font-weight': 'bold',
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'line-color': '#FFA500',
          'target-arrow-color': '#FFA500',
          'width': 4,
        }
      },
      {
        selector: 'edge.highlighted',
        style: {
          'line-color': '#00FF00',
          'target-arrow-color': '#00FF00',
          'width': 4,
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
    console.log('Node clicked:', node.data())
  })

  // 双击节点高亮相邻节点
  cy.on('dbltap', 'node', (event) => {
    const node = event.target
    
    // 移除之前的高亮
    cy.elements().removeClass('highlighted')
    
    // 高亮当前节点和相邻元素
    node.addClass('highlighted')
    node.connectedEdges().addClass('highlighted')
    node.neighborhood('node').addClass('highlighted')
  })

  // 点击空白处取消高亮
  cy.on('tap', (event) => {
    if (event.target === cy) {
      cy.elements().removeClass('highlighted')
    }
  })

  // 自动加载示例数据
  loadMockData()
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
  height: calc(100vh - 80px);
  background: #1a1a1a;
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

.demo-hint {
  position: absolute;
  bottom: 16px;
  right: 16px;
  z-index: 10;
  max-width: 300px;
}
</style>

