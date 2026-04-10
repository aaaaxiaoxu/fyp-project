/**
 * Unit tests for pure helper functions used in simulation.vue (Task 12).
 * These functions are replicated here to be testable without Nuxt/Vuetify.
 */

import { describe, it, expect } from 'vitest'
import { ref, computed } from 'vue'

// ---------------------------------------------------------------------------
// Replicated from simulation.vue — keep in sync with the source
// ---------------------------------------------------------------------------

type RuntimeStatus = 'created' | 'preparing' | 'ready' | 'running' | 'completed' | 'stopped' | 'failed'
type RuntimeActionPlatform = 'all' | 'twitter' | 'reddit'

type SimulationStatusResponse = {
  simulation_id: string
  status: RuntimeStatus
  current_round: number
  total_rounds: number
  twitter_actions_count: number
  reddit_actions_count: number
  interactive_ready: boolean
  error?: string | null
  recent_actions: SimulationAction[]
}

type SimulationAction = {
  simulation_id?: string
  platform?: string
  round_number?: number
  agent_id?: number
  agent_name?: string
  action_type?: string
  content?: string
  topic?: string
  created_at?: string
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

function normalizeActionType(value: string | undefined) {
  return value ? value.replaceAll('_', ' ') : 'ACTION'
}

function formatActionTime(value: string | undefined) {
  if (!value) {
    return 'pending'
  }
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

function actionKey(action: SimulationAction, index: number) {
  return [
    action.platform || 'platform',
    action.round_number ?? 'round',
    action.agent_id ?? 'agent',
    action.action_type || 'action',
    action.created_at || index,
  ].join(':')
}

function summarizeError(error: string | null | undefined) {
  if (!error) {
    return ''
  }
  return error.split('\n').slice(0, 3).join('\n')
}

function shortenUuid(value: string) {
  return value.length <= 14 ? value : `${value.slice(0, 6)}...${value.slice(-4)}`
}

// ---------------------------------------------------------------------------
// Computed property logic replicated from simulation.vue
// ---------------------------------------------------------------------------

function makeRuntimeComputeds(
  runtimeStatus: ReturnType<typeof ref<SimulationStatusResponse | null>>,
  runtimeActions: ReturnType<typeof ref<SimulationAction[]>>,
  simulationConfig: ReturnType<typeof ref<{ time_config?: { total_simulation_hours: number; minutes_per_round: number } } | null>>,
  activeSimulationId: ReturnType<typeof ref<string | null>>,
) {
  const totalRounds = computed(() => {
    const timeConfig = simulationConfig.value?.time_config
    if (!timeConfig) return 0
    return Math.max(1, Math.ceil((timeConfig.total_simulation_hours * 60) / Math.max(timeConfig.minutes_per_round, 1)))
  })

  const totalRuntimeActions = computed(
    () => (runtimeStatus.value?.twitter_actions_count || 0) + (runtimeStatus.value?.reddit_actions_count || 0),
  )

  const runtimeStatusMeta = computed(() =>
    runtimeMeta(runtimeStatus.value?.status || (simulationConfig.value ? 'ready' : 'created')),
  )

  const runtimeRoundText = computed(() => {
    const currentRound = runtimeStatus.value?.current_round ?? 0
    const total = runtimeStatus.value?.total_rounds || totalRounds.value || 0
    return total ? `${currentRound} / ${total}` : `${currentRound}`
  })

  const runtimeProgress = computed(() => {
    const currentRound = runtimeStatus.value?.current_round ?? 0
    const total = runtimeStatus.value?.total_rounds || totalRounds.value || 0
    if (total <= 0) return 0
    return Math.min(100, Math.max(0, Math.round((currentRound / total) * 100)))
  })

  const displayedRuntimeActions = computed(() => {
    const source = runtimeActions.value.length ? runtimeActions.value : runtimeStatus.value?.recent_actions || []
    return [...source].reverse()
  })

  const canStartRuntime = computed(() => {
    if (!activeSimulationId.value || !simulationConfig.value) return false
    const status = runtimeStatus.value?.status || 'ready'
    return ['ready', 'completed', 'stopped', 'failed'].includes(status)
  })

  return {
    totalRounds,
    totalRuntimeActions,
    runtimeStatusMeta,
    runtimeRoundText,
    runtimeProgress,
    displayedRuntimeActions,
    canStartRuntime,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('runtimeMeta', () => {
  it.each([
    ['created', 'Not Prepared', 'badge pending'],
    ['preparing', 'Preparing', 'badge processing'],
    ['ready', 'Ready', 'badge accent'],
    ['running', 'Running', 'badge processing'],
    ['completed', 'Completed', 'badge success'],
    ['stopped', 'Stopped', 'badge success'],
    ['failed', 'Failed', 'badge danger'],
  ] as const)('status=%s → label=%s, class=%s', (status, label, cls) => {
    const meta = runtimeMeta(status)
    expect(meta.label).toBe(label)
    expect(meta.class).toBe(cls)
  })

  it('returns passthrough for unknown status', () => {
    const meta = runtimeMeta('unknown_xyz')
    expect(meta.label).toBe('unknown_xyz')
    expect(meta.class).toBe('badge pending')
  })
})

describe('normalizeActionType', () => {
  it('replaces underscores with spaces', () => {
    expect(normalizeActionType('LIKE_POST')).toBe('LIKE POST')
    expect(normalizeActionType('CROSS_POST_RETWEET')).toBe('CROSS POST RETWEET')
  })

  it('returns ACTION for undefined', () => {
    expect(normalizeActionType(undefined)).toBe('ACTION')
  })

  it('returns ACTION for empty string', () => {
    expect(normalizeActionType('')).toBe('ACTION')
  })

  it('preserves already-clean values', () => {
    expect(normalizeActionType('POST')).toBe('POST')
    expect(normalizeActionType('COMMENT')).toBe('COMMENT')
  })
})

describe('formatActionTime', () => {
  it('returns "pending" for undefined', () => {
    expect(formatActionTime(undefined)).toBe('pending')
  })

  it('returns original string for invalid date', () => {
    expect(formatActionTime('not-a-date')).toBe('not-a-date')
  })

  it('formats a valid ISO timestamp to HH:MM:SS', () => {
    // 2026-01-01T00:00:01+00:00 → depends on local timezone for display
    const result = formatActionTime('2026-01-01T12:34:56+00:00')
    // Should be a time string matching HH:MM:SS pattern
    expect(result).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })
})

describe('actionKey', () => {
  it('generates a composite key from action fields', () => {
    const action: SimulationAction = {
      platform: 'twitter',
      round_number: 3,
      agent_id: 7,
      action_type: 'POST',
      created_at: '2026-01-01T00:00:01+00:00',
    }
    const key = actionKey(action, 0)
    expect(key).toBe('twitter:3:7:POST:2026-01-01T00:00:01+00:00')
  })

  it('uses fallbacks for missing fields', () => {
    const key = actionKey({}, 42)
    expect(key).toBe('platform:round:agent:action:42')
  })

  it('uses index as fallback when created_at is missing', () => {
    const action: SimulationAction = { platform: 'reddit' }
    expect(actionKey(action, 5)).toContain(':5')
  })
})

describe('summarizeError', () => {
  it('returns empty for null/undefined/empty', () => {
    expect(summarizeError(null)).toBe('')
    expect(summarizeError(undefined)).toBe('')
    expect(summarizeError('')).toBe('')
  })

  it('returns first 3 lines of a multiline error', () => {
    const err = 'line1\nline2\nline3\nline4\nline5'
    expect(summarizeError(err)).toBe('line1\nline2\nline3')
  })

  it('returns single-line errors unchanged', () => {
    expect(summarizeError('Something went wrong')).toBe('Something went wrong')
  })
})

describe('shortenUuid', () => {
  it('returns strings ≤14 chars unchanged', () => {
    expect(shortenUuid('short')).toBe('short')
    expect(shortenUuid('exactly14chars')).toBe('exactly14chars')
  })

  it('truncates long strings to first 6 + ... + last 4', () => {
    const result = shortenUuid('abcdef1234567890')
    expect(result).toBe('abcdef...7890')
  })
})

describe('runtimeProgress computed', () => {
  function setup(current: number, total: number, statusOverride?: RuntimeStatus) {
    const runtimeStatus = ref<SimulationStatusResponse | null>({
      simulation_id: 'sim1',
      status: statusOverride ?? 'running',
      current_round: current,
      total_rounds: total,
      twitter_actions_count: 0,
      reddit_actions_count: 0,
      interactive_ready: false,
      recent_actions: [],
    })
    const { runtimeProgress } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref('sim1'))
    return runtimeProgress
  }

  it('returns 0 when total is 0', () => {
    expect(setup(0, 0).value).toBe(0)
  })

  it('returns 50% at halfway point', () => {
    expect(setup(6, 12).value).toBe(50)
  })

  it('returns 100% when complete', () => {
    expect(setup(12, 12).value).toBe(100)
  })

  it('clamps at 100 if somehow current > total', () => {
    expect(setup(15, 12).value).toBe(100)
  })
})

describe('runtimeRoundText computed', () => {
  it('shows "current / total" when total is known', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>({
      simulation_id: 'sim1',
      status: 'running',
      current_round: 5,
      total_rounds: 72,
      twitter_actions_count: 0,
      reddit_actions_count: 0,
      interactive_ready: false,
      recent_actions: [],
    })
    const { runtimeRoundText } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref('sim1'))
    expect(runtimeRoundText.value).toBe('5 / 72')
  })

  it('shows just current_round when no total available', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>({
      simulation_id: 'sim1',
      status: 'running',
      current_round: 3,
      total_rounds: 0,
      twitter_actions_count: 0,
      reddit_actions_count: 0,
      interactive_ready: false,
      recent_actions: [],
    })
    const { runtimeRoundText } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref('sim1'))
    expect(runtimeRoundText.value).toBe('3')
  })
})

describe('totalRuntimeActions computed', () => {
  it('sums twitter and reddit counts', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>({
      simulation_id: 'sim1',
      status: 'completed',
      current_round: 72,
      total_rounds: 72,
      twitter_actions_count: 2919,
      reddit_actions_count: 2919,
      interactive_ready: true,
      recent_actions: [],
    })
    const { totalRuntimeActions } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref('sim1'))
    expect(totalRuntimeActions.value).toBe(5838)
  })

  it('returns 0 when no status', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const { totalRuntimeActions } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref(null))
    expect(totalRuntimeActions.value).toBe(0)
  })
})

describe('runtimeStatusMeta computed', () => {
  it('returns ready meta when config is loaded but no status yet', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const simulationConfig = ref<{ time_config?: any } | null>({ time_config: undefined })
    const { runtimeStatusMeta } = makeRuntimeComputeds(runtimeStatus, ref([]), simulationConfig, ref('sim1'))
    expect(runtimeStatusMeta.value.label).toBe('Ready')
  })

  it('returns created meta when no config and no status', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const { runtimeStatusMeta } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref(null))
    expect(runtimeStatusMeta.value.label).toBe('Not Prepared')
  })

  it('reflects running status from runtimeStatus', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>({
      simulation_id: 'sim1',
      status: 'running',
      current_round: 5,
      total_rounds: 72,
      twitter_actions_count: 100,
      reddit_actions_count: 100,
      interactive_ready: false,
      recent_actions: [],
    })
    const { runtimeStatusMeta } = makeRuntimeComputeds(runtimeStatus, ref([]), ref({ time_config: undefined }), ref('sim1'))
    expect(runtimeStatusMeta.value.label).toBe('Running')
    expect(runtimeStatusMeta.value.class).toBe('badge processing')
  })
})

describe('displayedRuntimeActions computed', () => {
  it('prefers runtimeActions over recent_actions when non-empty', () => {
    const fullActions: SimulationAction[] = [
      { platform: 'twitter', round_number: 1, action_type: 'POST' },
      { platform: 'twitter', round_number: 2, action_type: 'LIKE' },
    ]
    const runtimeStatus = ref<SimulationStatusResponse | null>({
      simulation_id: 'sim1',
      status: 'completed',
      current_round: 2,
      total_rounds: 72,
      twitter_actions_count: 2,
      reddit_actions_count: 0,
      interactive_ready: false,
      recent_actions: [{ platform: 'reddit', round_number: 1, action_type: 'COMMENT' }],
    })
    const runtimeActions = ref<SimulationAction[]>(fullActions)
    const { displayedRuntimeActions } = makeRuntimeComputeds(runtimeStatus, runtimeActions, ref(null), ref('sim1'))
    // Should use runtimeActions (twitter), reversed
    expect(displayedRuntimeActions.value[0].action_type).toBe('LIKE')
    expect(displayedRuntimeActions.value[1].action_type).toBe('POST')
  })

  it('falls back to recent_actions when runtimeActions is empty, reversed', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>({
      simulation_id: 'sim1',
      status: 'running',
      current_round: 3,
      total_rounds: 72,
      twitter_actions_count: 2,
      reddit_actions_count: 1,
      interactive_ready: false,
      recent_actions: [
        { platform: 'reddit', round_number: 2, action_type: 'COMMENT' },
        { platform: 'twitter', round_number: 3, action_type: 'REPOST' },
      ],
    })
    const { displayedRuntimeActions } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref('sim1'))
    // Reversed: REPOST first, COMMENT second
    expect(displayedRuntimeActions.value[0].action_type).toBe('REPOST')
    expect(displayedRuntimeActions.value[1].action_type).toBe('COMMENT')
  })

  it('returns empty when both sources are empty', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const { displayedRuntimeActions } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref('sim1'))
    expect(displayedRuntimeActions.value).toHaveLength(0)
  })
})

describe('canStartRuntime computed', () => {
  const config = ref<{ time_config?: any } | null>({ time_config: undefined })

  it('returns false when no simulationId', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const { canStartRuntime } = makeRuntimeComputeds(runtimeStatus, ref([]), config, ref(null))
    expect(canStartRuntime.value).toBe(false)
  })

  it('returns false when no config', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const { canStartRuntime } = makeRuntimeComputeds(runtimeStatus, ref([]), ref(null), ref('sim1'))
    expect(canStartRuntime.value).toBe(false)
  })

  it('returns true when status is null (defaults to ready)', () => {
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const { canStartRuntime } = makeRuntimeComputeds(runtimeStatus, ref([]), config, ref('sim1'))
    expect(canStartRuntime.value).toBe(true)
  })

  it.each(['ready', 'completed', 'stopped', 'failed'] as RuntimeStatus[])(
    'returns true for startable status=%s',
    (status) => {
      const runtimeStatus = ref<SimulationStatusResponse | null>({
        simulation_id: 'sim1',
        status,
        current_round: 0,
        total_rounds: 72,
        twitter_actions_count: 0,
        reddit_actions_count: 0,
        interactive_ready: false,
        recent_actions: [],
      })
      const { canStartRuntime } = makeRuntimeComputeds(runtimeStatus, ref([]), config, ref('sim1'))
      expect(canStartRuntime.value).toBe(true)
    },
  )

  it.each(['running', 'preparing', 'created'] as RuntimeStatus[])(
    'returns false for non-startable status=%s',
    (status) => {
      const runtimeStatus = ref<SimulationStatusResponse | null>({
        simulation_id: 'sim1',
        status,
        current_round: 0,
        total_rounds: 72,
        twitter_actions_count: 0,
        reddit_actions_count: 0,
        interactive_ready: false,
        recent_actions: [],
      })
      const { canStartRuntime } = makeRuntimeComputeds(runtimeStatus, ref([]), config, ref('sim1'))
      expect(canStartRuntime.value).toBe(false)
    },
  )
})

describe('totalRounds computed from time_config', () => {
  it('computes correctly from hours and minutes_per_round', () => {
    const simulationConfig = ref<{ time_config?: any } | null>({
      time_config: { total_simulation_hours: 12, minutes_per_round: 10 },
    })
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const { totalRounds } = makeRuntimeComputeds(runtimeStatus, ref([]), simulationConfig, ref(null))
    // 12h * 60min / 10 min_per_round = 72
    expect(totalRounds.value).toBe(72)
  })

  it('returns 0 when no time_config', () => {
    const simulationConfig = ref<{ time_config?: any } | null>(null)
    const runtimeStatus = ref<SimulationStatusResponse | null>(null)
    const { totalRounds } = makeRuntimeComputeds(runtimeStatus, ref([]), simulationConfig, ref(null))
    expect(totalRounds.value).toBe(0)
  })

  it('clamps minimum to 1 round', () => {
    const simulationConfig = ref<{ time_config?: any } | null>({
      time_config: { total_simulation_hours: 0.001, minutes_per_round: 60 },
    })
    const { totalRounds } = makeRuntimeComputeds(ref(null), ref([]), simulationConfig, ref(null))
    expect(totalRounds.value).toBe(1)
  })
})
