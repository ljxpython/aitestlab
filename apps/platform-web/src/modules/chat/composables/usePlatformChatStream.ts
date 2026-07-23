import { useStream } from '@langchain/vue'
import type { Checkpoint, Message } from '@langchain/langgraph-sdk'
import { computed, ref, watch, type WritableComputedRef } from 'vue'
import { createLanggraphClient } from '@/services/langgraph/client'
import { normalizeRuntimeGatewayError } from '@/services/runtime-gateway/workspace.service'
import { summarizeMessageContent, type ChatAttachmentBlock } from '@/utils/chat-content'
import type { ChatMessageMetadata } from '../branching'
import { createPlatformChatStreamActions } from './platform-chat-stream/actions'
import {
  extractInterruptPayload,
  extractThreadFailureMessage,
  getMetadataCheckpointId,
  isAbortLikeError,
  isBreakpointInterrupt,
  toLegacyMessage
} from './platform-chat-stream/helpers'
import type { ChatState, UsePlatformChatStreamOptions } from './platform-chat-stream/types'

export function usePlatformChatStream(options: UsePlatformChatStreamOptions) {
  const sending = ref(false)
  const cancelling = ref(false)
  const detailError = ref('')
  const detailInfo = ref('')
  const lastRunId = ref('')
  const currentRunId = ref('')
  const lastEventAt = ref('')

  const langgraphClient = computed(() => createLanggraphClient(options.projectId.value.trim() || undefined))
  const stream = useStream<ChatState>({
    client: langgraphClient,
    assistantId: computed(() => options.target.value?.resolvedTargetId || ''),
    threadId: computed(() => options.activeThreadId.value || null),
    messagesKey: 'messages',
    fetchStateHistory: { limit: 20 },
    reconnectOnMount: true,
    initialValues: {
      messages: []
    },
    onThreadId: (threadId) => {
      options.activeThreadId.value = threadId
      lastRunId.value = ''
      detailInfo.value = ''
    },
    onCreated: (run) => {
      const runId = run?.run_id?.trim() || ''
      currentRunId.value = runId
      lastRunId.value = runId
    },
    onMetadataEvent: (payload) => {
      const runId =
        payload && typeof payload === 'object' && typeof (payload as { run_id?: unknown }).run_id === 'string'
          ? ((payload as { run_id?: string }).run_id || '').trim()
          : ''
      if (runId) {
        currentRunId.value = runId
        lastRunId.value = runId
      }
    },
    onFinish: async () => {
      sending.value = false
      cancelling.value = false
      currentRunId.value = ''
      lastEventAt.value = new Date().toISOString()
      await options.onRefreshThread(options.activeThreadId.value)
    },
    onError: async (streamError) => {
      if (!isAbortLikeError(streamError)) {
        detailError.value = normalizeRuntimeGatewayError(streamError, '对话运行失败').message
      } else if (cancelling.value) {
        detailInfo.value = '本轮运行已取消。输入框里的草稿已保留，你可以继续修改后重新发送。'
      }

      sending.value = false
      cancelling.value = false
      currentRunId.value = ''
      await options.onRefreshThread(options.activeThreadId.value, { preserveInfo: true })
    }
  })

  const displayState = computed<Record<string, unknown> | null>(() => {
    const values = stream.values.value
    if (!values || typeof values !== 'object') {
      return null
    }

    return values as Record<string, unknown>
  })

  const displayStateRaw = computed<Record<string, unknown> | null>(() => {
    const values = displayState.value
    if (!values) {
      return null
    }

    return {
      ...values,
      interrupt: stream.interrupt.value,
      tasks: (displayState.value?.tasks as unknown) || undefined
    }
  })

  const messages = computed<Message[]>(() => stream.messages.value.map((message) => toLegacyMessage(message)))

  const messageMetadataById = computed<Record<string, ChatMessageMetadata>>(() => {
    const metadataById: Record<string, ChatMessageMetadata> = {}

    stream.messages.value.forEach((message, index) => {
      const metadata = stream.getMessagesMetadata(message, index)
      const messageId = typeof message.id === 'string' && message.id.trim() ? message.id : `message-${index}`
      metadataById[messageId] = {
        messageId,
        checkpointId: getMetadataCheckpointId(metadata),
        firstSeenState: metadata?.firstSeenState as ChatMessageMetadata['firstSeenState'],
        parentCheckpoint:
          (metadata?.firstSeenState?.parent_checkpoint as Checkpoint | null | undefined) || null,
        branch: metadata?.branch,
        branchOptions: metadata?.branchOptions
      }
    })

    return metadataById
  })

  const interruptPayload = computed(() => {
    const interrupt = stream.interrupt.value
    if (interrupt !== undefined) {
      return interrupt
    }
    return extractInterruptPayload(displayStateRaw.value)
  })

  const threadFailureMessage = computed(() =>
    extractThreadFailureMessage(
      displayStateRaw.value,
      options.activeThreadStatus.value,
      options.activeThreadError.value
    )
  )
  const hasBreakpointInterrupt = computed(() => isBreakpointInterrupt(interruptPayload.value))
  const canContinueDebug = computed(() => {
    if (!options.runOptions.debugMode || sending.value) {
      return false
    }

    if (interruptPayload.value !== undefined) {
      return hasBreakpointInterrupt.value
    }

    return options.activeThreadStatus.value === 'interrupted'
  })

  const isViewingBranch = computed(() => options.selectedBranch.value.trim().length > 0)
  const actions = createPlatformChatStreamActions({
    stream,
    options,
    sending,
    cancelling,
    detailError,
    detailInfo,
    lastRunId,
    currentRunId,
    lastEventAt,
    messages,
    messageMetadataById,
    interruptPayload
  })

  watch(
    () => stream.branch.value,
    (nextBranch) => {
      const normalizedBranch = nextBranch.trim()
      if (options.selectedBranch.value !== normalizedBranch) {
        options.selectedBranch.value = normalizedBranch
      }
    }
  )

  watch(
    () => stream.history.value,
    (nextHistory) => {
      options.historyItems.value = Array.isArray(nextHistory)
        ? nextHistory.map((entry) => entry as unknown as Record<string, unknown>)
        : []
    },
    { immediate: true }
  )

  watch(
    () => stream.isLoading.value,
    (isLoading) => {
      sending.value = isLoading
      if (isLoading) {
        lastEventAt.value = new Date().toISOString()
      }
    },
    { immediate: true }
  )

  return {
    canContinueDebug,
    cancelling,
    cancelActiveRun: actions.cancelActiveRun,
    clearDetailFeedback: actions.clearDetailFeedback,
    continueDebugRun: () => (canContinueDebug.value ? actions.continueDebugRun() : Promise.resolve(false)),
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
    messageMetadataById: messageMetadataById as WritableComputedRef<Record<string, ChatMessageMetadata>>,
    messages,
    resetStreamView: actions.resetStreamView,
    resumeInterruptedRun: actions.resumeInterruptedRun,
    retryMessage: actions.retryMessage,
    selectBranch: actions.selectBranch,
    selectedBranch: options.selectedBranch,
    sendMessage: (content: string, attachments: ChatAttachmentBlock[] = []) =>
      actions.sendMessage(content, attachments),
    sending,
    switchThread: actions.switchThread,
    threadFailureMessage
  }
}
