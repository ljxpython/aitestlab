import { computed, reactive, ref, watch, type ComputedRef, type Ref } from 'vue'
import { listRuntimeModelPolicies } from '@/services/runtime-policies/runtime-policies.service'
import { listRuntimeModels } from '@/services/runtime/runtime.service'
import {
  normalizeRuntimeGatewayError,
  resolveRuntimePermissionDescription,
  updateRuntimeThreadState
} from '@/services/runtime-gateway/workspace.service'
import type { ManagementThread } from '@/types/management'
import { summarizeMessageContent } from '@/utils/chat-content'
import type { ChatMessageMetadata } from '../branching'
import { resolveChatDefaultModelId } from '../runtime-model-default'
import { useChatThreadWorkspace } from './useChatThreadWorkspace'
import { usePlatformChatStream } from './usePlatformChatStream'
import type { ChatResolvedTarget, ChatRunOptions } from '../types'

type UseChatWorkspaceOptions = {
  projectId: ComputedRef<string>
  target: ComputedRef<ChatResolvedTarget | null>
  initialThreadId: Ref<string>
  startNewThreadOnLoad?: Ref<boolean>
}

export function useChatWorkspace(options: UseChatWorkspaceOptions) {
  // Validate the URL thread against the project thread list before handing it to
  // useStream. Otherwise a stale/deleted URL thread makes the SDK issue 404
  // state/stream requests before the list loader can select a valid thread.
  const activeThreadId = ref('')
  const activeThread = ref<ManagementThread | null>(null)
  const selectedBranch = ref('')
  const historyItems = ref<Record<string, unknown>[]>([])
  const loadingRuntime = ref(false)
  const runtimeError = ref('')
  const defaultModelId = ref('')
  const runOptions = reactive<ChatRunOptions>({
    modelId: '',
    systemPrompt: '',
    enableTools: false,
    toolNames: [],
    temperature: '',
    maxTokens: ''
  })
  const runtimeModels = ref(awaitableEmptyModels())

  const streamState = usePlatformChatStream({
    projectId: computed(() => options.projectId.value),
    target: computed(() => options.target.value),
    activeThreadId,
    activeThreadStatus: computed(() => activeThread.value?.status || null),
    activeThreadError: computed(() => activeThread.value?.error || null),
    historyItems,
    selectedBranch,
    runOptions,
    onRefreshThread: async (threadId, loadOptions) => {
      await threadWorkspace.syncActiveThreadFromList(threadId, loadOptions)
    }
  })

  const threadWorkspace = useChatThreadWorkspace({
    projectId: computed(() => options.projectId.value),
    target: computed(() => options.target.value),
    activeThreadId,
    activeThread,
    selectedBranch,
    historyItems,
    displayState: streamState.displayState,
    clearStreamDetailFeedback: streamState.clearDetailFeedback,
    resetStreamView: streamState.resetStreamView,
    streamDetailError: streamState.detailError,
    streamDetailInfo: streamState.detailInfo
  })

  const canStartThread = computed(
    () => Boolean(options.projectId.value && options.target.value) && !streamState.sending.value
  )
  const canSend = computed(
    () => Boolean(options.projectId.value && options.target.value) && !streamState.sending.value
  )
  const accessDeniedMessage = computed(() => {
    const permissionError = threadWorkspace.detailErrorMeta.value || threadWorkspace.threadErrorMeta.value
    return resolveRuntimePermissionDescription(permissionError)
  })

  async function loadRuntimeCatalog() {
    const projectId = options.projectId.value.trim()
    if (!projectId) {
      runtimeModels.value = awaitableEmptyModels()
      defaultModelId.value = ''
      runtimeError.value = ''
      return
    }

    loadingRuntime.value = true
    runtimeError.value = ''

    try {
      const [modelsPayload, modelPoliciesPayload] = await Promise.all([
        listRuntimeModels(projectId),
        listRuntimeModelPolicies(projectId).catch(() => null)
      ])
      runtimeModels.value = Array.isArray(modelsPayload.models) ? modelsPayload.models : awaitableEmptyModels()
      const modelPolicies = Array.isArray(modelPoliciesPayload?.items) ? modelPoliciesPayload.items : []
      defaultModelId.value = resolveChatDefaultModelId(runtimeModels.value, modelPolicies)

      if (!runOptions.modelId.trim()) {
        runOptions.modelId = defaultModelId.value
      }
    } catch (loadError) {
      const normalizedError = normalizeRuntimeGatewayError(loadError, '运行时目录加载失败')
      runtimeModels.value = awaitableEmptyModels()
      defaultModelId.value = ''
      runtimeError.value = normalizedError.message
    } finally {
      loadingRuntime.value = false
    }
  }

  async function updateThreadStatePatch(values: Record<string, unknown>) {
    const projectId = options.projectId.value.trim()
    const threadId = activeThreadId.value.trim()

    if (!projectId || !threadId) {
      throw new Error('缺少可更新的线程上下文')
    }

    await updateRuntimeThreadState(projectId, threadId, values)
    await threadWorkspace.syncActiveThreadFromList(threadId)
    return true
  }

  function selectBranch(branch: string) {
    threadWorkspace.stageSelectedBranch(branch)
    streamState.selectBranch(selectedBranch.value)
  }

  watch(
    [
      () => options.projectId.value,
      () => options.target.value?.resolvedTargetId,
      () => options.startNewThreadOnLoad?.value ?? false
    ],
    async () => {
      const startNewThread = options.startNewThreadOnLoad?.value ?? false
      const initialThreadId = startNewThread ? '' : options.initialThreadId.value
      threadWorkspace.resetForContextChange('')
      await Promise.all([
        loadRuntimeCatalog(),
        threadWorkspace.loadThreadList(initialThreadId, { selectLatest: !startNewThread })
      ])
    },
    { immediate: true }
  )

  watch(
    () => options.initialThreadId.value,
    async (nextThreadId) => {
      const normalizedThreadId = nextThreadId.trim()
      if (!normalizedThreadId) {
        if (activeThreadId.value) {
          threadWorkspace.clearActiveThreadState()
        }
        return
      }

      if (normalizedThreadId === activeThreadId.value) {
        return
      }

      if (threadWorkspace.threadItems.value.some((item) => item.thread_id === normalizedThreadId)) {
        await threadWorkspace.syncActiveThreadFromList(normalizedThreadId)
        return
      }

      await threadWorkspace.loadThreadList(normalizedThreadId)
    }
  )

  watch(
    () => streamState.displayState.value,
    () => {
      if (activeThreadId.value.trim()) {
        threadWorkspace.syncActiveThreadFromHistory(activeThreadId.value)
      }
    },
    { deep: true }
  )

  return {
    activeThreadId,
    activeThread,
    activeState: streamState.displayState,
    displayState: streamState.displayState,
    canSend,
    canStartThread,
    creatingThread: computed(() => false),
    cancelActiveRun: streamState.cancelActiveRun,
    accessDeniedMessage,
    detailError: streamState.detailError,
    detailInfo: streamState.detailInfo,
    defaultModelId,
    detailWarning: threadWorkspace.detailWarning,
    deleteThread: threadWorkspace.deleteThread,
    editHumanMessage: streamState.editHumanMessage,
    error: threadWorkspace.error,
    historyItems,
    interruptPayload: streamState.interruptPayload,
    isViewingBranch: streamState.isViewingBranch,
    lastEventAt: streamState.lastEventAt,
    lastRunId: streamState.lastRunId,
    loadingRuntime,
    loadingThreadDetail: threadWorkspace.loadingThreadDetail,
    loadingThreads: threadWorkspace.loadingThreads,
    messageMetadataById: streamState.messageMetadataById as ComputedRef<Record<string, ChatMessageMetadata>>,
    messages: streamState.messages,
    refreshActiveThread: threadWorkspace.refreshActiveThread,
    retryMessage: streamState.retryMessage,
    runOptions,
    runtimeError,
    runtimeModels,
    cancelling: streamState.cancelling,
    selectedBranch,
    selectBranch,
    selectThread: threadWorkspace.selectThread,
    selectedThreadSummary: threadWorkspace.selectedThreadSummary,
    sendMessage: streamState.sendMessage,
    sending: streamState.sending,
    startNewThread: threadWorkspace.startNewThread,
    threadFailureMessage: streamState.threadFailureMessage,
    threadItems: threadWorkspace.threadItems,
    threadSummary: threadWorkspace.threadSummary,
    resumeInterruptedRun: streamState.resumeInterruptedRun,
    resumeAllInterruptedRuns: streamState.resumeAllInterruptedRuns,
    streamHandle: streamState.streamHandle,
    toolCalls: streamState.toolCalls,
    updateThreadStatePatch,
    targetText: computed(() => options.target.value?.label || '--'),
    targetTypeText: computed(() => (options.target.value?.targetType === 'graph' ? 'Graph' : 'Assistant')),
    latestMessagePreview: computed(() => {
      const preview = streamState.latestMessagePreview.value
      return preview || summarizeMessageContent(activeThread.value?.values)
    })
  }
}

function awaitableEmptyModels() {
  return [] as Awaited<ReturnType<typeof listRuntimeModels>>['models']
}
