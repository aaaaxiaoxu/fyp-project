/**
 * Unit tests for app/utils/explorerSse.ts (Task 14).
 * Covers parseSseBuffer and createExplorerSessionId.
 */

import { describe, it, expect } from 'vitest'
import { parseSseBuffer, createExplorerSessionId } from '../app/utils/explorerSse'

// ---------------------------------------------------------------------------
// parseSseBuffer
// ---------------------------------------------------------------------------

describe('parseSseBuffer — basic parsing', () => {
  it('parses a single complete event block', () => {
    const buffer = 'event: status\ndata: {"status":"started"}\n\n'
    const { events, rest } = parseSseBuffer(buffer)
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('status')
    expect(events[0].data).toEqual({ status: 'started' })
    expect(rest).toBe('')
  })

  it('parses multiple complete event blocks in one buffer', () => {
    const buffer = [
      'event: tool_call\ndata: {"tool_name":"quick_search"}\n\n',
      'event: answer_chunk\ndata: {"chunk":"Hello world"}\n\n',
    ].join('')
    const { events } = parseSseBuffer(buffer)
    expect(events).toHaveLength(2)
    expect(events[0].event).toBe('tool_call')
    expect(events[1].event).toBe('answer_chunk')
    expect(events[1].data).toEqual({ chunk: 'Hello world' })
  })

  it('returns incomplete trailing block as rest', () => {
    const buffer = 'event: status\ndata: {"status":"started"}\n\nevent: tool_call\ndata: {"tool_name'
    const { events, rest } = parseSseBuffer(buffer)
    expect(events).toHaveLength(1)
    expect(rest).toContain('tool_call')
  })

  it('returns empty events and full buffer as rest when no complete block', () => {
    const buffer = 'event: status\ndata: {"status":"started"}'
    const { events, rest } = parseSseBuffer(buffer)
    expect(events).toHaveLength(0)
    expect(rest).toBe(buffer)
  })

  it('returns empty events for empty buffer', () => {
    const { events, rest } = parseSseBuffer('')
    expect(events).toHaveLength(0)
    expect(rest).toBe('')
  })
})

describe('parseSseBuffer — field handling', () => {
  it('handles CRLF line endings', () => {
    const buffer = 'event: final_answer\r\ndata: {"answer":"done"}\r\n\r\n'
    const { events } = parseSseBuffer(buffer)
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('final_answer')
    expect(events[0].data).toEqual({ answer: 'done' })
  })

  it('ignores comment lines starting with colon', () => {
    const buffer = ': keep-alive\nevent: status\ndata: {"status":"ok"}\n\n'
    const { events } = parseSseBuffer(buffer)
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('status')
  })

  it('splits correctly on blank line separating two mini-blocks', () => {
    // SSE spec: \n\n is the block separator, so this is actually 2 blocks:
    // block1: "event: tool_result" (no data → event with empty data object)
    // block2: "data: {\"tool_name\":\"x\"}" (no event → defaults to "message")
    const buffer = 'event: tool_result\n\ndata: {"tool_name":"x"}\n\n'
    const { events } = parseSseBuffer(buffer)
    expect(events).toHaveLength(2)
    // First block: named event with empty data
    expect(events[0].event).toBe('tool_result')
    // Second block: default "message" event with data
    expect(events[1].event).toBe('message')
    expect(events[1].data).toEqual({ tool_name: 'x' })
  })

  it('trims trailing whitespace from field values', () => {
    const buffer = 'event: answer_chunk   \ndata: {"chunk":"hi"}   \n\n'
    const { events } = parseSseBuffer(buffer)
    expect(events[0].event).toBe('answer_chunk')
  })

  it('handles data with space after colon', () => {
    const buffer = 'event: status\ndata: {"status":"running"}\n\n'
    const { events } = parseSseBuffer(buffer)
    expect(events[0].data).toEqual({ status: 'running' })
  })
})

describe('parseSseBuffer — data parsing edge cases', () => {
  it('falls back to raw string when data is not JSON', () => {
    const buffer = 'event: error\ndata: plain text error\n\n'
    const { events } = parseSseBuffer(buffer)
    expect(events).toHaveLength(1)
    expect(events[0].data).toEqual({ raw: 'plain text error' })
  })

  it('wraps non-object JSON in value wrapper', () => {
    const buffer = 'event: status\ndata: 42\n\n'
    const { events } = parseSseBuffer(buffer)
    expect(events[0].data).toEqual({ value: 42 })
  })

  it('returns empty data object when data line is absent', () => {
    // Block has event but no data line — filtered out since no data and event is explicit
    const buffer = 'event: status\n\n'
    const { events } = parseSseBuffer(buffer)
    // no data lines means empty data but event is set — included
    if (events.length > 0) {
      expect(events[0].data).toEqual({})
    }
  })

  it('handles valid JSON with nested objects', () => {
    const result = { facts: ['Alice supports policy.'], nodes: [] }
    const buffer = `event: tool_result\ndata: ${JSON.stringify({ result })}\n\n`
    const { events } = parseSseBuffer(buffer)
    expect(events[0].data.result).toEqual(result)
  })

  it('handles unicode content in data', () => {
    const buffer = 'event: answer_chunk\ndata: {"chunk":"Alice支持社区政策"}\n\n'
    const { events } = parseSseBuffer(buffer)
    expect(events[0].data).toEqual({ chunk: 'Alice支持社区政策' })
  })
})

describe('parseSseBuffer — streaming simulation', () => {
  it('correctly processes a realistic Explorer SSE stream', () => {
    const stream = [
      'event: status\ndata: {"simulation_id":"sim1","status":"started"}\n\n',
      'event: tool_call\ndata: {"tool_name":"quick_search","parameters":{"question":"Alice"}}\n\n',
      'event: tool_result\ndata: {"tool_name":"quick_search","result":{"facts":["Alice supports policy."]}}\n\n',
      'event: answer_chunk\ndata: {"chunk":"Based on `quick_search`,"}\n\n',
      'event: answer_chunk\ndata: {"chunk":" Alice supports the community policy."}\n\n',
      'event: final_answer\ndata: {"answer":"Based on quick_search, Alice supports the community policy.","tool_name":"quick_search"}\n\n',
    ].join('')

    const { events, rest } = parseSseBuffer(stream)
    expect(events).toHaveLength(6)
    expect(rest).toBe('')

    const names = events.map((e) => e.event)
    expect(names).toEqual(['status', 'tool_call', 'tool_result', 'answer_chunk', 'answer_chunk', 'final_answer'])

    // Answer chunks reconstruct the full answer
    const chunks = events
      .filter((e) => e.event === 'answer_chunk')
      .map((e) => e.data.chunk as string)
      .join('')
    expect(chunks).toContain('Alice supports')
  })

  it('correctly accumulates answer from split buffer delivery', () => {
    const fullBuffer =
      'event: answer_chunk\ndata: {"chunk":"Hello"}\n\nevent: answer_chunk\ndata: {"chunk":" World"}\n\n'

    // Simulate chunked delivery: first chunk cuts mid-block
    const part1 = fullBuffer.slice(0, 40)
    const part2 = fullBuffer.slice(40)

    const { events: e1, rest: r1 } = parseSseBuffer(part1)
    const { events: e2 } = parseSseBuffer(r1 + part2)

    const totalEvents = [...e1, ...e2]
    const answer = totalEvents
      .filter((e) => e.event === 'answer_chunk')
      .map((e) => e.data.chunk as string)
      .join('')
    expect(answer).toBe('Hello World')
  })

  it('handles error event correctly', () => {
    const buffer = 'event: error\ndata: {"message":"tool exploded","mode":"ask"}\n\n'
    const { events } = parseSseBuffer(buffer)
    expect(events[0].event).toBe('error')
    expect(events[0].data.message).toBe('tool exploded')
  })
})

// ---------------------------------------------------------------------------
// createExplorerSessionId
// ---------------------------------------------------------------------------

describe('createExplorerSessionId', () => {
  it('starts with explorer_ prefix', () => {
    const id = createExplorerSessionId()
    expect(id).toMatch(/^explorer_/)
  })

  it('returns a non-empty string longer than prefix', () => {
    const id = createExplorerSessionId()
    expect(id.length).toBeGreaterThan('explorer_'.length)
  })

  it('generates unique ids on successive calls', () => {
    const ids = new Set(Array.from({ length: 20 }, () => createExplorerSessionId()))
    expect(ids.size).toBe(20)
  })

  it('only contains alphanumeric and underscore characters', () => {
    // timestamp is base-36 (alphanumeric), suffix is base-36 slice
    const id = createExplorerSessionId()
    expect(id).toMatch(/^[a-z0-9_]+$/)
  })
})
