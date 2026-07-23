import type { AIMessage, BaseMessage, ToolMessage } from '@langchain/core/messages'
import type { Checkpoint, Message } from '@langchain/langgraph-sdk'
import type { ComputedRef, Ref } from 'vue'
import type { ChatAttachmentBlock } from '@/utils/chat-content'
import type { ChatMessageMetadata } from '../../branching'
import type { ChatResolvedTarget, ChatRunOptions } from '../../types'

export type ChatState = Record<string, unknown> & {
  messages?: Message[]
  todos?: unknown
  files?: unknown
  ui?: unknown
}

export type UsePlatformChatStreamOptions = {
  projectId: ComputedRef<string>
  target: ComputedRef<ChatResolvedTarget | null>
  activeThreadId: Ref<string>
  activeThreadStatus: ComputedRef<string | null>
  activeThreadError: ComputedRef<Record<string, unknown> | string | null | undefined>
  historyItems: Ref<Record<string, unknown>[]>
  selectedBranch: Ref<string>
  runOptions: ChatRunOptions
  onRefreshThread: (threadId: string, loadOptions?: { preserveInfo?: boolean }) => Promise<void>
}

export type PlatformChatStreamLike = {
  branch: Ref<string>
  messages: Ref<BaseMessage[]>
  setBranch: (branch: string) => void
  stop: () => void
  submit: (
    payload?: Record<string, unknown> | null,
    options?: Record<string, unknown>
  ) => Promise<unknown>
  switchThread: (threadId: string | null) => void
}

export type PlatformChatStreamActionDeps = {
  stream: PlatformChatStreamLike
  options: UsePlatformChatStreamOptions
  sending: Ref<boolean>
  cancelling: Ref<boolean>
  detailError: Ref<string>
  detailInfo: Ref<string>
  lastRunId: Ref<string>
  currentRunId: Ref<string>
  lastEventAt: Ref<string>
  messages: ComputedRef<Message[]>
  messageMetadataById: ComputedRef<Record<string, ChatMessageMetadata>>
  interruptPayload: ComputedRef<unknown>
}

export type {
  AIMessage,
  BaseMessage,
  ChatAttachmentBlock,
  Checkpoint,
  Message,
  ToolMessage
}
