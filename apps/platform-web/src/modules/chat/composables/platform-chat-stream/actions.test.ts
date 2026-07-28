import { computed, ref } from 'vue'
import { createRuntimeThread } from '@/services/runtime-gateway/workspace.service'
import { createPlatformChatStreamActions } from './actions'
import type { PlatformChatStreamActionDeps } from './types'

vi.mock('@/services/runtime-gateway/workspace.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/runtime-gateway/workspace.service')>()),
  createRuntimeThread: vi.fn().mockResolvedValue({ thread_id: 'created-thread' })
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function createDeps(submit = vi.fn().mockResolvedValue(undefined)): PlatformChatStreamActionDeps {
  const commandPending = ref(false)
  const streamLoading = ref(false)

  return {
    stream: {
      messages: ref([]),
      stop: vi.fn().mockResolvedValue(undefined),
      submit,
      respond: vi.fn().mockResolvedValue(undefined),
      respondAll: vi.fn().mockResolvedValue(undefined)
    },
    options: {
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
      historyItems: ref([]),
      selectedBranch: ref(''),
      runOptions: {
        modelId: '',
        systemPrompt: '',
        enableTools: false,
        toolNames: [],
        temperature: '',
        maxTokens: ''
      },
      onRefreshThread: vi.fn()
    },
    commandPending,
    isBusy: computed(() => commandPending.value || streamLoading.value),
    cancelling: ref(false),
    detailError: ref(''),
    detailInfo: ref(''),
    lastRunId: ref(''),
    lastEventAt: ref(''),
    messages: computed(() => []),
    messageMetadataById: computed(() => ({})),
    interruptPayload: computed(() => undefined)
  }
}

describe('platform chat stream actions', () => {
  it('locks duplicate submission until the stream lifecycle takes over', async () => {
    const pending = deferred<undefined>()
    const deps = createDeps(vi.fn(() => pending.promise))
    const actions = createPlatformChatStreamActions(deps)

    const submission = actions.sendMessage('hello')

    expect(deps.commandPending.value).toBe(true)
    await expect(actions.sendMessage('duplicate')).resolves.toBe(false)
    pending.resolve(undefined)
    await expect(submission).resolves.toBe(true)
    expect(deps.commandPending.value).toBe(false)
  })

  it('releases command state and reports a normalized submit failure', async () => {
    const deps = createDeps(vi.fn().mockRejectedValue(new Error('submit failed')))
    const actions = createPlatformChatStreamActions(deps)

    await expect(actions.sendMessage('hello')).resolves.toBe(false)

    expect(deps.commandPending.value).toBe(false)
    expect(deps.detailError.value).toContain('submit failed')
  })

  it('cancels the server run through the SDK stream', async () => {
    const deps = createDeps()
    deps.commandPending.value = true
    const actions = createPlatformChatStreamActions(deps)

    await expect(actions.cancelActiveRun()).resolves.toBe(true)

    expect(deps.stream.stop).toHaveBeenCalledOnce()
    expect(deps.cancelling.value).toBe(false)
  })

  it('creates a project-scoped thread before the first v2 submit', async () => {
    const deps = createDeps()
    deps.stream.submit = vi.fn().mockImplementation(() => {
      expect(deps.options.activeThreadId.value).toBe('')
      return Promise.resolve()
    })
    deps.options.activeThreadId.value = ''
    const actions = createPlatformChatStreamActions(deps)

    await expect(actions.sendMessage('hello')).resolves.toBe(true)

    expect(createRuntimeThread).toHaveBeenCalledWith('project-1', deps.options.target.value)
    expect(deps.options.activeThreadId.value).toBe('created-thread')
    expect(deps.stream.submit).toHaveBeenCalledWith(
      expect.objectContaining({ messages: expect.any(Array) }),
      expect.objectContaining({ threadId: 'created-thread' })
    )
  })

  it('uses SDK fork and batched interrupt commands', async () => {
    const deps = createDeps()
    deps.messageMetadataById = computed(() => ({
      'ai-1': {
        messageId: 'ai-1',
        parentCheckpoint: { checkpoint_id: 'checkpoint-parent' }
      }
    }))
    const actions = createPlatformChatStreamActions(deps)

    await expect(actions.retryMessage('ai-1')).resolves.toBe(true)
    expect(deps.stream.submit).toHaveBeenCalledWith(
      undefined,
      expect.objectContaining({
        forkFrom: 'checkpoint-parent',
        config: {
          configurable: {
            platform_runtime: { enable_tools: false }
          }
        }
      })
    )

    await expect(
      actions.resumeAllInterruptedRuns({
        'interrupt-a': { decisions: [{ type: 'approve' }] },
        'interrupt-b': { decisions: [{ type: 'reject', message: 'no' }] }
      })
    ).resolves.toBe(true)
    expect(deps.stream.respondAll).toHaveBeenCalledWith(
      expect.objectContaining({
        'interrupt-a': expect.any(Object),
        'interrupt-b': expect.any(Object)
      }),
      expect.objectContaining({ config: expect.any(Object) })
    )
  })

  it('resumes a hydrated persisted interrupt through the SDK protocol action', async () => {
    const deps = createDeps()
    deps.interruptPayload = computed(() => ({ id: 'interrupt-a' }))
    const actions = createPlatformChatStreamActions(deps)

    await expect(
      actions.resumeInterruptedRun(
        { decisions: [{ type: 'approve' }] },
        'interrupt-a'
      )
    ).resolves.toBe(true)

    expect(deps.stream.respond).toHaveBeenCalledWith(
      { decisions: [{ type: 'approve' }] },
      expect.objectContaining({
        interruptId: 'interrupt-a'
      })
    )
  })
})
