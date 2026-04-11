import { describe, expect, it } from 'vitest'
import { buildGraphRouteQuery, buildSimulationRouteQuery } from '~/utils/workspaceRoutes'

describe('buildGraphRouteQuery', () => {
  it('preserves the current project when navigating back to graph', () => {
    expect(buildGraphRouteQuery('proj_123')).toEqual({ project: 'proj_123' })
  })

  it('omits blank project ids', () => {
    expect(buildGraphRouteQuery('   ')).toEqual({})
    expect(buildGraphRouteQuery(null)).toEqual({})
  })
})

describe('buildSimulationRouteQuery', () => {
  it('preserves both project and simulation context when returning to simulation', () => {
    expect(buildSimulationRouteQuery('proj_123', 'sim_456')).toEqual({
      project: 'proj_123',
      simulation: 'sim_456',
    })
  })

  it('keeps project context even if the simulation id is missing', () => {
    expect(buildSimulationRouteQuery('proj_123', '')).toEqual({ project: 'proj_123' })
  })
})
