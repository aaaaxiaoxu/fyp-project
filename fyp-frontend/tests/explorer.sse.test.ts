import { describe, expect, it, vi } from 'vitest'
import { createExplorerSessionId, parseSseBuffer } from '~/utils/explorerSse'

describe('parseSseBuffer', () => {
  it('parses Explorer SSE events and keeps an incomplete trailing block', () => {
    const payload = [
      'event: tool_call',
      'data: {"tool_name":"quick_search","parameters":{"question":"who leads?"}}',
      '',
      'event: answer_chunk',
      'data: {"chunk":"first"}',
      '',
      'event: final_answer',
      'data: {"answer":"done"}',
    ].join('\n')

    const { events, rest } = parseSseBuffer(payload)

    expect(events).toEqual([
      {
        event: 'tool_call',
        data: { tool_name: 'quick_search', parameters: { question: 'who leads?' } },
      },
      {
        event: 'answer_chunk',
        data: { chunk: 'first' },
      },
    ])
    expect(rest).toBe('event: final_answer\ndata: {"answer":"done"}')
  })

  it('parses the final block after the stream adds a separator', () => {
    const { events, rest } = parseSseBuffer('event: final_answer\ndata: {"answer":"done"}\n\n')

    expect(events).toEqual([{ event: 'final_answer', data: { answer: 'done' } }])
    expect(rest).toBe('')
  })

  it('handles CRLF, comments, multi-line data, and invalid JSON without throwing', () => {
    const payload = [
      ': keepalive',
      'event: error',
      'data: {"message":"line 1"',
      'data: "bad"}',
      '',
      '',
    ].join('\r\n')

    const { events, rest } = parseSseBuffer(payload)

    expect(events).toEqual([
      {
        event: 'error',
        data: { raw: '{"message":"line 1"\n"bad"}' },
      },
    ])
    expect(rest).toBe('')
  })
})

describe('createExplorerSessionId', () => {
  it('generates backend-compatible session ids', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1_776_666_666_000)
    vi.spyOn(Math, 'random').mockReturnValue(0.123456789)

    expect(createExplorerSessionId()).toMatch(/^explorer_[a-z0-9]+_[a-z0-9]+$/)
    expect(createExplorerSessionId().length).toBeLessThanOrEqual(64)

    vi.restoreAllMocks()
  })
})
