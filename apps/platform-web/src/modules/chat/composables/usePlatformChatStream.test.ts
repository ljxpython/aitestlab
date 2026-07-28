import { computed, nextTick, ref } from 'vue'
import { usePlatformChatStream } from './usePlatformChatStream'

const streamMock = vi.hoisted(() => ({
  value: null as Record<string, unknown> | null,
  options: null as Record<string, unknown> | null
}))

vi.mock('@langchain/vue', () => ({
  useStream: (options: Record<string, unknown>) => {
    streamMock.options = options
    return streamMock.value
  }
}))

function createStream() {
  return {
    error: ref(undefined),
    interrupts: ref([]),
    isLoading: ref(false),
    messages: ref([]),
    threadId: ref<string | null>('thread-1'),
    toolCalls: ref([]),
    values: ref({ messages: [] }),
    respond: vi.fn().mockResolvedValue(undefined),
    respondAll: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
    submit: vi.fn().mockResolvedValue(undefined)
  }
}

function createOptions(onRefreshThread = vi.fn().mockResolvedValue(undefined)) {
  return {
    projectId: computed(() => 'project-1'),
    target: computed(() => ({
      targetType: 'assistant' as const,
      assistantId: 'assistant-1',
      assistantName: 'Assistant',
      resolvedTargetId: 'assistant-1',
      displayName: 'Assistant',
      label: 'Assistant · Assistant'
    })),
    activeThreadId: ref('thread-1'),
    activeThreadStatus: computed(() => 'idle'),
    activeThreadError: computed(() => null),
    historyItems: ref([{ checkpoint: { checkpoint_id: 'gateway-history' } }]),
    selectedBranch: ref(''),
    runOptions: {
      modelId: '',
      systemPrompt: '',
      enableTools: false,
      toolNames: [],
      temperature: '',
      maxTokens: ''
    },
    onRefreshThread
  }
}

describe('usePlatformChatStream', () => {
  it('uses the built-in Agent Server transport without a custom adapter or legacy fallback', () => {
    streamMock.value = createStream()
    usePlatformChatStream(createOptions())

    expect(streamMock.options).toMatchObject({
      apiUrl: expect.stringContaining('/api/langgraph'),
      assistantId: 'assistant-1',
      callerOptions: { fetch: expect.any(Function) },
      fetch: expect.any(Function),
      threadId: expect.any(Function)
    })
    expect(
      (streamMock.options?.callerOptions as { fetch?: unknown }).fetch
    ).toBe(streamMock.options?.fetch)
    expect(streamMock.options).not.toHaveProperty('transport')
  })

  it('hands command pending to SDK loading and refreshes once on finish', async () => {
    const stream = createStream()
    streamMock.value = stream
    const options = createOptions()
    const adapter = usePlatformChatStream(options)

    stream.isLoading.value = true
    await nextTick()
    expect(adapter.sending.value).toBe(true)

    stream.isLoading.value = false
    await (
      streamMock.options?.onCompleted as (info: {
        reason: string
      }) => Promise<void>
    )({
      reason: 'success'
    })
    expect(adapter.sending.value).toBe(false)
    expect(options.onRefreshThread).toHaveBeenCalledOnce()
    expect(options.onRefreshThread).toHaveBeenCalledWith('thread-1', {
      preserveInfo: false
    })
  })

  it('keeps persistent history owned by the runtime gateway snapshot', async () => {
    const stream = createStream()
    streamMock.value = stream
    const options = createOptions()
    usePlatformChatStream(options)

    stream.values.value = { messages: [] }
    await nextTick()

    expect(options.historyItems.value).toEqual([
      { checkpoint: { checkpoint_id: 'gateway-history' } }
    ])
  })

  it('does not render stale SDK projections after switching to a blank thread', async () => {
    const stream = createStream()
    stream.messages.value = [{ id: 'old-message', type: 'human', content: '旧会话' }]
    stream.values.value = { messages: stream.messages.value }
    stream.toolCalls.value = [{ id: 'old-tool' }]
    stream.interrupts.value = [{ id: 'old-interrupt', value: { question: '旧审批' } }]
    streamMock.value = stream
    const options = createOptions()
    const adapter = usePlatformChatStream(options)

    options.activeThreadId.value = ''
    options.historyItems.value = []
    await nextTick()

    expect(adapter.messages.value).toEqual([])
    expect(adapter.displayState.value).toBeNull()
    expect(adapter.toolCalls.value).toEqual([])
    expect(adapter.interruptPayload.value).toBeUndefined()
  })

  it('shows the persisted thread head when a completed v2 stream projection is empty', async () => {
    const stream = createStream()
    streamMock.value = stream
    const interrupt = {
      id: 'interrupt-1',
      value: { action_requests: [{ name: 'submit_high_impact_action', args: {} }] }
    }
    const options = createOptions(
      vi.fn(async () => {
        options.historyItems.value = [
          {
            checkpoint: { checkpoint_id: 'checkpoint-1' },
            values: {
              messages: [{ id: 'assistant-1', type: 'ai', content: '等待审批' }]
            },
            interrupts: [interrupt],
            tasks: [{ interrupts: [interrupt] }]
          }
        ]
      })
    )
    const adapter = usePlatformChatStream(options)

    await (
      streamMock.options?.onCompleted as (info: { reason: string }) => Promise<void>
    )({ reason: 'success' })

    expect(adapter.messages.value).toEqual([
      { id: 'assistant-1', type: 'ai', content: '等待审批' }
    ])
    expect(adapter.interruptPayload.value).toEqual([interrupt])
  })

  it('keeps a completed run error visible after refreshing the persisted snapshot', async () => {
    const stream = createStream()
    stream.error.value = new Error('run failed')
    streamMock.value = stream
    const options = createOptions(vi.fn(async () => undefined))
    const adapter = usePlatformChatStream(options)

    await (
      streamMock.options?.onCompleted as (info: {
        reason: string
      }) => Promise<void>
    )({
      reason: 'error'
    })

    expect(adapter.detailError.value).toContain('run failed')
  })

  it('reports cancellation without claiming the submitted message remains in the composer', async () => {
    const stream = createStream()
    streamMock.value = stream
    const options = createOptions()
    const adapter = usePlatformChatStream(options)

    await (
      streamMock.options?.onCompleted as (info: {
        reason: string
      }) => Promise<void>
    )({
      reason: 'stopped'
    })

    expect(adapter.detailInfo.value).toBe(
      '本轮运行已取消。输入框已恢复可编辑，你可以继续发送消息。'
    )
    expect(options.onRefreshThread).toHaveBeenCalledWith('thread-1', {
      preserveInfo: true
    })
  })
})
