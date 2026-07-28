import { computed, ref } from 'vue'
import {
  getRuntimeThreadSnapshot,
  listRuntimeThreadsPage
} from '@/services/runtime-gateway/workspace.service'
import type { RuntimeThreadSnapshot } from '@/services/runtime-gateway/workspace.service'
import { useChatThreadWorkspace } from './useChatThreadWorkspace'

vi.mock('@/services/runtime-gateway/workspace.service', () => ({
  buildRuntimeSnapshotWarning: vi.fn(() => ''),
  deleteRuntimeThread: vi.fn(),
  getRuntimeThreadSnapshot: vi.fn(),
  listRuntimeThreadsPage: vi.fn(),
  normalizeRuntimeGatewayError: vi.fn((error: Error) => ({
    kind: 'unknown',
    status: null,
    code: '',
    message: error.message
  }))
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function snapshot(threadId: string): RuntimeThreadSnapshot {
  return {
    detail: {
      thread_id: threadId,
      status: 'idle',
      values: { messages: [{ id: `${threadId}-message`, type: 'human', content: threadId }] }
    },
    state: null,
    history: [{ checkpoint: { checkpoint_id: `${threadId}-checkpoint` }, values: {} }],
    stateError: null,
    historyError: null
  }
}

function debugSnapshot(threadId: string): RuntimeThreadSnapshot {
  const result = snapshot(threadId)
  result.detail.metadata = { session_kind: 'legacy_debug' }
  return result
}

describe('useChatThreadWorkspace', () => {
  it('excludes legacy debug sessions from the formal chat workspace', async () => {
    vi.mocked(listRuntimeThreadsPage).mockResolvedValueOnce({
      items: [
        {
          thread_id: 'debug-thread',
          status: 'interrupted',
          metadata: { session_kind: 'legacy_debug' }
        },
        {
          thread_id: 'chat-thread',
          status: 'idle',
          metadata: {}
        }
      ],
      total: 2,
      limit: 100,
      offset: 0
    })
    vi.mocked(getRuntimeThreadSnapshot).mockResolvedValueOnce(snapshot('chat-thread'))
    const activeThreadId = ref('')
    const workspace = useChatThreadWorkspace({
      projectId: computed(() => 'project-1'),
      target: computed(() => ({
        targetType: 'graph' as const,
        graphId: 'assistant',
        updatedAt: '',
        resolvedTargetId: 'assistant',
        displayName: 'Assistant',
        label: 'Graph · Assistant'
      })),
      activeThreadId,
      activeThread: ref(null),
      selectedBranch: ref(''),
      historyItems: ref<Record<string, unknown>[]>([]),
      displayState: computed(() => null),
      clearStreamDetailFeedback: vi.fn(),
      resetStreamView: vi.fn(),
      streamDetailError: ref(''),
      streamDetailInfo: ref('')
    })

    workspace.resetForContextChange('debug-thread')
    expect(activeThreadId.value).toBe('debug-thread')
    await workspace.loadThreadList('debug-thread')

    expect(workspace.threadItems.value.map((item) => item.thread_id)).toEqual(['chat-thread'])
    expect(getRuntimeThreadSnapshot).toHaveBeenCalledOnce()
    expect(getRuntimeThreadSnapshot).toHaveBeenCalledWith(
      'project-1',
      'chat-thread',
      expect.any(Object)
    )
    expect(activeThreadId.value).toBe('chat-thread')
  })

  it('rejects a preferred debug snapshot and selects the next formal thread', async () => {
    vi.clearAllMocks()
    vi.mocked(listRuntimeThreadsPage).mockResolvedValueOnce({
      items: [
        { thread_id: 'debug-thread', status: 'interrupted', metadata: {} },
        { thread_id: 'chat-thread', status: 'idle', metadata: {} }
      ],
      total: 2,
      limit: 100,
      offset: 0
    })
    vi.mocked(getRuntimeThreadSnapshot)
      .mockResolvedValueOnce(debugSnapshot('debug-thread'))
      .mockResolvedValueOnce(snapshot('chat-thread'))
    const activeThreadId = ref('debug-thread')
    const resetStreamView = vi.fn()
    const workspace = useChatThreadWorkspace({
      projectId: computed(() => 'project-1'),
      target: computed(() => ({
        targetType: 'graph' as const,
        graphId: 'assistant',
        updatedAt: '',
        resolvedTargetId: 'assistant',
        displayName: 'Assistant',
        label: 'Graph · Assistant'
      })),
      activeThreadId,
      activeThread: ref(null),
      selectedBranch: ref(''),
      historyItems: ref<Record<string, unknown>[]>([]),
      displayState: computed(() => null),
      clearStreamDetailFeedback: vi.fn(),
      resetStreamView,
      streamDetailError: ref(''),
      streamDetailInfo: ref('')
    })

    await workspace.loadThreadList('debug-thread')

    expect(workspace.threadItems.value.map((item) => item.thread_id)).toEqual(['chat-thread'])
    expect(getRuntimeThreadSnapshot).toHaveBeenCalledTimes(2)
    expect(activeThreadId.value).toBe('chat-thread')
    expect(resetStreamView).toHaveBeenCalled()
  })

  it('does not let an older thread response overwrite the active thread', async () => {
    const first = deferred<RuntimeThreadSnapshot>()
    const second = deferred<RuntimeThreadSnapshot>()
    vi.mocked(getRuntimeThreadSnapshot)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const activeThreadId = ref('')
    const activeThread = ref(null)
    const historyItems = ref<Record<string, unknown>[]>([])
    const workspace = useChatThreadWorkspace({
      projectId: computed(() => 'project-1'),
      target: computed(() => ({
        targetType: 'assistant' as const,
        assistantId: 'assistant-1',
        resolvedTargetId: 'assistant-1',
        displayName: 'Assistant',
        label: 'Assistant · Assistant'
      })),
      activeThreadId,
      activeThread,
      selectedBranch: ref(''),
      historyItems,
      displayState: computed(() => null),
      clearStreamDetailFeedback: vi.fn(),
      resetStreamView: vi.fn(),
      streamDetailError: ref(''),
      streamDetailInfo: ref('')
    })

    const firstLoad = workspace.syncActiveThreadFromList('thread-a')
    const secondLoad = workspace.syncActiveThreadFromList('thread-b')
    second.resolve(snapshot('thread-b'))
    await secondLoad
    first.resolve(snapshot('thread-a'))
    await firstLoad

    expect(activeThreadId.value).toBe('thread-b')
    expect(activeThread.value?.thread_id).toBe('thread-b')
    expect(historyItems.value[0]).toMatchObject({
      checkpoint: { checkpoint_id: 'thread-b-checkpoint' }
    })
  })

  it('normalizes the legacy nested values shape only at the snapshot boundary', async () => {
    const legacySnapshot = snapshot('thread-a')
    legacySnapshot.history = [
      {
        checkpoint: { checkpoint_id: 'legacy-checkpoint' },
        values: {
          messages: [{ id: 'legacy-message', type: 'human', content: 'legacy' }]
        }
      }
    ]
    vi.mocked(getRuntimeThreadSnapshot).mockResolvedValueOnce(legacySnapshot)
    const historyItems = ref<Record<string, unknown>[]>([])
    const workspace = useChatThreadWorkspace({
      projectId: computed(() => 'project-1'),
      target: computed(() => ({
        targetType: 'assistant' as const,
        assistantId: 'assistant-1',
        resolvedTargetId: 'assistant-1',
        displayName: 'Assistant',
        label: 'Assistant'
      })),
      activeThreadId: ref(''),
      activeThread: ref(null),
      selectedBranch: ref(''),
      historyItems,
      displayState: computed(() => null),
      clearStreamDetailFeedback: vi.fn(),
      resetStreamView: vi.fn(),
      streamDetailError: ref(''),
      streamDetailInfo: ref('')
    })

    await workspace.syncActiveThreadFromList('thread-a')

    expect(historyItems.value[0]?.values).toEqual({
      messages: [{ id: 'legacy-message', type: 'human', content: 'legacy' }]
    })
  })
})
