import { useStream } from '@langchain/vue'
import type { Message } from '@langchain/langgraph-sdk'
import { computed, ref, watch } from 'vue'
import {
  createLanggraphAuthorizedFetch,
  getLanggraphApiUrl
} from '@/services/langgraph/client'
import { normalizeRuntimeGatewayError } from '@/services/runtime-gateway/workspace.service'
import { summarizeMessageContent, type ChatAttachmentBlock } from '@/utils/chat-content'
import {
  buildChatMessageMetadata,
  getChatBranchContext,
  normalizeHistoryStates
} from '../branching'
import { createPlatformChatStreamActions } from './platform-chat-stream/actions'
import {
  extractInterruptPayload,
  extractThreadFailureMessage,
  toLegacyMessage
} from './platform-chat-stream/helpers'
import type { ChatState, UsePlatformChatStreamOptions } from './platform-chat-stream/types'

export function usePlatformChatStream(options: UsePlatformChatStreamOptions) {
  const commandPending = ref(false)
  const cancelling = ref(false)
  const detailError = ref('')
  const detailInfo = ref('')
  const lastRunId = ref('')
  const lastEventAt = ref('')

  const authorizedFetch = createLanggraphAuthorizedFetch()
  const scopedFetch: typeof fetch = (input, init) => {
    const headers = new Headers(init?.headers)
    const projectId = options.projectId.value.trim()
    if (projectId) {
      headers.set('x-project-id', projectId)
    } else {
      headers.delete('x-project-id')
    }
    return authorizedFetch(input, { ...init, headers })
  }

  const stream = useStream<ChatState>({
    apiUrl: getLanggraphApiUrl(),
    callerOptions: { fetch: scopedFetch },
    fetch: scopedFetch,
    assistantId: options.target.value?.resolvedTargetId || '',
    threadId: () => options.activeThreadId.value || null,
    messagesKey: 'messages',
    initialValues: {
      messages: []
    },
    onThreadId: (threadId) => {
      options.activeThreadId.value = threadId
      lastRunId.value = ''
      detailInfo.value = ''
    },
    onCreated: ({ runId }) => {
      commandPending.value = false
      lastRunId.value = runId.trim()
    },
    onCompleted: async ({ reason }) => {
      const completedError =
        reason === 'error' && stream.error.value !== undefined && stream.error.value !== null
          ? normalizeRuntimeGatewayError(stream.error.value, '对话运行失败').message
          : ''
      commandPending.value = false
      cancelling.value = false
      lastEventAt.value = new Date().toISOString()

      if (reason === 'stopped') {
        detailInfo.value = '本轮运行已取消。输入框已恢复可编辑，你可以继续发送消息。'
      }

      await options.onRefreshThread(options.activeThreadId.value, {
        preserveInfo: reason === 'stopped'
      })

      if (completedError) {
        detailError.value = completedError
      }
    }
  })

  const historyStates = computed(() => normalizeHistoryStates(options.historyItems.value))
  const streamMatchesActiveThread = computed(() => {
    const activeThreadId = options.activeThreadId.value.trim()
    return Boolean(activeThreadId) && stream.threadId.value === activeThreadId
  })
  const branchContext = computed(() =>
    getChatBranchContext(options.selectedBranch.value, historyStates.value)
  )
  const selectedBranchValues = computed<Record<string, unknown> | null>(() => {
    if (!options.selectedBranch.value.trim()) {
      return null
    }

    const values = branchContext.value.threadHead?.values
    return values && typeof values === 'object' ? (values as Record<string, unknown>) : null
  })
  const persistedHeadState = computed<Record<string, unknown> | null>(() => {
    const head = branchContext.value.threadHead
    const values = head?.values
    if (!values || typeof values !== 'object') {
      return null
    }
    const persistedHead = head as unknown as Record<string, unknown>

    return {
      ...(values as Record<string, unknown>),
      interrupts: persistedHead.interrupts,
      tasks: persistedHead.tasks
    }
  })
  const displayState = computed<Record<string, unknown> | null>(() => {
    const liveValues = streamMatchesActiveThread.value ? stream.values.value : null
    const values =
      selectedBranchValues.value ||
      (stream.isLoading.value ? liveValues : persistedHeadState.value) ||
      liveValues
    return values && typeof values === 'object' ? (values as Record<string, unknown>) : null
  })
  const messages = computed<Message[]>(() => {
    const branchMessages = selectedBranchValues.value?.messages
    if (Array.isArray(branchMessages)) {
      return branchMessages as Message[]
    }

    const liveMessages = streamMatchesActiveThread.value
      ? stream.messages.value.map((message) => toLegacyMessage(message))
      : []
    if (stream.isLoading.value || liveMessages.length > 0) {
      return liveMessages
    }

    const persistedMessages = persistedHeadState.value?.messages
    return Array.isArray(persistedMessages) ? (persistedMessages as Message[]) : liveMessages
  })
  const messageMetadataById = computed(() =>
    buildChatMessageMetadata(messages.value, historyStates.value, branchContext.value)
  )

  const interruptPayload = computed(() => {
    const liveInterrupts = streamMatchesActiveThread.value ? stream.interrupts.value : []
    if (liveInterrupts.length === 1) {
      return liveInterrupts[0]
    }
    if (liveInterrupts.length > 1) {
      return liveInterrupts
    }

    return extractInterruptPayload({
      ...(displayState.value || {}),
      tasks: displayState.value?.tasks
    })
  })
  const threadFailureMessage = computed(() =>
    extractThreadFailureMessage(
      displayState.value,
      options.activeThreadStatus.value,
      options.activeThreadError.value
    )
  )
  const isViewingBranch = computed(() => options.selectedBranch.value.trim().length > 0)
  const sending = computed(() => commandPending.value || stream.isLoading.value)
  const actions = createPlatformChatStreamActions({
    stream,
    options,
    commandPending,
    isBusy: sending,
    cancelling,
    detailError,
    detailInfo,
    lastRunId,
    lastEventAt,
    messages,
    messageMetadataById,
    interruptPayload
  })

  watch(
    () => stream.isLoading.value,
    (isLoading) => {
      if (isLoading) {
        commandPending.value = false
        lastEventAt.value = new Date().toISOString()
      }
    },
    { immediate: true }
  )

  watch(
    () => stream.error.value,
    (streamError) => {
      if (streamError !== undefined && streamError !== null) {
        detailError.value = normalizeRuntimeGatewayError(streamError, '对话运行失败').message
      }
    }
  )

  return {
    cancelling,
    cancelActiveRun: actions.cancelActiveRun,
    clearDetailFeedback: actions.clearDetailFeedback,
    detailError,
    detailInfo,
    displayState,
    editHumanMessage: actions.editHumanMessage,
    historyItems: options.historyItems,
    interruptPayload,
    isViewingBranch,
    lastEventAt,
    lastRunId,
    latestMessagePreview: computed(() => {
      const lastMessage = messages.value[messages.value.length - 1]
      return lastMessage ? summarizeMessageContent(lastMessage.content) : ''
    }),
    messageMetadataById,
    messages,
    resetStreamView: actions.resetStreamView,
    resumeAllInterruptedRuns: actions.resumeAllInterruptedRuns,
    resumeInterruptedRun: actions.resumeInterruptedRun,
    retryMessage: actions.retryMessage,
    selectBranch: actions.selectBranch,
    selectedBranch: options.selectedBranch,
    sendMessage: (content: string, attachments: ChatAttachmentBlock[] = []) =>
      actions.sendMessage(content, attachments),
    sending,
    streamHandle: stream,
    threadFailureMessage,
    toolCalls: computed(() =>
      streamMatchesActiveThread.value ? stream.toolCalls.value : []
    )
  }
}
