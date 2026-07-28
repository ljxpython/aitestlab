import type { Message } from '@langchain/langgraph-sdk'
import type { Ref } from 'vue'
import type { ChatMessageMetadata } from './branching'
import { getMessageAttachments, getMessageText } from '@/utils/threads'

type MessageActionContext = {
  messageMetadataById: Ref<Record<string, ChatMessageMetadata>>
  sending: Ref<boolean>
  hasBlockingInterrupt: Ref<boolean>
  editingMessageId: Ref<string>
  editingMessageValue: Ref<string>
  selectBranch: (branch: string) => void
  retryMessage: (messageId: string, forkFrom?: string) => Promise<boolean>
  editHumanMessage: (messageId: string, content: Message['content'], forkFrom?: string) => Promise<boolean>
}

export function buildEditedMessageContent(message: Message, nextText: string): Message['content'] {
  const normalizedText = nextText.trim()

  if (Array.isArray(message.content)) {
    const attachments = getMessageAttachments(message.content)
    return normalizedText
      ? ([{ type: 'text', text: normalizedText }, ...attachments] as Message['content'])
      : (attachments as unknown as Message['content'])
  }

  return normalizedText
}

export function createChatMessageActions(context: MessageActionContext) {
  function getMessageMeta(messageId: string): ChatMessageMetadata | undefined {
    return context.messageMetadataById.value[messageId]
  }

  function getMessageBranchIndex(messageId: string) {
    const meta = getMessageMeta(messageId)
    if (!meta?.branchOptions?.length) {
      return -1
    }
    return meta.branchOptions.indexOf(meta.branch || '')
  }

  function hasBranchSwitcher(messageId: string) {
    return (getMessageMeta(messageId)?.branchOptions?.length || 0) > 1
  }

  function selectPreviousMessageBranch(messageId: string) {
    const meta = getMessageMeta(messageId)
    const branchIndex = getMessageBranchIndex(messageId)
    if (!meta?.branchOptions || branchIndex <= 0) {
      return
    }

    context.selectBranch(meta.branchOptions[branchIndex - 1] || '')
  }

  function selectNextMessageBranch(messageId: string) {
    const meta = getMessageMeta(messageId)
    const branchIndex = getMessageBranchIndex(messageId)
    if (!meta?.branchOptions || branchIndex < 0 || branchIndex >= meta.branchOptions.length - 1) {
      return
    }

    context.selectBranch(meta.branchOptions[branchIndex + 1] || '')
  }

  function canEditMessage(message: Message, messageId: string, parentCheckpointId?: string) {
    const meta = getMessageMeta(messageId)
    return (
      message.type === 'human' &&
      !context.sending.value &&
      !context.hasBlockingInterrupt.value &&
      Boolean(parentCheckpointId?.trim() || meta?.parentCheckpoint?.checkpoint_id?.trim())
    )
  }

  function canRetryMessage(message: Message, messageId: string, parentCheckpointId?: string) {
    const meta = getMessageMeta(messageId)
    return (
      message.type === 'ai' &&
      !context.sending.value &&
      !context.hasBlockingInterrupt.value &&
      Boolean(parentCheckpointId?.trim() || meta?.parentCheckpoint?.checkpoint_id?.trim())
    )
  }

  function startEditMessage(message: Message, messageId: string) {
    if (!canEditMessage(message, messageId)) {
      return
    }

    context.editingMessageId.value = messageId
    context.editingMessageValue.value = getMessageText(message.content)
  }

  function cancelEditMessage() {
    context.editingMessageId.value = ''
    context.editingMessageValue.value = ''
  }

  async function submitEditMessage(message: Message, messageId: string, parentCheckpointId?: string) {
    if (context.editingMessageId.value !== messageId) {
      return {
        ok: false as const,
        reason: 'not-editing'
      }
    }

    const nextContent = buildEditedMessageContent(message, context.editingMessageValue.value)
    const hasText = getMessageText(nextContent).trim().length > 0
    const hasAttachments = Array.isArray(nextContent) && getMessageAttachments(nextContent).length > 0

    if (!hasText && !hasAttachments) {
      return {
        ok: false as const,
        reason: 'empty-content'
      }
    }

    const updated = parentCheckpointId
      ? await context.editHumanMessage(messageId, nextContent, parentCheckpointId)
      : await context.editHumanMessage(messageId, nextContent)
    if (updated) {
      cancelEditMessage()
      return {
        ok: true as const
      }
    }

    return {
      ok: false as const,
      reason: 'edit-failed'
    }
  }

  async function handleRetryMessage(messageId: string, parentCheckpointId?: string) {
    return parentCheckpointId
      ? await context.retryMessage(messageId, parentCheckpointId)
      : await context.retryMessage(messageId)
  }

  return {
    getMessageMeta,
    getMessageBranchIndex,
    hasBranchSwitcher,
    selectPreviousMessageBranch,
    selectNextMessageBranch,
    canEditMessage,
    canRetryMessage,
    startEditMessage,
    cancelEditMessage,
    submitEditMessage,
    handleRetryMessage
  }
}
