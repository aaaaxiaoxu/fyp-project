<template>
  <div class="relative h-full min-h-[420px] overflow-hidden bg-transparent">
    <div
      v-if="!nodes.length"
      class="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center text-sm text-slate-500"
    >
      <div class="text-base font-semibold text-slate-700">Graph canvas is waiting for data</div>
      <p class="max-w-sm text-xs leading-6 text-slate-500">
        Build a graph for the selected project, then explore nodes and edges here.
      </p>
    </div>

    <div ref="containerRef" class="h-full w-full" :class="{ 'opacity-0': !nodes.length }"></div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

type LayoutName = 'cose' | 'breadthfirst' | 'circle'

type GraphNode = {
  uuid: string
  name: string
  labels: string[]
  summary: string
  attributes: Record<string, unknown>
}

type GraphEdge = {
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

type GraphSelection =
  | {
      type: 'node'
      data: GraphNode
    }
  | {
      type: 'edge'
      data: GraphEdge
    }
  | null

const props = withDefaults(
  defineProps<{
    nodes: GraphNode[]
    edges: GraphEdge[]
    layoutName?: LayoutName
  }>(),
  {
    layoutName: 'cose',
  },
)

const emit = defineEmits<{
  select: [selection: GraphSelection]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
let cyInstance: any = null
let resizeObserver: ResizeObserver | null = null

function buildNodeColor(label: string | undefined): { background: string; line: string; text: string } {
  const palette: Record<string, { background: string; line: string; text: string }> = {
    // generic semantic types
    Character: { background: '#ff8a65', line: '#ff5722', text: '#111827' },
    Person: { background: '#ff8a65', line: '#ff5722', text: '#111827' },
    Organization: { background: '#64b5f6', line: '#1e88e5', text: '#111827' },
    Location: { background: '#4db6ac', line: '#00897b', text: '#111827' },
    Event: { background: '#ba68c8', line: '#8e24aa', text: '#111827' },
    Concept: { background: '#b0bec5', line: '#607d8b', text: '#111827' },
    // social simulation entity types from ontology generator
    Villager: { background: '#ffcc80', line: '#fb8c00', text: '#111827' },
    Cadre: { background: '#ef9a9a', line: '#e53935', text: '#111827' },
    Commune: { background: '#90caf9', line: '#1e88e5', text: '#111827' },
    ProductionTeam: { background: '#80cbc4', line: '#00897b', text: '#111827' },
    Family: { background: '#ce93d8', line: '#8e24aa', text: '#111827' },
    School: { background: '#80deea', line: '#00acc1', text: '#111827' },
    Student: { background: '#9fa8da', line: '#3949ab', text: '#111827' },
    MediaOutlet: { background: '#d1c4e9', line: '#7e57c2', text: '#111827' },
    Government: { background: '#ffab91', line: '#f4511e', text: '#111827' },
    Community: { background: '#a5d6a7', line: '#43a047', text: '#111827' },
  }

  return palette[label || ''] || {
    background: '#cfd8dc',
    line: '#78909c',
    text: '#111827',
  }
}

async function renderGraph() {
  if (!import.meta.client) {
    return
  }

  if (!containerRef.value) {
    return
  }

  if (!props.nodes.length) {
    destroyGraph()
    return
  }

  const [{ default: cytoscape }] = await Promise.all([import('cytoscape')])

  const nodeIds = new Set(props.nodes.map((node) => node.uuid))
  const elements = [
    ...props.nodes.map((node) => {
      const primaryLabel = node.labels[0]
      const colors = buildNodeColor(primaryLabel)
      return {
        data: {
          id: node.uuid,
          label: node.name,
          summary: node.summary,
          primaryLabel,
          raw: node,
          backgroundColor: colors.background,
          borderColor: colors.line,
          textColor: colors.text,
        },
      }
    }),
    ...props.edges
      .filter((edge) => nodeIds.has(edge.source_node_uuid) && nodeIds.has(edge.target_node_uuid))
      .map((edge) => ({
        data: {
          id: edge.uuid,
          source: edge.source_node_uuid,
          target: edge.target_node_uuid,
          label: edge.name || edge.fact_type || 'relation',
          fact: edge.fact,
          raw: edge,
        },
      })),
  ]

  destroyGraph()

  cyInstance = cytoscape({
    container: containerRef.value,
    elements,
    wheelSensitivity: 0.18,
    minZoom: 0.25,
    maxZoom: 2.5,
    layout: {
      name: props.layoutName,
      animate: true,
      fit: true,
      padding: 52,
      randomize: false,
      nodeRepulsion: 140000,
      idealEdgeLength: 170,
      edgeElasticity: 80,
      nestingFactor: 0.75,
    },
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(backgroundColor)',
          'border-width': 2,
          'border-color': 'data(borderColor)',
          label: 'data(label)',
          color: 'data(textColor)',
          'font-size': 12,
          'font-weight': 700,
          'text-wrap': 'wrap',
          'text-max-width': 120,
          'text-valign': 'center',
          'text-halign': 'center',
          'overlay-padding': 8,
          'overlay-opacity': 0,
          width: 'label',
          height: 'label',
          padding: '22px',
        },
      },
      {
        selector: 'edge',
        style: {
          width: 2,
          'curve-style': 'bezier',
          'line-color': '#9ca3af',
          'target-arrow-color': '#9ca3af',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.8,
          label: 'data(label)',
          color: '#4b5563',
          'font-size': 10,
          'text-background-color': '#ffffff',
          'text-background-opacity': 0.96,
          'text-background-padding': 3,
          'text-rotation': 'autorotate',
          'text-margin-y': -10,
          'overlay-opacity': 0,
        },
      },
      {
        selector: ':selected',
        style: {
          'border-width': 4,
          'border-color': '#111827',
          'line-color': '#111827',
          'target-arrow-color': '#111827',
        },
      },
    ],
  })

  cyInstance.on('tap', 'node', (event: any) => {
    emit('select', {
      type: 'node',
      data: event.target.data('raw') as GraphNode,
    })
  })

  cyInstance.on('tap', 'edge', (event: any) => {
    emit('select', {
      type: 'edge',
      data: event.target.data('raw') as GraphEdge,
    })
  })

  cyInstance.on('tap', (event: any) => {
    if (event.target === cyInstance) {
      emit('select', null)
    }
  })

  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      cyInstance?.resize()
      cyInstance?.fit(undefined, 48)
    })
    resizeObserver.observe(containerRef.value)
  }
}

function destroyGraph() {
  resizeObserver?.disconnect()
  resizeObserver = null

  if (cyInstance) {
    cyInstance.destroy()
    cyInstance = null
  }
}

watch(
  () => [props.nodes, props.edges, props.layoutName],
  async () => {
    await renderGraph()
  },
  { deep: true },
)

onMounted(async () => {
  await renderGraph()
})

onBeforeUnmount(() => {
  destroyGraph()
})
</script>
