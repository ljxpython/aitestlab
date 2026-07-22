import { describe, expect, it } from 'vitest'

import { normalizeChatTargetFromThreadMetadata } from './chatTarget'

describe('normalizeChatTargetFromThreadMetadata', () => {
  it('restores assistant targets from thread metadata', () => {
    expect(
      normalizeChatTargetFromThreadMetadata(
        {
          target_type: 'assistant',
          target_display_name: 'Support Bot',
          assistant_id: 'assistant-1'
        },
        '2026-07-22T08:00:00.000Z'
      )
    ).toEqual({
      targetType: 'assistant',
      assistantId: 'assistant-1',
      assistantName: 'Support Bot',
      updatedAt: '2026-07-22T08:00:00.000Z'
    })
  })

  it('restores graph targets from thread metadata', () => {
    expect(
      normalizeChatTargetFromThreadMetadata(
        {
          target_type: 'graph',
          target_display_name: 'Customer Graph',
          assistant_id: 'graph-runtime-1',
          graph_id: 'graph-1',
          graph_name: 'Customer Graph'
        },
        '2026-07-22T09:00:00.000Z'
      )
    ).toEqual({
      targetType: 'graph',
      graphId: 'graph-1',
      graphName: 'Customer Graph',
      updatedAt: '2026-07-22T09:00:00.000Z'
    })
  })

  it('uses graph assistant id when graph id is absent', () => {
    expect(
      normalizeChatTargetFromThreadMetadata(
        {
          target_type: 'graph',
          target_display_name: 'Runtime Graph',
          assistant_id: 'graph-runtime-1'
        },
        '2026-07-22T10:00:00.000Z'
      )
    ).toEqual({
      targetType: 'graph',
      graphId: 'graph-runtime-1',
      graphName: 'Runtime Graph',
      updatedAt: '2026-07-22T10:00:00.000Z'
    })
  })

  it('ignores metadata without a restorable chat target', () => {
    expect(normalizeChatTargetFromThreadMetadata({ target_type: 'assistant' })).toBeNull()
    expect(normalizeChatTargetFromThreadMetadata(null)).toBeNull()
  })
})
