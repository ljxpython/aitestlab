export type ChatTargetType = 'assistant' | 'graph'

export type ChatTargetPreference = {
  targetType: ChatTargetType
  assistantId?: string
  assistantName?: string
  graphId?: string
  graphName?: string
  updatedAt: string
}

type ChatTargetInput = {
  targetType?: string | null
  assistantId?: string | null
  assistantName?: string | null
  graphId?: string | null
  graphName?: string | null
  updatedAt?: string | null
}

const STORAGE_KEY_PREFIX = 'platform-web:chat-target:'

function getStorageKey(projectId: string) {
  return `${STORAGE_KEY_PREFIX}${projectId}`
}

function normalizeTargetName(value?: string | null) {
  const normalized = value?.trim() || ''
  return normalized || undefined
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function readMetadataText(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  return typeof value === 'string' ? value.trim() : ''
}

export function normalizeChatTarget(input?: ChatTargetInput | null): ChatTargetPreference | null {
  if (!input) {
    return null
  }

  const targetType = input.targetType === 'graph' ? 'graph' : 'assistant'
  const assistantId = input.assistantId?.trim() || ''
  const assistantName = normalizeTargetName(input.assistantName)
  const graphId = input.graphId?.trim() || ''
  const graphName = normalizeTargetName(input.graphName)
  const updatedAt = input.updatedAt?.trim() || new Date().toISOString()

  if (targetType === 'graph') {
    const resolvedGraphId = graphId || assistantId
    if (!resolvedGraphId) {
      return null
    }

    return {
      targetType,
      graphId: resolvedGraphId,
      graphName,
      updatedAt
    }
  }

  if (!assistantId) {
    return null
  }

  return {
    targetType,
    assistantId,
    assistantName,
    updatedAt
  }
}

export function normalizeChatTargetFromThreadMetadata(
  metadata: unknown,
  updatedAt?: string | null
): ChatTargetPreference | null {
  const record = asRecord(metadata)
  if (!record) {
    return null
  }

  const targetType = readMetadataText(record, 'target_type').toLowerCase()
  const assistantId = readMetadataText(record, 'assistant_id')
  const assistantName = readMetadataText(record, 'assistant_name')
  const graphId = readMetadataText(record, 'graph_id')
  const graphName = readMetadataText(record, 'graph_name')
  const targetDisplayName = readMetadataText(record, 'target_display_name')

  if (targetType === 'graph' || graphId) {
    return normalizeChatTarget({
      targetType: 'graph',
      graphId: graphId || assistantId,
      graphName: graphName || targetDisplayName,
      updatedAt
    })
  }

  if (targetType === 'assistant' || assistantId) {
    return normalizeChatTarget({
      targetType: 'assistant',
      assistantId,
      assistantName: assistantName || targetDisplayName,
      updatedAt
    })
  }

  return null
}

function resolveComparableTargetId(target: ChatTargetPreference) {
  if (target.targetType === 'graph') {
    return target.graphId?.trim() || target.assistantId?.trim() || ''
  }

  return target.assistantId?.trim() || ''
}

export function hasChatTargetDisplayName(target?: ChatTargetPreference | null) {
  if (!target) {
    return false
  }

  if (target.targetType === 'graph') {
    return Boolean(target.graphName?.trim())
  }

  return Boolean(target.assistantName?.trim())
}

export function mergeChatTargets(
  preferred?: ChatTargetInput | null,
  fallback?: ChatTargetInput | null
): ChatTargetPreference | null {
  const normalizedPreferred = normalizeChatTarget(preferred)
  const normalizedFallback = normalizeChatTarget(fallback)

  if (!normalizedPreferred) {
    return normalizedFallback
  }

  if (!normalizedFallback) {
    return normalizedPreferred
  }

  if (
    normalizedPreferred.targetType !== normalizedFallback.targetType ||
    resolveComparableTargetId(normalizedPreferred) !== resolveComparableTargetId(normalizedFallback)
  ) {
    return normalizedPreferred
  }

  if (normalizedPreferred.targetType === 'graph') {
    return {
      ...normalizedFallback,
      ...normalizedPreferred,
      graphName: normalizedPreferred.graphName || normalizedFallback.graphName
    }
  }

  return {
    ...normalizedFallback,
    ...normalizedPreferred,
    assistantName: normalizedPreferred.assistantName || normalizedFallback.assistantName
  }
}

export function writeRecentChatTarget(projectId: string, input: ChatTargetInput) {
  if (!projectId.trim() || typeof window === 'undefined') {
    return
  }

  const target = normalizeChatTarget(input)
  if (!target) {
    return
  }

  window.localStorage.setItem(getStorageKey(projectId), JSON.stringify(target))
}

export function readRecentChatTarget(projectId: string): ChatTargetPreference | null {
  if (!projectId.trim() || typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(getStorageKey(projectId))
  if (!raw) {
    return null
  }

  try {
    return normalizeChatTarget(JSON.parse(raw) as ChatTargetInput)
  } catch {
    window.localStorage.removeItem(getStorageKey(projectId))
    return null
  }
}

export function clearRecentChatTarget(projectId: string) {
  if (!projectId.trim() || typeof window === 'undefined') {
    return
  }
  window.localStorage.removeItem(getStorageKey(projectId))
}
