import type { Message } from '@langchain/langgraph-sdk'
import type {
  ManagementThread,
  RuntimeModelItem,
  RuntimeToolItem,
  ThreadHistoryEntry
} from '@/types/management'
import type { ChatTargetPreference } from '@/utils/chatTarget'

export type ChatResolvedTarget = ChatTargetPreference & {
  resolvedTargetId: string
  displayName: string
  label: string
}

export type ChatWorkspaceDisplay = {
  title: string
  description: string
  emptyTitle?: string
  emptyDescription?: string
}

export type ChatWorkspaceFeatures = {
  allowRunOptions?: boolean
  showHistory?: boolean
  showArtifacts?: boolean
  showContextBar?: boolean
}

export type ChatRunOptions = {
  modelId: string
  systemPrompt: string
  enableTools: boolean
  toolNames: string[]
  temperature: string
  maxTokens: string
}

export type ChatWorkspaceThread = ManagementThread
export type ChatWorkspaceHistoryEntry = ThreadHistoryEntry
export type ChatWorkspaceMessage = Message

export type ChatRuntimeCatalog = {
  models: RuntimeModelItem[]
  tools: RuntimeToolItem[]
}

export function resolveChatTarget(target?: ChatTargetPreference | null): ChatResolvedTarget | null {
  if (!target) {
    return null
  }

  if (target.targetType === 'graph') {
    const graphId = target.graphId?.trim() || target.assistantId?.trim() || ''
    if (!graphId) {
      return null
    }

    const displayName = target.graphName?.trim() || graphId

    return {
      targetType: 'graph',
      graphId,
      graphName: target.graphName,
      updatedAt: target.updatedAt,
      resolvedTargetId: graphId,
      displayName,
      label: `Graph · ${displayName}`
    }
  }

  const assistantId = target.assistantId?.trim() || ''
  if (!assistantId) {
    return null
  }

  const displayName = target.assistantName?.trim() || assistantId

  return {
    targetType: 'assistant',
    assistantId,
    assistantName: target.assistantName,
    updatedAt: target.updatedAt,
    resolvedTargetId: assistantId,
    displayName,
    label: `Agent · ${displayName}`
  }
}
