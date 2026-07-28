import type { Message } from '@langchain/langgraph-sdk'
import type { AssembledToolCall } from '@langchain/vue'
import { getMessageText } from '@/utils/chat-content'
import { toPrettyJson } from '@/utils/threads'
import { extractToolCallsFromMessage } from './tool-call-utils'
import { buildChatToolResultView, type ChatToolResultRenderMode } from './tool-result-renderers'

type ToolCallResultMap = Record<string, Message>

export type ChatToolCallArgEntry = {
  key: string
  valueText: string
}

export type ChatToolCallCard = {
  key: string
  name: string
  idLabel: string
  status: 'pending' | 'completed' | 'error'
  argsEntries: ChatToolCallArgEntry[]
  resultText?: string
  resultRenderMode: ChatToolResultRenderMode
  resultImageUrl?: string
  errorText?: string
}

export type ChatSubAgentCard = {
  id: string
  name: string
  status: 'pending' | 'completed' | 'error'
  input: string
  output?: string
}

function getAssembledToolResult(toolCall: AssembledToolCall | undefined): Message | undefined {
  if (!toolCall || toolCall.status !== 'finished' || toolCall.output == null) {
    return undefined
  }

  return {
    type: 'tool',
    tool_call_id: toolCall.callId,
    content:
      typeof toolCall.output === 'string'
        ? toolCall.output
        : toPrettyJson(toolCall.output)
  } as Message
}

function normalizeToolArgs(args: unknown): Record<string, unknown> {
  if (args && typeof args === 'object' && !Array.isArray(args)) {
    return args as Record<string, unknown>
  }

  if (typeof args === 'string') {
    try {
      const parsed = JSON.parse(args)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      // ignore parse failure
    }

    return {
      input: args
    }
  }

  return {}
}

function toArgEntries(args: unknown): ChatToolCallArgEntry[] {
  return Object.entries(normalizeToolArgs(args)).map(([key, value]) => ({
    key,
    valueText: typeof value === 'string' ? value : toPrettyJson(value)
  }))
}

function normalizeToolCallInput(args: unknown): string {
  if (args == null) {
    return ''
  }
  if (typeof args === 'string') {
    return args
  }
  if (typeof args === 'object') {
    const record = args as Record<string, unknown>
    const task =
      typeof record.task === 'string'
        ? record.task
        : typeof record.description === 'string'
          ? record.description
          : ''
    if (task.trim()) {
      return task
    }
    return toPrettyJson(record)
  }
  return String(args)
}

function getSubAgentName(args: unknown): string {
  if (!args || typeof args !== 'object') {
    return 'sub-agent'
  }

  const record = args as Record<string, unknown>
  return typeof record.subagent_type === 'string' && record.subagent_type.trim()
    ? record.subagent_type.trim()
    : 'sub-agent'
}

export function buildToolResultsByCallId(messages: Message[]): ToolCallResultMap {
  return messages.reduce<ToolCallResultMap>((result, item) => {
    if (item.type === 'tool' && typeof item.tool_call_id === 'string' && item.tool_call_id.trim()) {
      result[item.tool_call_id] = item
    }
    return result
  }, {})
}

export function buildChatMessageMetaView(
  message: Message,
  allMessages: Message[],
  assembledToolCalls: AssembledToolCall[] = []
) {
  const assembledByCallId = new Map(assembledToolCalls.map((item) => [item.callId, item]))
  let legacyToolResultsByCallId: ToolCallResultMap | undefined

  if (message.type !== 'ai') {
    return {
      toolCalls: [] as ChatToolCallCard[],
      subAgentCards: [] as ChatSubAgentCard[]
    }
  }

  const toolCalls: ChatToolCallCard[] = []
  const subAgentCards: ChatSubAgentCard[] = []

  extractToolCallsFromMessage(message).forEach((toolCall, index) => {
    const toolCallId = toolCall.id
    const toolName = toolCall.name
    const assembledToolCall = toolCallId ? assembledByCallId.get(toolCallId) : undefined
    if (!assembledToolCall && legacyToolResultsByCallId === undefined) {
      legacyToolResultsByCallId = buildToolResultsByCallId(allMessages)
    }
    const toolResult = getAssembledToolResult(assembledToolCall) ||
      (toolCallId ? legacyToolResultsByCallId?.[toolCallId] : undefined)
    const resultView = buildChatToolResultView(toolName, toolResult)
    const status = assembledToolCall
      ? assembledToolCall.status === 'running'
        ? 'pending'
        : assembledToolCall.status === 'error'
          ? 'error'
          : 'completed'
      : toolResult
        ? 'completed'
        : 'pending'

    if (toolName === 'task') {
      const output = toolResult ? getMessageText(toolResult.content) : assembledToolCall?.error || ''
      subAgentCards.push({
        id: toolCallId || `task-${message.id || 'message'}-${index + 1}`,
        name: getSubAgentName(toolCall.args),
        status,
        input: normalizeToolCallInput(toolCall.args),
        output: output || undefined
      })
      return
    }

    toolCalls.push({
      key: toolCallId || `${toolName || 'tool'}-${index + 1}`,
      name: toolName || 'Unknown Tool',
      idLabel: toolCallId || `tool-${index + 1}`,
      status,
      argsEntries: toArgEntries(toolCall.args),
      resultText: resultView.text,
      resultRenderMode: resultView.mode,
      resultImageUrl: resultView.imageUrl,
      errorText: assembledToolCall?.error
    })
  })

  return {
    toolCalls,
    subAgentCards
  }
}
