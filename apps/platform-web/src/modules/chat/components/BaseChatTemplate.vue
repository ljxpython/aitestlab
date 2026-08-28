<script setup lang="ts">
import type { Message } from '@langchain/langgraph-sdk'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import type { LocationQueryRaw } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import { useUiStore } from '@/stores/ui'
import { copyText } from '@/utils/clipboard'
import { shortId } from '@/utils/format'
import { getMessageText } from '@/utils/threads'
import ChatArtifactPanel from './ChatArtifactPanel.vue'
import ChatComposer from './ChatComposer.vue'
import ChatContextDrawer from './ChatContextDrawer.vue'
import ChatInterruptPanel from './ChatInterruptPanel.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatRunOptionsDialog from './ChatRunOptionsDialog.vue'
import ChatThreadDrawer from './ChatThreadDrawer.vue'
import { buildChatCompactModeView } from '../compact-mode-view-model'
import { normalizeChatInspectorFiles } from '../inspector-view-model'
import { buildChatLiveFollowView } from '../live-follow-view-model'
import { createChatMessageActions } from '../message-actions'
import { buildChatDisplayMessages } from '../message-view-model'
import { buildChatPlanView } from '../plan-view-model'
import { isChatViewportNearBottom } from '../scroll-state'
import { buildChatThreadListView, type ChatThreadStatusFilter } from '../thread-list-view-model'
import { useChatAttachments } from '../composables/useChatAttachments'
import { useChatWorkspace } from '../composables/useChatWorkspace'
import type { ChatResolvedTarget, ChatWorkspaceDisplay, ChatWorkspaceFeatures } from '../types'

type InspectorTabKey = 'overview' | 'tasks' | 'files' | 'history'
type FollowPauseReason = 'manualScroll' | 'contextDrawer' | 'runtimeOptions' | 'messageMeta'
const CHAT_DRAFT_STORAGE_PREFIX = 'pw:chat:draft'

const props = withDefaults(
  defineProps<{
    target: ChatResolvedTarget | null
    display: ChatWorkspaceDisplay
    features?: ChatWorkspaceFeatures
    initialThreadId?: string
    sourceNote?: string
    contextNotice?: string
    allowResetTarget?: boolean
  }>(),
  {
    features: () => ({}),
    initialThreadId: '',
    sourceNote: '',
    contextNotice: '',
    allowResetTarget: false
  }
)

const emit = defineEmits<{
  'reset-target': []
  'compact-mode-change': [value: boolean]
}>()

const route = useRoute()
const router = useRouter()
const uiStore = useUiStore()
const { activeProjectId, activeProject } = useWorkspaceProjectContext()

const composerInput = ref('')
const threadSearch = ref('')
const threadStatusFilter = ref<ChatThreadStatusFilter>('all')
const threadsDrawerOpen = ref(false)
const contextDrawerOpen = ref(false)
const runtimeOptionsDialogOpen = ref(false)
const inspectorInitialTab = ref<InspectorTabKey>('overview')
const messagesViewport = ref<HTMLDivElement | null>(null)
const messagesContent = ref<HTMLDivElement | null>(null)
const isFocusMode = ref(false)
const workspaceHeaderCollapsed = ref(false)
const runtimeInfoDismissed = ref(false)
const deletingThreadId = ref('')
const editingMessageId = ref('')
const editingMessageValue = ref('')
const autoFollowEnabled = ref(true)
const unreadMessageCount = ref(0)
const bufferedStreamActivity = ref(false)
const expandedMessageMetaIds = ref<string[]>([])
const followPauseState = reactive<Record<FollowPauseReason, boolean>>({
  manualScroll: false,
  contextDrawer: false,
  runtimeOptions: false,
  messageMeta: false
})
const draftRunOptions = reactive({
  modelId: '',
  systemPrompt: '',
  enableTools: false,
  toolNames: [] as string[],
  temperature: '',
  maxTokens: ''
})

const workspace = useChatWorkspace({
  projectId: computed(() => activeProjectId.value || ''),
  target: computed(() => props.target),
  initialThreadId: computed(() => props.initialThreadId?.trim() || '')
})
const attachmentState = useChatAttachments()

const currentProject = activeProject
const renderMessages = computed(() => workspace.messages.value)
const displayMessages = computed(() =>
  buildChatDisplayMessages(renderMessages.value, workspace.lastEventAt.value)
)
const composerAttachments = computed(() => attachmentState.attachments.value)
const planView = computed(() => buildChatPlanView(workspace.displayState.value))
const inspectorFiles = computed(() => normalizeChatInspectorFiles(workspace.displayState.value))
const allowRunOptions = computed(() => props.features?.allowRunOptions ?? true)
const showHistory = computed(() => props.features?.showHistory ?? true)
const showArtifacts = computed(() => props.features?.showArtifacts ?? true)
const showContextBar = computed(() => props.features?.showContextBar ?? true)
const hasArtifactEntries = computed(() => {
  const rawEntries = workspace.displayState.value?.ui
  return Array.isArray(rawEntries) && rawEntries.length > 0
})
const hasComposerContent = computed(
  () => Boolean(composerInput.value.trim()) || composerAttachments.value.length > 0
)
const hasBlockingInterrupt = computed(
  () => workspace.interruptPayload.value !== undefined
)

function isGenericInternalRuntimeError(message: string) {
  return /^an internal error occurred$/i.test(message.trim())
}

const activeRunFailureDescription = computed(() => {
  const threadFailure = workspace.threadFailureMessage.value.trim()
  if (workspace.detailError.value.trim()) {
    const detailError = workspace.detailError.value.trim()
    return threadFailure && isGenericInternalRuntimeError(detailError) ? threadFailure : detailError
  }

  return threadFailure
})
const canSendFreshMessage = computed(
  () =>
    workspace.canSend.value &&
    !hasBlockingInterrupt.value &&
    hasComposerContent.value
)
const isInspectingMessageMeta = computed(() => expandedMessageMetaIds.value.length > 0)
const selectedToolsLabel = computed(() => {
  if (!draftRunOptions.enableTools) {
    return '已关闭'
  }
  if (draftRunOptions.toolNames.length === 0) {
    return '全部按默认策略'
  }
  return `${draftRunOptions.toolNames.length} 个工具`
})
const liveFollowView = computed(() =>
  buildChatLiveFollowView({
    autoFollowEnabled: autoFollowEnabled.value,
    isRunning: workspace.sending.value,
    unreadMessageCount: unreadMessageCount.value,
    bufferedStreamActivity: bufferedStreamActivity.value
  })
)
const liveFollowPillClass = computed(() => {
  if (liveFollowView.value.tone === 'success') {
    return 'pw-pill-soft-success'
  }

  if (liveFollowView.value.tone === 'warning') {
    return 'pw-pill-soft-warning'
  }

  return 'pw-pill-soft-info'
})
const compactModeView = computed(() =>
  buildChatCompactModeView({
    activeThreadId: workspace.activeThreadId.value,
    messageCount: renderMessages.value.length,
    isRunning: workspace.sending.value,
    loadingThreadDetail: workspace.loadingThreadDetail.value
  })
)
const isCompactMode = computed(() => compactModeView.value.enabled)
const isSurfaceCompact = computed(() => isCompactMode.value || isFocusMode.value)
const showJumpToLatestNotice = computed(
  () =>
    !contextDrawerOpen.value &&
    !runtimeOptionsDialogOpen.value &&
    liveFollowView.value.noticeVisible
)
const jumpToLatestTitle = computed(() => liveFollowView.value.title)
const jumpToLatestDescription = computed(() => {
  if (isInspectingMessageMeta.value) {
    return '你正在查看工具或子任务详情，点击可回到底部继续跟随。'
  }

  return liveFollowView.value.description
})

const headerPills = computed(() => [
  {
    label: 'Target',
    value: workspace.targetText.value
  },
  {
    label: 'Thread',
    value: workspace.activeThreadId.value ? shortId(workspace.activeThreadId.value) : '未创建'
  }
])

const threadStatusFilters = [
  { value: 'all', label: '全部' },
  { value: 'interrupted', label: '待处理' },
  { value: 'busy', label: '运行中' },
  { value: 'idle', label: '空闲' },
  { value: 'error', label: '异常' }
] as const
const threadListView = computed(() =>
  buildChatThreadListView({
    items: workspace.threadSummary.value,
    query: threadSearch.value,
    statusFilter: threadStatusFilter.value
  })
)
const filteredThreadSummary = computed(() => threadListView.value.filteredItems)
const groupedThreadSummary = computed(() => threadListView.value.groups)
const composerDraftKey = computed(() => {
  const projectId = activeProjectId.value.trim()
  const targetId = props.target?.resolvedTargetId?.trim() || 'no-target'
  const threadId = workspace.activeThreadId.value.trim() || '__new__'

  if (!projectId) {
    return ''
  }

  return `${CHAT_DRAFT_STORAGE_PREFIX}:${projectId}:${targetId}:${threadId}`
})

function readComposerDraft(storageKey: string) {
  if (typeof window === 'undefined' || !storageKey) {
    return ''
  }

  return window.localStorage.getItem(storageKey) || ''
}

function writeComposerDraft(storageKey: string, value: string) {
  if (typeof window === 'undefined' || !storageKey) {
    return
  }

  if (value.trim()) {
    window.localStorage.setItem(storageKey, value)
    return
  }

  window.localStorage.removeItem(storageKey)
}

function resetBufferedActivity() {
  unreadMessageCount.value = 0
  bufferedStreamActivity.value = false
}

let scheduledScrollBehavior: globalThis.ScrollBehavior = 'auto'
let scheduledScrollFrameId: number | null = null
let keepPinnedFrameId: number | null = null

function mergeScheduledBehavior(nextBehavior: globalThis.ScrollBehavior) {
  if (scheduledScrollBehavior === 'smooth' || nextBehavior === 'smooth') {
    scheduledScrollBehavior = 'smooth'
    return
  }

  scheduledScrollBehavior = nextBehavior
}

async function scrollMessagesToLatest(behavior: globalThis.ScrollBehavior = 'auto') {
  await nextTick()

  const viewport = messagesViewport.value
  if (!viewport) {
    return
  }

  viewport.scrollTo({
    top: viewport.scrollHeight,
    behavior
  })
}

function scheduleScrollToLatest(behavior: globalThis.ScrollBehavior = 'auto') {
  mergeScheduledBehavior(behavior)

  if (scheduledScrollFrameId !== null) {
    return
  }

  if (typeof window === 'undefined' || typeof window.requestAnimationFrame !== 'function') {
    void scrollMessagesToLatest(scheduledScrollBehavior)
    scheduledScrollBehavior = 'auto'
    return
  }

  scheduledScrollFrameId = window.requestAnimationFrame(() => {
    const nextBehavior = scheduledScrollBehavior
    scheduledScrollBehavior = 'auto'
    scheduledScrollFrameId = null
    void scrollMessagesToLatest(nextBehavior)
  })
}

function stopKeepPinnedToBottomLoop() {
  if (keepPinnedFrameId === null || typeof window === 'undefined') {
    return
  }

  window.cancelAnimationFrame(keepPinnedFrameId)
  keepPinnedFrameId = null
}

function keepPinnedToBottomLoop() {
  if (
    typeof window === 'undefined' ||
    !workspace.sending.value ||
    !autoFollowEnabled.value
  ) {
    stopKeepPinnedToBottomLoop()
    return
  }

  const viewport = messagesViewport.value
  if (viewport) {
    viewport.scrollTo({
      top: viewport.scrollHeight,
      behavior: 'auto'
    })
  }

  keepPinnedFrameId = window.requestAnimationFrame(() => {
    keepPinnedToBottomLoop()
  })
}

function updateAutoFollowState(options?: {
  resumeBehavior?: globalThis.ScrollBehavior
  skipScroll?: boolean
}) {
  const nextEnabled = !Object.values(followPauseState).some(Boolean)
  autoFollowEnabled.value = nextEnabled

  if (!nextEnabled) {
    return
  }

  resetBufferedActivity()

  if (!options?.skipScroll) {
    scheduleScrollToLatest(options?.resumeBehavior ?? 'auto')
  }
}

function setFollowPauseReason(
  reason: FollowPauseReason,
  isPaused: boolean,
  options?: {
    resumeBehavior?: globalThis.ScrollBehavior
    skipScroll?: boolean
  }
) {
  if (followPauseState[reason] === isPaused) {
    return
  }

  followPauseState[reason] = isPaused
  updateAutoFollowState(options)
}

function clearExpandedMessageMeta() {
  if (expandedMessageMetaIds.value.length === 0) {
    return
  }

  expandedMessageMetaIds.value = []
  setFollowPauseReason('messageMeta', false, { resumeBehavior: 'smooth' })
}

function applyFocusModeDocumentState(enabled: boolean) {
  if (typeof document === 'undefined') {
    return
  }

  document.documentElement.classList.toggle('pw-dialog-open', enabled)
  document.body.classList.toggle('pw-dialog-open', enabled)
}

function toggleFocusMode(nextValue?: boolean) {
  const normalizedValue = typeof nextValue === 'boolean' ? nextValue : !isFocusMode.value
  isFocusMode.value = normalizedValue

  if (!normalizedValue) {
    return
  }

  threadsDrawerOpen.value = false
  contextDrawerOpen.value = false
  runtimeOptionsDialogOpen.value = false
}

function toggleWorkspaceHeaderCollapsed(nextValue?: boolean) {
  workspaceHeaderCollapsed.value =
    typeof nextValue === 'boolean' ? nextValue : !workspaceHeaderCollapsed.value
}

function handleFocusModeKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || !isFocusMode.value) {
    return
  }

  event.preventDefault()
  toggleFocusMode(false)
}

function resumeAutoFollow(behavior: globalThis.ScrollBehavior = 'auto') {
  setFollowPauseReason('manualScroll', false, { resumeBehavior: behavior })
  clearExpandedMessageMeta()
  updateAutoFollowState({ resumeBehavior: behavior })
}

function handleMessagesScroll() {
  const viewport = messagesViewport.value
  if (!viewport) {
    return
  }

  if (isChatViewportNearBottom(viewport)) {
    setFollowPauseReason('manualScroll', false, { skipScroll: true })
    if (autoFollowEnabled.value) {
      resetBufferedActivity()
    }
    return
  }

  if (!followPauseState.manualScroll) {
    setFollowPauseReason('manualScroll', true, { skipScroll: true })
  }
}

function handleMessagesContentResize() {
  if (autoFollowEnabled.value) {
    scheduleScrollToLatest('auto')
    return
  }

  if (workspace.sending.value) {
    bufferedStreamActivity.value = true
  }
}

function syncThreadIdToRoute(threadId: string) {
  const normalizedThreadId = threadId.trim()
  const currentRouteThreadId =
    typeof route.query.threadId === 'string' && route.query.threadId.trim() ? route.query.threadId.trim() : ''

  if (normalizedThreadId === currentRouteThreadId) {
    return
  }

  const nextQuery: LocationQueryRaw = { ...route.query }

  if (normalizedThreadId) {
    nextQuery.threadId = normalizedThreadId

    if (route.path === '/workspace/chat' && props.target) {
      nextQuery.targetType = props.target.targetType
      if (props.target.targetType === 'graph') {
        nextQuery.graphId = props.target.resolvedTargetId
        nextQuery.graphName = props.target.displayName
        delete nextQuery.assistantId
        delete nextQuery.assistantName
      } else {
        nextQuery.assistantId = props.target.resolvedTargetId
        nextQuery.assistantName = props.target.displayName
        delete nextQuery.graphId
        delete nextQuery.graphName
      }
    }
  } else {
    delete nextQuery.threadId
  }

  void router.replace({
    path: route.path,
    query: nextQuery
  })
}

watch(
  () => workspace.activeThreadId.value,
  (threadId) => {
    syncThreadIdToRoute(threadId || '')
  }
)

watch(
  () => isCompactMode.value,
  (nextValue) => {
    emit('compact-mode-change', nextValue)

    if (nextValue && autoFollowEnabled.value) {
      scheduleScrollToLatest('auto')
    }
  },
  { immediate: true }
)

watch(
  () => isFocusMode.value,
  (nextValue) => {
    applyFocusModeDocumentState(nextValue)
  },
  { immediate: true }
)

watch(
  () => props.target,
  (nextTarget) => {
    if (!nextTarget) {
      toggleFocusMode(false)
    }
  }
)

watch(
  () => workspace.detailInfo.value,
  (nextValue, previousValue) => {
    if (!nextValue.trim()) {
      runtimeInfoDismissed.value = false
      return
    }

    if (nextValue !== previousValue) {
      runtimeInfoDismissed.value = false
    }
  }
)

watch(
  () => composerDraftKey.value,
  (nextKey) => {
    composerInput.value = readComposerDraft(nextKey)
  },
  { immediate: true }
)

watch(
  () => composerInput.value,
  (nextValue) => {
    writeComposerDraft(composerDraftKey.value, nextValue)
  }
)

watch(
  () => displayMessages.value.length,
  (nextCount, previousCount) => {
    const delta = Math.max(0, nextCount - previousCount)
    if (delta === 0) {
      return
    }

    if (autoFollowEnabled.value) {
      scheduleScrollToLatest(previousCount === 0 ? 'auto' : 'smooth')
      return
    }

    unreadMessageCount.value += delta
  }
)

watch(
  () => workspace.lastEventAt.value,
  (nextValue, previousValue) => {
    if (!nextValue || nextValue === previousValue) {
      return
    }

    if (autoFollowEnabled.value) {
      scheduleScrollToLatest('auto')
      return
    }

    bufferedStreamActivity.value = true
  }
)

watch(
  () => workspace.activeThreadId.value,
  () => {
    messageActions.cancelEditMessage()
    deletingThreadId.value = ''
    expandedMessageMetaIds.value = []
    followPauseState.manualScroll = false
    followPauseState.contextDrawer = false
    followPauseState.runtimeOptions = false
    followPauseState.messageMeta = false
    resetBufferedActivity()
    updateAutoFollowState({ skipScroll: true })
    scheduleScrollToLatest('auto')
  }
)

watch(
  () => contextDrawerOpen.value,
  (isOpen) => {
    setFollowPauseReason('contextDrawer', isOpen, {
      resumeBehavior: 'smooth',
      skipScroll: isOpen
    })
  }
)

watch(
  () => runtimeOptionsDialogOpen.value,
  (isOpen) => {
    setFollowPauseReason('runtimeOptions', isOpen, {
      resumeBehavior: 'smooth',
      skipScroll: isOpen
    })
  }
)

watch(
  [() => workspace.sending.value, () => autoFollowEnabled.value],
  ([isSending, canFollow], _previous, onCleanup) => {
    stopKeepPinnedToBottomLoop()

    if (typeof window === 'undefined' || !isSending || !canFollow) {
      return
    }

    keepPinnedFrameId = window.requestAnimationFrame(() => {
      keepPinnedToBottomLoop()
    })

    onCleanup(() => {
      stopKeepPinnedToBottomLoop()
    })
  },
  { immediate: true }
)

watch(
  messagesContent,
  (element, _previous, onCleanup) => {
    if (!element || typeof ResizeObserver === 'undefined') {
      return
    }

    const observer = new ResizeObserver(() => {
      handleMessagesContentResize()
    })
    observer.observe(element)

    onCleanup(() => {
      observer.disconnect()
    })
  },
  {
    flush: 'post'
  }
)

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleFocusModeKeydown)
  }

  applyFocusModeDocumentState(false)

  if (scheduledScrollFrameId === null || typeof window === 'undefined') {
    stopKeepPinnedToBottomLoop()
    return
  }

  window.cancelAnimationFrame(scheduledScrollFrameId)
  scheduledScrollFrameId = null
  stopKeepPinnedToBottomLoop()
})

onMounted(() => {
  if (typeof window === 'undefined') {
    return
  }

  window.addEventListener('keydown', handleFocusModeKeydown)
})

const messageActions = createChatMessageActions({
  messageMetadataById: workspace.messageMetadataById,
  sending: workspace.sending,
  hasBlockingInterrupt,
  editingMessageId,
  editingMessageValue,
  selectBranch: workspace.selectBranch,
  retryMessage: workspace.retryMessage,
  editHumanMessage: workspace.editHumanMessage
})

async function handleCopyMessage(message: Message) {
  const text = getMessageText(message.content).trim()
  if (!text) {
    uiStore.pushToast({
      type: 'warning',
      title: '没有可复制的文本',
      message: '当前消息主要是附件或结构化数据。'
    })
    return
  }

  const copied = await copyText(text)
  uiStore.pushToast({
    type: copied ? 'success' : 'error',
    title: copied ? '消息已复制' : '复制失败',
    message: copied ? '已写入系统剪贴板。' : '浏览器拒绝了复制动作。'
  })
}

async function submitEditMessage(message: Message, messageId: string, parentCheckpointId?: string) {
  const result = await messageActions.submitEditMessage(message, messageId, parentCheckpointId)
  if (!result.ok && result.reason === 'empty-content') {
    uiStore.pushToast({
      type: 'warning',
      title: '消息内容不能为空',
      message: '至少保留一段文本或者附件。'
    })
  }

  if (result.ok) {
    uiStore.pushToast({
      type: 'success',
      title: '已基于历史节点重发消息',
      message: '新的分支回复已经开始生成。'
    })
  }
}

async function handleRetryMessage(messageId: string, parentCheckpointId?: string) {
  const retried = await messageActions.handleRetryMessage(messageId, parentCheckpointId)
  if (retried) {
    uiStore.pushToast({
      type: 'success',
      title: '已重新生成回复',
      message: '当前回复会从对应 checkpoint 重新执行。'
    })
  }
}

async function handleDeleteThread(threadId: string) {
  if (!threadId.trim() || deletingThreadId.value) {
    return
  }

  const confirmed =
    typeof window === 'undefined'
      ? true
      : window.confirm('删除这个会话后无法恢复，确认继续吗？')

  if (!confirmed) {
    return
  }

  deletingThreadId.value = threadId
  try {
    await workspace.deleteThread(threadId)
    uiStore.pushToast({
      type: 'success',
      title: '会话已删除',
      message: threadId
    })
  } catch (error) {
    uiStore.pushToast({
      type: 'error',
      title: '删除失败',
      message: error instanceof Error ? error.message : '线程删除失败'
    })
  } finally {
    deletingThreadId.value = ''
  }
}

async function handleSend() {
  const draftContent = composerInput.value
  const draftAttachments = composerAttachments.value.map((attachment) => ({
    ...attachment,
    metadata: attachment.metadata ? { ...attachment.metadata } : undefined
  }))

  if (!draftContent.trim() && draftAttachments.length === 0) {
    return
  }

  composerInput.value = ''
  attachmentState.resetAttachments()

  void workspace.sendMessage(draftContent, draftAttachments)
    .then((sent) => {
      if (sent) {
        return
      }

      if (!composerInput.value.trim() && composerAttachments.value.length === 0) {
        composerInput.value = draftContent
        attachmentState.attachments.value = draftAttachments
      }
    })
    .catch(() => {
      if (!composerInput.value.trim() && composerAttachments.value.length === 0) {
        composerInput.value = draftContent
        attachmentState.attachments.value = draftAttachments
      }
    })
}

async function handleSelectThread(threadId: string) {
  await workspace.selectThread(threadId)
  threadsDrawerOpen.value = false
}

function handleResetTarget() {
  emit('reset-target')
  contextDrawerOpen.value = false
}

function syncDraftRunOptions() {
  draftRunOptions.modelId = workspace.runOptions.modelId
  draftRunOptions.systemPrompt = workspace.runOptions.systemPrompt
  draftRunOptions.enableTools = workspace.runOptions.enableTools
  draftRunOptions.toolNames = [...workspace.runOptions.toolNames]
  draftRunOptions.temperature = workspace.runOptions.temperature
  draftRunOptions.maxTokens = workspace.runOptions.maxTokens
}

function openRuntimeOptionsDialog() {
  syncDraftRunOptions()
  runtimeOptionsDialogOpen.value = true
}

function openInspectorDrawer(tab: InspectorTabKey = 'overview') {
  inspectorInitialTab.value = tab
  contextDrawerOpen.value = true
}

function toggleDraftTool(toolKey: string) {
  const normalizedToolKey = toolKey.trim()
  if (!normalizedToolKey) {
    return
  }

  const exists = draftRunOptions.toolNames.includes(normalizedToolKey)
  draftRunOptions.toolNames = exists
    ? draftRunOptions.toolNames.filter((item) => item !== normalizedToolKey)
    : [...draftRunOptions.toolNames, normalizedToolKey]
}

function restoreDraftRunOptions() {
  syncDraftRunOptions()
}

function applyDraftRunOptions() {
  workspace.runOptions.modelId = draftRunOptions.modelId || workspace.defaultModelId.value
  workspace.runOptions.systemPrompt = draftRunOptions.systemPrompt
  workspace.runOptions.enableTools = draftRunOptions.enableTools
  workspace.runOptions.toolNames = [...draftRunOptions.toolNames]
  workspace.runOptions.temperature = draftRunOptions.temperature
  workspace.runOptions.maxTokens = draftRunOptions.maxTokens
  runtimeOptionsDialogOpen.value = false
}

function handleJumpToLatest() {
  resumeAutoFollow('smooth')
}

function handleMessageMetaExpandedChange(messageId: string, expanded: boolean) {
  const normalizedId = messageId.trim()
  if (!normalizedId) {
    return
  }

  if (expanded) {
    if (!expandedMessageMetaIds.value.includes(normalizedId)) {
      expandedMessageMetaIds.value = [...expandedMessageMetaIds.value, normalizedId]
    }
    setFollowPauseReason('messageMeta', true, { skipScroll: true })
    return
  }

  if (!expandedMessageMetaIds.value.includes(normalizedId)) {
    return
  }

  expandedMessageMetaIds.value = expandedMessageMetaIds.value.filter((item) => item !== normalizedId)
  setFollowPauseReason('messageMeta', expandedMessageMetaIds.value.length > 0, {
    resumeBehavior: 'smooth'
  })
}

async function handleCancelRun() {
  await workspace.cancelActiveRun()
}
</script>

<template>
  <section
    class="pw-page-shell flex flex-1 min-h-0 flex-col"
    :class="
      isFocusMode
        ? 'fixed inset-0 z-[95] m-0 h-[100dvh] overflow-hidden bg-gray-50 p-4 dark:bg-dark-950 md:p-5 lg:p-6'
        : ''
    "
  >
    <div
      v-if="isFocusMode"
      class="flex items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white px-3 py-2 shadow-sm dark:border-dark-800 dark:bg-dark-900"
    >
      <div class="min-w-0 flex items-center gap-2">
        <div class="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
          专注模式
        </div>
        <span class="text-gray-300 dark:text-dark-700">·</span>
        <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
          {{ display.title }}
        </div>
      </div>

      <div class="flex items-center gap-2">
        <span class="hidden text-xs text-gray-400 dark:text-dark-500 md:inline">Esc 退出</span>
        <BaseButton
          variant="secondary"
          class="h-8 px-3 text-xs"
          @click="toggleFocusMode(false)"
        >
          <BaseIcon
            name="x"
            size="sm"
          />
          退出专注模式
        </BaseButton>
      </div>
    </div>

    <PageHeader
      v-if="!isFocusMode"
      :eyebrow="props.target?.targetType === 'graph' ? 'Graph Chat' : 'Assistant Chat'"
      :title="display.title"
      :description="display.description"
      :compact="isSurfaceCompact"
    />

    <StateBanner
      v-if="contextNotice && !isSurfaceCompact"
      title="上下文说明"
      :description="contextNotice"
      variant="success"
      :compact="isSurfaceCompact"
    />

    <StateBanner
      v-if="!isFocusMode && workspace.error.value"
      title="聊天线程加载失败"
      :description="workspace.error.value"
      variant="danger"
      :compact="isSurfaceCompact"
    />

    <StateBanner
      v-if="!isFocusMode && activeRunFailureDescription"
      title="当前对话运行失败"
      :description="activeRunFailureDescription"
      variant="danger"
      :compact="isSurfaceCompact"
    />

    <StateBanner
      v-if="!isFocusMode && workspace.runtimeError.value"
      title="运行时目录加载失败"
      :description="workspace.runtimeError.value"
      variant="warning"
      :compact="isSurfaceCompact"
    />

    <StateBanner
      v-if="!isFocusMode && workspace.detailInfo.value && !runtimeInfoDismissed"
      title="运行状态更新"
      :description="workspace.detailInfo.value"
      variant="info"
      :compact="isSurfaceCompact"
      dismissible
      @close="runtimeInfoDismissed = true"
    />

    <StateBanner
      v-if="!isFocusMode && workspace.detailWarning.value"
      title="会话状态部分未同步"
      :description="workspace.detailWarning.value"
      variant="warning"
      :compact="isSurfaceCompact"
    />

    <StateBanner
      v-if="!isFocusMode && workspace.isViewingBranch.value"
      title="当前正在查看历史分支"
      description="你现在看到的是某个 checkpoint 分支下的消息快照。继续发送、编辑或重试时，会基于这个分支重新生成新的对话路径。"
      variant="info"
      :compact="isSurfaceCompact"
    />

    <EmptyState
      v-if="!currentProject"
      icon="project"
      title="请先选择项目"
      description="Chat 是严格的项目级工作区。没有项目上下文，线程、图谱和助手这些东西全都不成立。"
    />

    <EmptyState
      v-else-if="!target"
      icon="chat"
      title="请先选择聊天目标"
      description="当前页已经是聊天工作台，但没有明确 assistant 或 graph，先从入口页选一个真实目标再进来。"
    />

    <EmptyState
      v-else-if="workspace.accessDeniedMessage.value"
      icon="shield"
      title="当前项目没有运行工作台权限"
      :description="workspace.accessDeniedMessage.value"
      action-label="重新同步"
      @action="workspace.refreshActiveThread"
    />

    <SurfaceCard
      v-else
      class="pw-chat-workspace p-0"
    >
      <div
        v-if="!isFocusMode"
        class="pw-chat-workspace-header"
        :class="workspaceHeaderCollapsed ? 'py-1' : ''"
      >
        <div class="flex h-8 items-center gap-3">
          <div
            v-if="showContextBar && !workspaceHeaderCollapsed"
            class="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto"
            :class="isSurfaceCompact ? 'gap-1.5' : ''"
          >
            <span
              v-for="pill in headerPills"
              :key="pill.label"
              class="pw-pill shrink-0"
              :class="isSurfaceCompact ? 'gap-1.5 px-2.5 py-1 text-[11px]' : 'px-2.5 py-1 text-[11px]'"
            >
              <span class="text-gray-400 dark:text-dark-400">{{ pill.label }}</span>
              <span class="max-w-[180px] truncate text-gray-700 dark:text-white">{{ pill.value }}</span>
            </span>
          </div>

          <div
            class="ml-auto flex shrink-0 items-center gap-2 overflow-x-auto"
            :class="isSurfaceCompact ? 'gap-1.5' : ''"
          >
            <div
              v-if="liveFollowView.visible && !workspaceHeaderCollapsed"
              class="pw-pill-soft gap-1.5 px-2.5 py-1.5 text-[11px] font-medium"
              :class="[liveFollowPillClass, isSurfaceCompact ? 'gap-1.5 px-2.5 py-1.5 text-[11px]' : '']"
            >
              <BaseIcon
                :name="liveFollowView.icon"
                size="xs"
              />
              <span>{{ liveFollowView.pillLabel }}</span>
            </div>
            <template v-if="!workspaceHeaderCollapsed">
              <BaseButton
                variant="secondary"
                class="h-8 px-3 text-xs"
                @click="toggleFocusMode(true)"
              >
                <BaseIcon
                  name="focus"
                  size="sm"
                />
                专注模式
              </BaseButton>
              <div class="flex items-center gap-1">
                <BaseButton
                  variant="secondary"
                  class="h-8 px-3 text-xs"
                  @click="threadsDrawerOpen = true"
                >
                  <BaseIcon
                    name="threads"
                    size="sm"
                  />
                  会话 {{ workspace.threadItems.value.length }}
                </BaseButton>
              </div>
              <BaseButton
                variant="secondary"
                class="h-8 px-3 text-xs"
                @click="openInspectorDrawer('overview')"
              >
                <BaseIcon
                  name="overview"
                  size="sm"
                />
                会话详情
              </BaseButton>
              <div v-if="allowRunOptions">
                <BaseButton
                  variant="secondary"
                  class="h-8 px-3 text-xs"
                  @click="openRuntimeOptionsDialog"
                >
                  <BaseIcon
                    name="runtime"
                    size="sm"
                  />
                  运行参数
                </BaseButton>
              </div>
              <BaseButton
                variant="secondary"
                class="h-8 px-3 text-xs"
                :disabled="workspace.loadingThreads.value || workspace.loadingThreadDetail.value"
                @click="workspace.refreshActiveThread"
              >
                <BaseIcon
                  name="refresh"
                  size="sm"
                />
                重新同步
              </BaseButton>
              <BaseButton
                class="h-8 px-3 text-xs"
                :disabled="!workspace.canStartThread.value"
                @click="workspace.startNewThread"
              >
                <BaseIcon
                  name="chat"
                  size="sm"
                />
                新对话
              </BaseButton>
            </template>
            <BaseButton
              variant="secondary"
              class="h-8 px-3 text-xs"
              @click="toggleWorkspaceHeaderCollapsed(!workspaceHeaderCollapsed)"
            >
              {{ workspaceHeaderCollapsed ? '打开顶部栏' : '收起顶部栏' }}
            </BaseButton>
          </div>
        </div>
      </div>

      <div
        class="relative z-10 min-h-0 flex flex-1 flex-col overflow-hidden"
        :class="
          showArtifacts && hasArtifactEntries
            ? isSurfaceCompact
              ? 'lg:grid lg:grid-cols-[minmax(0,1fr)_320px]'
              : 'lg:grid lg:grid-cols-[minmax(0,1fr)_360px]'
            : ''
        "
      >
        <div class="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <div
            ref="messagesViewport"
            class="pw-chat-stream"
            :class="isSurfaceCompact ? 'px-4 py-3 md:px-5 md:py-4' : ''"
            @scroll="handleMessagesScroll"
          >
            <div
              ref="messagesContent"
              class="pw-chat-stream-content"
            >
              <div
                v-if="workspace.loadingThreadDetail.value && renderMessages.length === 0"
                class="space-y-4"
              >
                <div
                  v-for="index in 3"
                  :key="index"
                  class="pw-panel-muted h-28 animate-pulse"
                />
              </div>

              <ChatMessageList
                v-else-if="displayMessages.length > 0"
                :display-messages="displayMessages"
                :all-messages="renderMessages"
                :editing-message-id="editingMessageId"
                :editing-message-value="editingMessageValue"
                :is-running="workspace.sending.value"
                :stream-handle="workspace.streamHandle"
                :tool-calls="workspace.toolCalls.value"
                :get-message-meta="messageActions.getMessageMeta"
                :get-message-branch-index="messageActions.getMessageBranchIndex"
                :has-branch-switcher="messageActions.hasBranchSwitcher"
                :can-edit-message="messageActions.canEditMessage"
                :can-retry-message="messageActions.canRetryMessage"
                @update:editing-message-value="editingMessageValue = $event"
                @copy-message="handleCopyMessage"
                @cancel-edit="messageActions.cancelEditMessage"
                @submit-edit="submitEditMessage"
                @start-edit="messageActions.startEditMessage"
                @retry-message="handleRetryMessage"
                @select-previous-branch="messageActions.selectPreviousMessageBranch"
                @select-next-branch="messageActions.selectNextMessageBranch"
                @message-meta-expanded-change="handleMessageMetaExpandedChange"
              />

              <div
                v-else
                class="pw-chat-empty-state"
              >
                <span class="pw-chat-empty-mark">
                  <BaseIcon
                    name="chat"
                    size="lg"
                  />
                </span>
                <h2 class="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
                  {{ display.emptyTitle || '开始新的对话' }}
                </h2>
                <p class="mt-2 max-w-lg text-sm leading-7 text-gray-500 dark:text-dark-300">
                  {{ display.emptyDescription || '输入任务目标后，Agent 会在这里展示回复、执行步骤与需要你确认的操作。' }}
                </p>
              </div>

              <ChatInterruptPanel
                v-if="hasBlockingInterrupt"
                class="pw-chat-interrupt"
                :interrupt="workspace.interruptPayload.value"
                :submitting="workspace.sending.value"
                :on-resume="workspace.resumeInterruptedRun"
                :on-resume-all="workspace.resumeAllInterruptedRuns"
              />
            </div>
          </div>

          <div
            v-if="showJumpToLatestNotice"
            class="pointer-events-none absolute bottom-5 right-5 z-10 flex justify-end"
          >
            <div class="pointer-events-auto pw-panel w-[calc(100vw-2.5rem)] px-4 py-3 sm:w-[320px]">
              <div class="flex items-start gap-3">
                <span class="mt-1 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/30 dark:text-primary-100">
                  <BaseIcon
                    :name="liveFollowView.icon"
                    size="sm"
                  />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="block text-sm font-semibold text-gray-900 dark:text-white">
                    {{ jumpToLatestTitle }}
                  </span>
                  <span class="mt-1 block text-xs leading-6 text-gray-500 dark:text-dark-300">
                    {{ jumpToLatestDescription }}
                  </span>
                </span>
              </div>
              <div class="mt-3 flex flex-wrap justify-end gap-2">
                <BaseButton
                  v-if="liveFollowView.showStopAction"
                  variant="danger"
                  :disabled="workspace.cancelling.value"
                  @click="handleCancelRun"
                >
                  <BaseIcon
                    name="x"
                    size="sm"
                  />
                  {{ workspace.cancelling.value ? '停止中...' : '停止生成' }}
                </BaseButton>
                <BaseButton @click="handleJumpToLatest">
                  <BaseIcon
                    name="chevron-down"
                    size="sm"
                  />
                  回到最新
                </BaseButton>
              </div>
            </div>
          </div>
        </div>

        <ChatArtifactPanel
          v-if="showArtifacts && hasArtifactEntries"
          :values="workspace.displayState.value"
        />
      </div>

      <ChatComposer
        v-model="composerInput"
        :attachments="composerAttachments"
        :is-running="workspace.sending.value"
        :has-blocking-interrupt="hasBlockingInterrupt"
        :can-start-thread="workspace.canStartThread.value"
        :show-continue-action="false"
        :can-send-fresh-message="canSendFreshMessage"
        :cancelling="workspace.cancelling.value"
        send-button-label="发送消息"
        :last-event-at="workspace.lastEventAt.value"
        :compact="isSurfaceCompact"
        :focus-mode="isFocusMode"
        @send="handleSend"
        @cancel="handleCancelRun"
        @new-thread="workspace.startNewThread"
        @file-input-change="attachmentState.handleInputChange"
        @composer-paste="attachmentState.handlePaste"
        @remove-attachment="attachmentState.removeAttachment"
      />
    </SurfaceCard>

    <ChatThreadDrawer
      :show="threadsDrawerOpen"
      :show-context-bar="showContextBar"
      :target-text="workspace.targetText.value"
      :target-type-text="workspace.targetTypeText.value"
      :search="threadSearch"
      :status-filter="threadStatusFilter"
      :filters="threadStatusFilters"
      :loading="workspace.loadingThreads.value"
      :thread-count="workspace.threadItems.value.length"
      :filtered-count="filteredThreadSummary.length"
      :can-start-thread="workspace.canStartThread.value"
      :active-thread-id="workspace.activeThreadId.value"
      :deleting-thread-id="deletingThreadId"
      :groups="groupedThreadSummary"
      @close="threadsDrawerOpen = false"
      @update:search="threadSearch = $event"
      @update:status-filter="threadStatusFilter = $event"
      @start-new-thread="workspace.startNewThread"
      @select-thread="handleSelectThread"
      @delete-thread="handleDeleteThread"
    />

    <ChatContextDrawer
      :show="contextDrawerOpen"
      :initial-tab="inspectorInitialTab"
      :show-history="showHistory"
      :show-artifacts="showArtifacts"
      :allow-reset-target="allowResetTarget"
      :target-text="workspace.targetText.value"
      :project-name="currentProject?.name || ''"
      :active-thread-id="workspace.activeThreadId.value"
      :last-run-id="workspace.lastRunId.value"
      :selected-branch="workspace.selectedBranch.value"
      :latest-message-preview="workspace.latestMessagePreview.value"
      :history-items="workspace.historyItems.value"
      :is-viewing-branch="workspace.isViewingBranch.value"
      :plan-view="planView"
      :files="inspectorFiles"
      :values="workspace.displayState.value"
      :is-running="workspace.sending.value"
      :has-interrupt="hasBlockingInterrupt"
      :source-note="props.sourceNote"
      :context-notice="props.contextNotice"
      :on-update-state="workspace.updateThreadStatePatch"
      @close="contextDrawerOpen = false"
      @select-branch="workspace.selectBranch($event)"
      @reset-target="handleResetTarget"
    />

    <ChatRunOptionsDialog
      :show="runtimeOptionsDialogOpen"
      :selected-tools-label="selectedToolsLabel"
      :draft-run-options="draftRunOptions"
      :runtime-models="workspace.runtimeModels.value"
      :runtime-tools="workspace.runtimeTools.value"
      :loading-runtime="workspace.loadingRuntime.value"
      @close="runtimeOptionsDialogOpen = false"
      @update:model-id="draftRunOptions.modelId = $event"
      @update:system-prompt="draftRunOptions.systemPrompt = $event"
      @update:enable-tools="draftRunOptions.enableTools = $event"
      @toggle-tool="toggleDraftTool"
      @update:temperature="draftRunOptions.temperature = $event"
      @update:max-tokens="draftRunOptions.maxTokens = $event"
      @restore="restoreDraftRunOptions"
      @apply="applyDraftRunOptions"
    />
  </section>
</template>
