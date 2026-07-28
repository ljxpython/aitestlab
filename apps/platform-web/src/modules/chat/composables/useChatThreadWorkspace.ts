import { computed, ref, type ComputedRef, type Ref } from 'vue'
import {
  buildRuntimeSnapshotWarning,
  deleteRuntimeThread,
  getRuntimeThreadSnapshot,
  listRuntimeThreadsPage,
  normalizeRuntimeGatewayError,
  type RuntimeGatewayErrorMeta,
  type RuntimeThreadSnapshot
} from '@/services/runtime-gateway/workspace.service'
import type { ManagementThread } from '@/types/management'
import {
  formatThreadTime,
  getThreadListTitle,
  getThreadPreviewText,
  getThreadStateValues
} from '@/utils/threads'
import type { ChatResolvedTarget } from '../types'

type UseChatThreadWorkspaceOptions = {
  projectId: ComputedRef<string>
  target: ComputedRef<ChatResolvedTarget | null>
  activeThreadId: Ref<string>
  activeThread: Ref<ManagementThread | null>
  selectedBranch: Ref<string>
  historyItems: Ref<Record<string, unknown>[]>
  displayState: ComputedRef<Record<string, unknown> | null>
  clearStreamDetailFeedback: (options?: { preserveInfo?: boolean }) => void
  resetStreamView: (options?: { preserveInfo?: boolean }) => void
  streamDetailError: Ref<string>
  streamDetailInfo: Ref<string>
}

type SyncActiveThreadResult = {
  degraded: boolean
  excluded: boolean
}

function normalizeHistoryEntry(entry: Record<string, unknown>) {
  const normalizedValues = getThreadStateValues(entry)
  return {
    ...entry,
    values: normalizedValues
  }
}

function resolveLegacyBrokenThreadNotice(snapshot: RuntimeThreadSnapshot): string {
  if (snapshot.stateError?.kind !== 'bad_request') {
    return ''
  }

  return '该历史线程的状态快照已经损坏，系统已将它隔离为旧线程。建议新开对话继续，避免再次被旧坏线程干扰。'
}

function isLegacyDebugThread(thread: ManagementThread) {
  return thread.metadata?.session_kind === 'legacy_debug'
}

export function useChatThreadWorkspace(options: UseChatThreadWorkspaceOptions) {
  const threadItems = ref<ManagementThread[]>([])
  const loadingThreads = ref(false)
  const loadingThreadDetail = ref(false)
  const error = ref('')
  const detailWarning = ref('')
  const threadErrorMeta = ref<RuntimeGatewayErrorMeta | null>(null)
  const detailErrorMeta = ref<RuntimeGatewayErrorMeta | null>(null)
  const degradedThreadHints = ref<Record<string, string>>({})

  let threadListToken = 0
  let detailToken = 0
  let preserveBranchOnThreadSync = false

  function invalidatePendingThreadLoads() {
    threadListToken += 1
    detailToken += 1
    loadingThreads.value = false
    loadingThreadDetail.value = false
  }

  function getThreadSortTimestamp(item: ManagementThread) {
    const rawTimestamp = item.updated_at || item.created_at || ''
    const parsedTimestamp = Date.parse(rawTimestamp)
    return Number.isNaN(parsedTimestamp) ? 0 : parsedTimestamp
  }

  function upsertThreadSummary(nextThread: ManagementThread) {
    const remainingThreads = threadItems.value.filter((item) => item.thread_id !== nextThread.thread_id)
    threadItems.value = [nextThread, ...remainingThreads].sort(
      (left, right) => getThreadSortTimestamp(right) - getThreadSortTimestamp(left)
    )
  }

  const threadSummary = computed(() =>
    threadItems.value.map((item) => ({
      id: item.thread_id,
      title: getThreadListTitle(item),
      preview: degradedThreadHints.value[item.thread_id] || getThreadPreviewText(item),
      updatedAt: item.updated_at || item.created_at || '',
      time: formatThreadTime(item.updated_at || item.created_at),
      status: item.status || 'idle'
    }))
  )

  const selectedThreadSummary = computed(
    () => threadSummary.value.find((item) => item.id === options.activeThreadId.value) || null
  )

  function clearDetailFeedback(controlOptions: { preserveInfo?: boolean } = {}) {
    detailWarning.value = ''
    detailErrorMeta.value = null
    options.clearStreamDetailFeedback(controlOptions)
  }

  function resetActiveThreadState(controlOptions: { preserveInfo?: boolean } = {}) {
    options.activeThreadId.value = ''
    options.activeThread.value = null
    options.historyItems.value = []
    options.selectedBranch.value = ''
    options.resetStreamView(controlOptions)
    clearDetailFeedback(controlOptions)
  }

  function clearActiveThreadState(controlOptions: { preserveInfo?: boolean } = {}) {
    invalidatePendingThreadLoads()
    resetActiveThreadState(controlOptions)
  }

  function resetForContextChange(initialThreadId = '') {
    invalidatePendingThreadLoads()
    options.activeThreadId.value = initialThreadId.trim()
    options.activeThread.value = null
    options.historyItems.value = []
    options.selectedBranch.value = ''
    degradedThreadHints.value = {}
    error.value = ''
    detailWarning.value = ''
    threadErrorMeta.value = null
    detailErrorMeta.value = null
    options.resetStreamView()
  }

  function syncActiveThreadFromHistory(threadId: string) {
    const normalizedThreadId = threadId.trim()
    if (!normalizedThreadId) {
      return
    }

    const current = threadItems.value.find((item) => item.thread_id === normalizedThreadId)
    if (current) {
      options.activeThread.value = {
        ...current,
        values: options.displayState.value || current.values
      }
      return
    }

    if (options.activeThread.value?.thread_id === normalizedThreadId) {
      options.activeThread.value = {
        ...options.activeThread.value,
        values: options.displayState.value || options.activeThread.value.values
      }
    }
  }

  async function syncActiveThreadFromList(
    threadId: string,
    loadOptions: { preserveInfo?: boolean } = {}
  ): Promise<SyncActiveThreadResult> {
    const projectId = options.projectId.value.trim()
    const normalizedThreadId = threadId.trim()

    if (!projectId || !normalizedThreadId) {
      return { degraded: false, excluded: false }
    }

    const currentToken = ++detailToken
    loadingThreadDetail.value = true
    clearDetailFeedback({ preserveInfo: loadOptions.preserveInfo })

    try {
      const fallbackSummary = threadItems.value.find((item) => item.thread_id === normalizedThreadId) || null
      const snapshot = await getRuntimeThreadSnapshot(projectId, normalizedThreadId, {
        summary: fallbackSummary,
        historyLimit: 20
      })

      if (currentToken !== detailToken) {
        return { degraded: false, excluded: false }
      }

      if (isLegacyDebugThread(snapshot.detail)) {
        threadItems.value = threadItems.value.filter(
          (item) => item.thread_id !== normalizedThreadId
        )
        if (options.activeThreadId.value === normalizedThreadId) {
          resetActiveThreadState()
        }
        return { degraded: false, excluded: true }
      }

      const degradedNotice = resolveLegacyBrokenThreadNotice(snapshot)
      if (degradedNotice) {
        degradedThreadHints.value = {
          ...degradedThreadHints.value,
          [normalizedThreadId]: degradedNotice
        }
      } else if (degradedThreadHints.value[normalizedThreadId]) {
        const nextHints = { ...degradedThreadHints.value }
        delete nextHints[normalizedThreadId]
        degradedThreadHints.value = nextHints
      }

      const liveValues =
        options.activeThreadId.value === normalizedThreadId ? options.displayState.value : null
      upsertThreadSummary(snapshot.detail)
      options.activeThreadId.value = normalizedThreadId
      options.activeThread.value = {
        ...snapshot.detail,
        values: liveValues || snapshot.detail.values
      }
      options.historyItems.value = Array.isArray(snapshot.history)
        ? snapshot.history.map((entry) => normalizeHistoryEntry(entry as Record<string, unknown>))
        : []
      detailWarning.value = degradedNotice || buildRuntimeSnapshotWarning(snapshot)

      if (!preserveBranchOnThreadSync) {
        options.selectedBranch.value = ''
      }

      return { degraded: Boolean(degradedNotice), excluded: false }
    } catch (loadError) {
      if (currentToken !== detailToken) {
        return { degraded: false, excluded: false }
      }

      const normalizedError = normalizeRuntimeGatewayError(loadError, '线程详情加载失败')
      clearActiveThreadState({ preserveInfo: true })
      options.streamDetailError.value = normalizedError.message
      detailErrorMeta.value = normalizedError
      return { degraded: false, excluded: false }
    } finally {
      preserveBranchOnThreadSync = false
      if (currentToken === detailToken) {
        loadingThreadDetail.value = false
      }
    }
  }

  async function loadThreadList(preferredThreadId = '') {
    const projectId = options.projectId.value.trim()
    const target = options.target.value

    if (!projectId || !target) {
      threadItems.value = []
      clearActiveThreadState()
      error.value = ''
      threadErrorMeta.value = null
      loadingThreads.value = false
      return
    }

    const currentToken = ++threadListToken
    loadingThreads.value = true
    error.value = ''
    threadErrorMeta.value = null

    try {
      const payload = await listRuntimeThreadsPage(projectId, {
        limit: 100,
        offset: 0,
        assistantId: target.targetType === 'assistant' ? target.assistantId : undefined,
        graphId: target.targetType === 'graph' ? target.graphId || target.resolvedTargetId : undefined
      })

      if (currentToken !== threadListToken) {
        return
      }

      threadItems.value = Array.isArray(payload.items)
        ? payload.items.filter((item) => !isLegacyDebugThread(item))
        : []

      const requestedThreadId = preferredThreadId.trim() || options.activeThreadId.value.trim()
      const explicitPreferredThreadId = threadItems.value.some(
        (item) => item.thread_id === requestedThreadId
      )
        ? requestedThreadId
        : ''
      const candidateThreadIds = Array.from(
        new Set(
          [explicitPreferredThreadId, ...threadItems.value.map((item) => item.thread_id)]
            .map((item) => item.trim())
            .filter(Boolean)
        )
      )

      if (candidateThreadIds.length === 0) {
        clearActiveThreadState()
        return
      }

      if (explicitPreferredThreadId) {
        const result = await syncActiveThreadFromList(explicitPreferredThreadId)
        if (!result.excluded) {
          return
        }
      }

      const skippedBrokenThreadIds: string[] = []
      for (const candidateThreadId of candidateThreadIds) {
        if (candidateThreadId === explicitPreferredThreadId) {
          continue
        }

        const result = await syncActiveThreadFromList(candidateThreadId, {
          preserveInfo: skippedBrokenThreadIds.length > 0
        })
        if (result.excluded) {
          continue
        }
        if (!result.degraded) {
          if (skippedBrokenThreadIds.length > 0) {
            options.streamDetailInfo.value = `检测到 ${skippedBrokenThreadIds.length} 个旧坏线程，已自动切到最近可用会话。`
          }
          return
        }

        skippedBrokenThreadIds.push(candidateThreadId)
      }

      if (skippedBrokenThreadIds.length > 0) {
        options.streamDetailInfo.value = '当前可见会话都存在历史状态损坏，建议直接新建对话继续。'
      }
    } catch (loadError) {
      if (currentToken !== threadListToken) {
        return
      }

      const normalizedError = normalizeRuntimeGatewayError(loadError, '线程列表加载失败')
      threadItems.value = []
      clearActiveThreadState()
      error.value = normalizedError.message
      threadErrorMeta.value = normalizedError
    } finally {
      if (currentToken === threadListToken) {
        loadingThreads.value = false
      }
    }
  }

  async function startNewThread() {
    if (!options.projectId.value.trim() || !options.target.value) {
      return false
    }

    invalidatePendingThreadLoads()
    error.value = ''
    options.activeThreadId.value = ''
    options.activeThread.value = null
    options.historyItems.value = []
    options.selectedBranch.value = ''
    options.resetStreamView()
    clearDetailFeedback()
    options.streamDetailInfo.value = '已切换到空白对话。发送第一条消息时，系统才会创建新的 thread。'
    return true
  }

  async function selectThread(threadId: string) {
    const normalizedThreadId = threadId.trim()
    if (!normalizedThreadId || normalizedThreadId === options.activeThreadId.value) {
      return
    }

    invalidatePendingThreadLoads()
    await syncActiveThreadFromList(normalizedThreadId)
  }

  async function refreshActiveThread() {
    if (options.activeThreadId.value.trim()) {
      await syncActiveThreadFromList(options.activeThreadId.value)
      return
    }
    await loadThreadList()
  }

  async function deleteThreadById(threadId: string) {
    const projectId = options.projectId.value.trim()
    const normalizedThreadId = threadId.trim()

    if (!projectId || !normalizedThreadId) {
      throw new Error('缺少可删除的线程上下文')
    }

    await deleteRuntimeThread(projectId, normalizedThreadId)

    const remaining = threadItems.value.filter((item) => item.thread_id !== normalizedThreadId)
    threadItems.value = remaining
    if (degradedThreadHints.value[normalizedThreadId]) {
      const nextHints = { ...degradedThreadHints.value }
      delete nextHints[normalizedThreadId]
      degradedThreadHints.value = nextHints
    }

    if (options.activeThreadId.value === normalizedThreadId) {
      const nextThreadId = remaining[0]?.thread_id || ''
      if (!nextThreadId) {
        clearActiveThreadState()
        return true
      }

      await syncActiveThreadFromList(nextThreadId)
    }

    return true
  }

  function stageSelectedBranch(branch: string) {
    options.selectedBranch.value = branch.trim()
    preserveBranchOnThreadSync = true
  }

  return {
    clearActiveThreadState,
    clearDetailFeedback,
    deleteThread: deleteThreadById,
    degradedThreadHints,
    detailErrorMeta,
    detailWarning,
    error,
    loadThreadList,
    loadingThreadDetail,
    loadingThreads,
    refreshActiveThread,
    resetForContextChange,
    selectThread,
    selectedThreadSummary,
    stageSelectedBranch,
    startNewThread,
    syncActiveThreadFromHistory,
    syncActiveThreadFromList,
    threadErrorMeta,
    threadItems,
    threadSummary
  }
}
