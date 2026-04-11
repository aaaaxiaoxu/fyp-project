function normalizeRouteValue(value: string | null | undefined) {
  const normalized = value?.trim()
  return normalized ? normalized : null
}

export function buildGraphRouteQuery(projectId: string | null | undefined) {
  const query: Record<string, string> = {}
  const normalizedProjectId = normalizeRouteValue(projectId)
  if (normalizedProjectId) {
    query.project = normalizedProjectId
  }
  return query
}

export function buildSimulationRouteQuery(projectId: string | null | undefined, simulationId: string | null | undefined) {
  const query = buildGraphRouteQuery(projectId)
  const normalizedSimulationId = normalizeRouteValue(simulationId)
  if (normalizedSimulationId) {
    query.simulation = normalizedSimulationId
  }
  return query
}
