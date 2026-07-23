import type { Message } from '@langchain/langgraph-sdk'
import type { ChatAttachmentBlock } from '@/utils/chat-content'
import type { ChatResolvedTarget } from '../../types'
import type { AIMessage, BaseMessage, ToolMessage } from './types'

function unwrapInterruptPayload(interrupt: unknown): unknown {
  if (Array.isArray(interrupt)) {
    return interrupt.map(unwrapInterruptPayload)
  }
  if (
    interrupt &&
    typeof interrupt === 'object' &&
    'value' in interrupt &&
    (interrupt as { value?: unknown }).value !== undefined
  ) {
    return (interrupt as { value?: unknown }).value
  }
  return interrupt
}

function hasMeaningfulInterruptPayload(interrupt: unknown): boolean {
  const payload = unwrapInterruptPayload(interrupt)

  if (Array.isArray(payload)) {
    return payload.some((item) => hasMeaningfulInterruptPayload(item))
  }

  if (!payload) {
    return false
  }

  if (typeof payload === 'object') {
    return Object.keys(payload as Record<string, unknown>).length > 0
  }

  return true
}

export function isBreakpointInterrupt(interrupt: unknown): boolean {
  const payload = unwrapInterruptPayload(interrupt)
  if (Array.isArray(payload)) {
    return payload.length > 0 && payload.every((item) => isBreakpointInterrupt(item))
  }
  if (!payload || typeof payload !== 'object') {
    return false
  }
  return (payload as Record<string, unknown>).when === 'breakpoint'
}

export function extractInterruptPayload(state?: Record<string, unknown> | null): unknown {
  if (!state || typeof state !== 'object') {
    return undefined
  }

  if ('__interrupt__' in state && hasMeaningfulInterruptPayload(state.__interrupt__)) {
    return state.__interrupt__
  }

  if ('interrupt' in state && hasMeaningfulInterruptPayload(state.interrupt)) {
    return state.interrupt
  }

  if ('interrupts' in state && hasMeaningfulInterruptPayload(state.interrupts)) {
    return state.interrupts
  }

  const tasks = Array.isArray(state.tasks) ? state.tasks : []
  const taskInterrupts = tasks
    .map((task) => {
      if (!task || typeof task !== 'object') {
        return undefined
      }
      return (task as { interrupts?: unknown }).interrupts
    })
    .filter((item) => hasMeaningfulInterruptPayload(item))

  if (taskInterrupts.length === 1) {
    return taskInterrupts[0]
  }

  if (taskInterrupts.length > 1) {
    return taskInterrupts
  }

  return undefined
}

function extractErrorText(value: unknown): string {
  if (typeof value === 'string') {
    return value.trim()
  }

  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return ''
  }

  const record = value as Record<string, unknown>
  for (const key of ['error', 'message', 'detail']) {
    const candidate = record[key]
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim()
    }
  }

  return ''
}

function extractStringField(record: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const candidate = record[key]
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim()
    }
  }

  return ''
}

function isCancelledRunMessage(message: string): boolean {
  return /cancellederror|aborterror|cancelled|canceled|aborted/i.test(message.trim())
}

function isGenericInternalErrorMessage(message: string): boolean {
  return /^an internal error occurred$/i.test(message.trim())
}

function extractRuntimeErrorText(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return extractErrorText(value)
  }

  const record = value as Record<string, unknown>
  const errorType = extractStringField(record, ['error', 'type', 'name', 'code'])
  const errorMessage = extractStringField(record, ['message', 'detail'])

  if (isCancelledRunMessage(`${errorType} ${errorMessage}`)) {
    return ''
  }

  if (/^APIConnectionError$/i.test(errorType)) {
    return '模型上游连接失败：OpenAI 兼容模型代理连接异常，请检查当前模型的 base_url、API key、模型名和网络。'
  }

  if (errorMessage && !isGenericInternalErrorMessage(errorMessage)) {
    return errorMessage
  }

  if (errorType && !isGenericInternalErrorMessage(errorType)) {
    return errorMessage && errorMessage !== errorType ? `${errorType}: ${errorMessage}` : errorType
  }

  return errorMessage || extractErrorText(value)
}

export function extractThreadFailureMessage(
  state?: Record<string, unknown> | null,
  threadStatus?: string | null,
  threadError?: Record<string, unknown> | string | null
): string {
  const tasks = Array.isArray(state?.tasks) ? state.tasks : []
  let cancelledRunDetected = false
  for (const task of tasks) {
    if (!task || typeof task !== 'object') {
      continue
    }

    const taskError = extractRuntimeErrorText((task as Record<string, unknown>).error)
    if (taskError) {
      if (isCancelledRunMessage(taskError)) {
        cancelledRunDetected = true
        continue
      }
      return taskError
    }
  }

  const stateError = extractRuntimeErrorText(state?.error)
  if (stateError) {
    if (isCancelledRunMessage(stateError)) {
      return ''
    }
    return stateError
  }

  const runtimeThreadError = extractRuntimeErrorText(threadError)
  if (runtimeThreadError) {
    if (isCancelledRunMessage(runtimeThreadError)) {
      return ''
    }
    return runtimeThreadError
  }

  if (cancelledRunDetected) {
    return ''
  }

  return threadStatus === 'error' ? '最近一次运行失败，请查看线程状态后继续。' : ''
}

export function hasPendingTaskToolCall(messages: BaseMessage[]): boolean {
  const resolvedToolCallIds = new Set<string>()

  for (const message of messages) {
    if (message.getType() === 'tool') {
      const toolMessage = message as ToolMessage
      if (typeof toolMessage.tool_call_id === 'string' && toolMessage.tool_call_id.trim()) {
        resolvedToolCallIds.add(toolMessage.tool_call_id)
      }
    }
  }

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message?.getType() !== 'ai') {
      continue
    }

    const toolCalls = ((message as AIMessage).tool_calls || []) as Array<{
      id?: string
      name?: string
    }>

    for (const toolCall of toolCalls) {
      if (!toolCall) {
        continue
      }
      const unresolved = !toolCall.id || !resolvedToolCallIds.has(toolCall.id)
      if (unresolved && toolCall.name === 'task') {
        return true
      }
    }
  }

  return false
}

export function isAbortLikeError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true
  }
  if (error instanceof Error && /aborted|aborterror|cancelled|canceled/i.test(error.name + error.message)) {
    return true
  }
  return false
}

export function toLegacyMessage(message: BaseMessage): Message {
  return {
    ...((message.toDict().data as unknown) as Record<string, unknown>),
    type: message.getType() as Message['type']
  } as Message
}

export function createThreadMetadata(target: ChatResolvedTarget) {
  if (target.targetType === 'graph') {
    return {
      target_type: 'graph',
      target_display_name: target.displayName,
      assistant_id: target.resolvedTargetId,
      graph_id: target.graphId || target.resolvedTargetId,
      graph_name: target.graphName || target.displayName
    }
  }

  return {
    target_type: 'assistant',
    target_display_name: target.displayName,
    assistant_id: target.assistantId || target.resolvedTargetId,
    assistant_name: target.assistantName || target.displayName
  }
}

export function getMetadataCheckpointId(metadata?: { firstSeenState?: unknown }) {
  const firstSeenState =
    metadata?.firstSeenState && typeof metadata.firstSeenState === 'object'
      ? (metadata.firstSeenState as Record<string, unknown>)
      : null
  const checkpoint = firstSeenState?.checkpoint
  if (!checkpoint || typeof checkpoint !== 'object' || Array.isArray(checkpoint)) {
    return ''
  }

  const checkpointId = (checkpoint as { checkpoint_id?: unknown }).checkpoint_id
  return typeof checkpointId === 'string' ? checkpointId.trim() : ''
}

export function buildOptimisticMessage(content: string, attachments: ChatAttachmentBlock[]): Message {
  const normalizedContent = content.trim()
  const normalizedAttachments = attachments.filter((item) => item && typeof item === 'object')

  return {
    type: 'human',
    content:
      normalizedAttachments.length > 0
        ? ([...(normalizedContent ? [{ type: 'text', text: normalizedContent }] : []), ...normalizedAttachments] as Message['content'])
        : normalizedContent
  }
}

export function toOptimisticBaseMessage(content: Message['content']): Message {
  return {
    type: 'human',
    content
  }
}
