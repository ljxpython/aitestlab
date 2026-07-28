import type { AIMessage, BaseMessage, ToolMessage } from '@langchain/core/messages'
import type { Checkpoint, Message } from '@langchain/langgraph-sdk'
import type { StreamRespondAllOptions, StreamRespondOptions, StreamStopOptions, StreamSubmitOptions } from '@langchain/langgraph-sdk/stream'
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
  messages: Readonly<Ref<BaseMessage[]>>
  stop: (options?: StreamStopOptions) => Promise<void>
  submit: (
    payload?: Record<string, unknown> | null,
    options?: StreamSubmitOptions<ChatState>
  ) => Promise<void>
  respond: (response: unknown, options?: StreamRespondOptions) => Promise<void>
  respondAll: (responsesById: Record<string, unknown>, options?: StreamRespondAllOptions) => Promise<void>
}

export type PlatformChatStreamActionDeps = {
  stream: PlatformChatStreamLike
  options: UsePlatformChatStreamOptions
  commandPending: Ref<boolean>
  isBusy: ComputedRef<boolean>
  cancelling: Ref<boolean>
  detailError: Ref<string>
  detailInfo: Ref<string>
  lastRunId: Ref<string>
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
