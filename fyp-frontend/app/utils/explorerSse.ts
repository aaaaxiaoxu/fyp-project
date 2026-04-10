export type ExplorerSseEvent = {
  event: string
  data: Record<string, unknown>
}

export function parseSseBuffer(buffer: string): { events: ExplorerSseEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n')
  const rest = blocks.pop() ?? ''

  return {
    events: blocks.map(parseSseBlock).filter((event): event is ExplorerSseEvent => Boolean(event)),
    rest,
  }
}

export function createExplorerSessionId() {
  const timestamp = Date.now().toString(36)
  const suffix = Math.random().toString(36).slice(2, 10)
  return `explorer_${timestamp}_${suffix}`
}

function parseSseBlock(block: string): ExplorerSseEvent | null {
  const lines = block.split('\n')
  let eventName = 'message'
  const dataLines: string[] = []

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    if (!line || line.startsWith(':')) {
      continue
    }
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim() || 'message'
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }

  if (!dataLines.length && eventName === 'message') {
    return null
  }

  return {
    event: eventName,
    data: parseDataLines(dataLines),
  }
}

function parseDataLines(lines: string[]): Record<string, unknown> {
  const raw = lines.join('\n')
  if (!raw) {
    return {}
  }

  try {
    const parsed: unknown = JSON.parse(raw)
    return isRecord(parsed) ? parsed : { value: parsed }
  } catch {
    return { raw }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}
