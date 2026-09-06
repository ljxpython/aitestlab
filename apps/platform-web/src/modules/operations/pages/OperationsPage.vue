<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import { usePagination } from '@/composables/usePagination'
import ActionMenu from '@/components/platform/ActionMenu.vue'
import BulkActionsBar from '@/components/platform/BulkActionsBar.vue'
import DataTable from '@/components/platform/DataTable.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { ActionMenuItem, BulkActionItem, DataTableColumn } from '@/components/platform/data-table'
import {
  bulkArchiveOperations,
  bulkCancelOperations,
  bulkRestoreOperations,
  cancelOperation,
  cleanupExpiredOperationArtifacts,
  createOperationPageStream,
  downloadOperationArtifact,
  getOperationDetail,
  listOperations
} from '@/services/operations/operations.service'
import { useUiStore } from '@/stores/ui'
import type {
  ManagementOperation,
  OperationArchiveScope,
  OperationStatus
} from '@/types/management'
import { downloadBlob } from '@/utils/browser-download'
import { formatDateTime, shortId } from '@/utils/format'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

const router = useRouter()
const { activeProjectId, activeProject } = useWorkspaceProjectContext()
const uiStore = useUiStore()
const authorization = useAuthorization()
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:operations:page-size'
})

const scope = ref<'project' | 'global'>('project')
const kindInput = ref('')
const statusInput = ref<'' | OperationStatus>('')
const requestedByInput = ref('')
const archiveScope = ref<OperationArchiveScope>('exclude')

const kind = ref('')
const status = ref<OperationStatus | undefined>(undefined)
const requestedBy = ref('')

const loading = ref(false)
const bulkPending = ref(false)
const cleanupPending = ref(false)
const cancellingId = ref('')
const error = ref('')
const notice = ref('')
const items = ref<ManagementOperation[]>([])
const selectedOperationIds = ref<string[]>([])
const liveMode = ref<'connecting' | 'stream' | 'polling'>('connecting')
const liveHeartbeatAt = ref('')

const detailDialogOpen = ref(false)
const detailLoading = ref(false)
const selectedOperation = ref<ManagementOperation | null>(null)

const currentProject = activeProject
const canReadGlobalOperations = computed(() => authorization.can('platform.operation.read'))
const canReadProjectOperations = computed(() =>
  authorization.can('project.operation.read', activeProjectId.value)
)
const canMutateCurrentScope = computed(() =>
  scope.value === 'global'
    ? authorization.can('platform.operation.write')
    : authorization.can('project.operation.write', activeProjectId.value)
)

const runningCount = computed(() =>
  items.value.filter((item) => item.status === 'submitted' || item.status === 'running').length
)
const failedCount = computed(() => items.value.filter((item) => item.status === 'failed').length)
const succeededCount = computed(() => items.value.filter((item) => item.status === 'succeeded').length)
const archivedCount = computed(() => items.value.filter((item) => Boolean(item.archived_at)).length)
const selectedOperations = computed(() =>
  items.value.filter((item) => selectedOperationIds.value.includes(item.id))
)
const selectedTerminalOperationIds = computed(() =>
  selectedOperations.value.filter((item) => isTerminal(item.status)).map((item) => item.id)
)
const selectedRunningOperationIds = computed(() =>
  selectedOperations.value.filter((item) => !isTerminal(item.status)).map((item) => item.id)
)
const selectedArchivedOperationIds = computed(() =>
  selectedOperations.value.filter((item) => Boolean(item.archived_at)).map((item) => item.id)
)

const stats = computed(() => [
  {
    label: '当前范围',
    value: scope.value === 'project' ? currentProject.value?.name || '当前项目' : 'Global',
    hint: scope.value === 'project' ? '只看当前项目相关操作' : '跨项目统一操作视图',
    icon: 'project',
    tone: 'primary'
  },
  {
    label: '活跃任务',
    value: runningCount.value,
    hint: 'submitted / running 状态的操作',
    icon: 'activity',
    tone: runningCount.value > 0 ? 'warning' : 'success'
  },
  {
    label: '失败任务',
    value: failedCount.value,
    hint: '当前页可见的 failed 操作数量',
    icon: 'alert',
    tone: failedCount.value > 0 ? 'danger' : 'success'
  },
  {
    label: '已完成',
    value: succeededCount.value,
    hint: `当前结果集总数 ${pagination.total.value}`,
    icon: 'check',
    tone: 'success'
  },
  {
    label: '已归档',
    value: archivedCount.value,
    hint: archiveScope.value === 'exclude' ? '默认视图已隐藏已归档记录' : '当前结果集中的已归档操作',
    icon: 'archive',
    tone: archivedCount.value > 0 ? 'neutral' : 'success'
  }
])

const rows = computed(() => items.value as unknown as Record<string, unknown>[])

const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'created_at',
    label: '提交时间',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.created_at || ''
  },
  {
    key: 'kind',
    label: 'Kind',
    sortable: true,
    sortValue: (row) => row.kind || ''
  },
  {
    key: 'status',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.status || ''
  },
  {
    key: 'project_id',
    label: '项目 / 操作人',
    sortable: true,
    sortValue: (row) => `${row.project_id || ''}:${row.requested_by || ''}`
  },
  {
    key: 'updated_at',
    label: '更新时间',
    sortable: true,
    sortValue: (row) => row.updated_at || ''
  }
])

function isTerminal(statusValue: OperationStatus) {
  return statusValue === 'succeeded' || statusValue === 'failed' || statusValue === 'cancelled'
}

function statusTone(statusValue: OperationStatus): 'neutral' | 'success' | 'warning' | 'danger' {
  if (statusValue === 'succeeded') {
    return 'success'
  }
  if (statusValue === 'failed' || statusValue === 'cancelled') {
    return 'danger'
  }
  if (statusValue === 'running' || statusValue === 'submitted') {
    return 'warning'
  }
  return 'neutral'
}

function operationFromRow(row: Record<string, unknown>) {
  return row as ManagementOperation
}

function canMutateOperation(operation: ManagementOperation): boolean {
  return operation.project_id
    ? authorization.can('project.operation.write', operation.project_id)
    : authorization.can('platform.operation.write')
}

function formatJson(value: Record<string, unknown> | null | undefined) {
  if (!value || Object.keys(value).length === 0) {
    return ''
  }

  return JSON.stringify(value, null, 2)
}

function inferResourceRoute(operation: ManagementOperation) {
  if (operation.kind === 'runtime.models.refresh') {
    return '/workspace/runtime/models'
  }
  if (operation.kind === 'runtime.tools.refresh') {
    return '/workspace/runtime/models'
  }
  if (operation.kind === 'runtime.graphs.refresh') {
    return '/workspace/graphs'
  }
  if (operation.kind === 'assistant.resync') {
    const assistantId = String(operation.result_payload.id || operation.input_payload.assistant_id || '').trim()
    return assistantId ? `/workspace/assistants/${encodeURIComponent(assistantId)}` : '/workspace/assistants'
  }
  if (operation.kind === 'testcase.documents.export') {
    return '/workspace/testcase/documents'
  }
  if (operation.kind === 'testcase.cases.export') {
    return '/workspace/testcase/cases'
  }
  if (
    (operation.kind === 'knowledge.documents.scan' ||
      operation.kind === 'knowledge.documents.clear') &&
    operation.project_id
  ) {
    return `/workspace/projects/${operation.project_id}/knowledge/documents`
  }
  return ''
}

function hasArtifact(operation: ManagementOperation | null) {
  if (!operation) {
    return false
  }
  const artifact = operation.result_payload?._artifact
  return Boolean(artifact && typeof artifact === 'object' && !isArtifactExpired(operation))
}

function artifactExpiresAt(operation: ManagementOperation | null) {
  if (!operation) {
    return ''
  }
  const topLevel = operation.result_payload?.artifact_expires_at
  if (typeof topLevel === 'string' && topLevel.trim()) {
    return topLevel.trim()
  }
  const artifact = operation.result_payload?._artifact
  if (artifact && typeof artifact === 'object') {
    const expiresAt = (artifact as Record<string, unknown>).expires_at
    if (typeof expiresAt === 'string' && expiresAt.trim()) {
      return expiresAt.trim()
    }
  }
  return ''
}

function artifactStorageBackend(operation: ManagementOperation | null) {
  if (!operation) {
    return ''
  }
  const topLevel = operation.result_payload?.artifact_storage_backend
  if (typeof topLevel === 'string' && topLevel.trim()) {
    return topLevel.trim()
  }
  const artifact = operation.result_payload?._artifact
  if (artifact && typeof artifact === 'object') {
    const backend = (artifact as Record<string, unknown>).storage_backend
    if (typeof backend === 'string' && backend.trim()) {
      return backend.trim()
    }
  }
  return ''
}

function isArtifactExpired(operation: ManagementOperation | null) {
  const expiresAt = artifactExpiresAt(operation)
  if (!expiresAt) {
    return false
  }
  const parsed = Date.parse(expiresAt)
  return !Number.isNaN(parsed) && parsed <= Date.now()
}

function clearSelection() {
  selectedOperationIds.value = []
}

function updateSelectedOperationIds(keys: Array<string | number>) {
  selectedOperationIds.value = keys.map(String)
}

function applyOperationPage(payload: { items: ManagementOperation[]; total: number }) {
  items.value = payload.items
  pagination.setTotal(payload.total)
  selectedOperationIds.value = selectedOperationIds.value.filter((id) =>
    payload.items.some((item) => item.id === id)
  )

  if (selectedOperation.value) {
    const current = payload.items.find((item) => item.id === selectedOperation.value?.id)
    if (current) {
      selectedOperation.value = current
    }
  }
}

async function loadOperations(options?: { silent?: boolean }) {
  if (!options?.silent) {
    loading.value = true
  }
  error.value = ''

  try {
    const payload = await listOperations({
      projectId: scope.value === 'project' ? activeProjectId.value || undefined : undefined,
      kind: kind.value || undefined,
      status: status.value,
      requestedBy: requestedBy.value || undefined,
      archiveScope: archiveScope.value,
      limit: pagination.pageSize.value,
      offset: pagination.offset.value
    })
    applyOperationPage(payload)
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value = resolvePlatformHttpErrorMessage(loadError, '操作中心加载失败', '操作中心')
  } finally {
    if (!options?.silent) {
      loading.value = false
    }
  }
}

function applyFilters() {
  kind.value = kindInput.value.trim()
  status.value = statusInput.value || undefined
  requestedBy.value = requestedByInput.value.trim()
  if (pagination.page.value === 1) {
    restartLiveUpdates()
    return
  }
  pagination.resetPage()
}

function resetFilters() {
  kindInput.value = ''
  statusInput.value = ''
  requestedByInput.value = ''
  kind.value = ''
  status.value = undefined
  requestedBy.value = ''
  archiveScope.value = 'exclude'
  if (pagination.page.value === 1) {
    restartLiveUpdates()
    return
  }
  pagination.resetPage()
}

async function openOperationDetail(operationId: string) {
  detailDialogOpen.value = true
  detailLoading.value = true
  try {
    selectedOperation.value = await getOperationDetail(operationId)
  } catch (detailError) {
    selectedOperation.value = null
    error.value = resolvePlatformHttpErrorMessage(detailError, '操作详情加载失败', '操作中心')
  } finally {
    detailLoading.value = false
  }
}

function closeOperationDetail() {
  detailDialogOpen.value = false
  selectedOperation.value = null
}

async function handleCancel(operation: ManagementOperation) {
  if (!canMutateOperation(operation)) {
    error.value = '当前账号没有修改该操作的权限'
    return
  }
  cancellingId.value = operation.id
  error.value = ''
  notice.value = ''

  try {
    const updated = await cancelOperation(operation.id)
    notice.value = `操作 ${shortId(updated.id)} 已取消`
    uiStore.pushToast({
      type: 'success',
      title: '操作已取消',
      message: notice.value
    })
    if (selectedOperation.value?.id === updated.id) {
      selectedOperation.value = updated
    }
    await loadOperations()
  } catch (cancelError) {
    error.value = resolvePlatformHttpErrorMessage(cancelError, '取消操作失败', '操作中心')
  } finally {
    cancellingId.value = ''
  }
}

async function handleBulkCancel() {
  if (!selectedRunningOperationIds.value.length) {
    return
  }
  if (!canMutateCurrentScope.value) {
    error.value = '当前账号没有批量修改操作的权限'
    return
  }
  bulkPending.value = true
  error.value = ''
  try {
    const result = await bulkCancelOperations(selectedRunningOperationIds.value)
    notice.value = `已取消 ${result.updated_count} 个操作`
    clearSelection()
    await loadOperations()
  } catch (bulkError) {
    error.value = resolvePlatformHttpErrorMessage(bulkError, '批量取消操作失败', '操作中心')
  } finally {
    bulkPending.value = false
  }
}

async function handleBulkArchive() {
  if (!selectedTerminalOperationIds.value.length) {
    return
  }
  if (!canMutateCurrentScope.value) {
    error.value = '当前账号没有批量修改操作的权限'
    return
  }
  bulkPending.value = true
  error.value = ''
  try {
    const result = await bulkArchiveOperations(selectedTerminalOperationIds.value)
    notice.value = `已归档 ${result.updated_count} 个操作`
    clearSelection()
    await loadOperations()
  } catch (bulkError) {
    error.value = resolvePlatformHttpErrorMessage(bulkError, '批量归档失败', '操作中心')
  } finally {
    bulkPending.value = false
  }
}

async function handleBulkRestore() {
  if (!selectedArchivedOperationIds.value.length) {
    return
  }
  if (!canMutateCurrentScope.value) {
    error.value = '当前账号没有批量修改操作的权限'
    return
  }
  bulkPending.value = true
  error.value = ''
  try {
    const result = await bulkRestoreOperations(selectedArchivedOperationIds.value)
    notice.value = `已恢复 ${result.updated_count} 个操作`
    clearSelection()
    await loadOperations()
  } catch (bulkError) {
    error.value = resolvePlatformHttpErrorMessage(bulkError, '批量恢复归档失败', '操作中心')
  } finally {
    bulkPending.value = false
  }
}

async function handleDownloadArtifact(operation: ManagementOperation) {
  if (isArtifactExpired(operation)) {
    error.value = '该操作产物已过期，请重新触发导出。'
    return
  }
  try {
    const download = await downloadOperationArtifact(operation.id)
    downloadBlob(
      download.blob,
      download.filename ||
        `operation-${operation.kind}-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}`
    )
    uiStore.pushToast({
      type: 'success',
      title: '结果已下载',
      message: download.filename || shortId(operation.id)
    })
  } catch (downloadError) {
    error.value = resolvePlatformHttpErrorMessage(downloadError, '下载操作产物失败', '操作结果下载')
  }
}

async function handleCleanupExpiredArtifacts() {
  if (!authorization.can('platform.operation.write')) {
    error.value = '当前账号没有清理操作产物的权限'
    return
  }
  cleanupPending.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await cleanupExpiredOperationArtifacts()
    notice.value = `已清理 ${result.removed_count} 个过期产物，回收 ${result.bytes_reclaimed} bytes。`
    uiStore.pushToast({
      type: 'success',
      title: '过期产物已清理',
      message: `removed ${result.removed_count} / scanned ${result.scanned_count}`
    })
    await loadOperations({ silent: true })
    if (selectedOperation.value) {
      selectedOperation.value = await getOperationDetail(selectedOperation.value.id)
    }
  } catch (cleanupError) {
    error.value = resolvePlatformHttpErrorMessage(cleanupError, '清理过期产物失败', '操作产物')
  } finally {
    cleanupPending.value = false
  }
}

async function handleSingleArchive(operation: ManagementOperation) {
  if (!canMutateOperation(operation)) {
    error.value = '当前账号没有修改该操作的权限'
    return
  }
  bulkPending.value = true
  error.value = ''
  try {
    const result = await bulkArchiveOperations([operation.id])
    notice.value = `已归档 ${result.updated_count} 个操作`
    await loadOperations()
    if (selectedOperation.value?.id === operation.id) {
      selectedOperation.value = await getOperationDetail(operation.id)
    }
  } catch (archiveError) {
    error.value = resolvePlatformHttpErrorMessage(archiveError, '归档操作失败', '操作中心')
  } finally {
    bulkPending.value = false
  }
}

async function handleSingleRestore(operation: ManagementOperation) {
  if (!canMutateOperation(operation)) {
    error.value = '当前账号没有修改该操作的权限'
    return
  }
  bulkPending.value = true
  error.value = ''
  try {
    const result = await bulkRestoreOperations([operation.id])
    notice.value = `已恢复 ${result.updated_count} 个操作`
    await loadOperations()
    if (selectedOperation.value?.id === operation.id) {
      selectedOperation.value = await getOperationDetail(operation.id)
    }
  } catch (restoreError) {
    error.value = resolvePlatformHttpErrorMessage(restoreError, '恢复归档失败', '操作中心')
  } finally {
    bulkPending.value = false
  }
}

function jumpToAudit(operation: ManagementOperation) {
  void router.push({
    path: '/workspace/audit',
    query: {
      targetType: 'operation',
      targetId: operation.id
    }
  })
}

function operationActions(operation: ManagementOperation): ActionMenuItem[] {
  const actions: ActionMenuItem[] = [
    {
      key: 'detail',
      label: '查看详情',
      icon: 'eye',
      onSelect: () => void openOperationDetail(operation.id)
    },
    {
      key: 'audit',
      label: '查看审计',
      icon: 'audit',
      onSelect: () => jumpToAudit(operation)
    }
  ]

  if (operation.archived_at) {
    actions.splice(1, 0, {
      key: 'restore',
      label: '恢复归档',
      icon: 'refresh',
      disabled: bulkPending.value || !canMutateOperation(operation),
      onSelect: () => void handleSingleRestore(operation)
    })
  } else if (isTerminal(operation.status)) {
    actions.splice(1, 0, {
      key: 'archive',
      label: '归档',
      icon: 'archive',
      disabled: bulkPending.value || !canMutateOperation(operation),
      onSelect: () => void handleSingleArchive(operation)
    })
  }

  if (hasArtifact(operation)) {
    actions.splice(1, 0, {
      key: 'download-artifact',
      label: '下载结果',
      icon: 'download',
      onSelect: () => void handleDownloadArtifact(operation)
    })
  }

  if (!isTerminal(operation.status)) {
    actions.push({
      key: 'cancel',
      label: cancellingId.value === operation.id ? '取消中...' : '取消操作',
      icon: 'x',
      disabled: cancellingId.value === operation.id || !canMutateOperation(operation),
      onSelect: () => void handleCancel(operation)
    })
  }

  return actions
}

const bulkActionSummary = computed(() => {
  if (!selectedOperations.value.length) {
    return ''
  }
  const terminal = selectedTerminalOperationIds.value.length
  const running = selectedRunningOperationIds.value.length
  const archived = selectedArchivedOperationIds.value.length
  return `可取消 ${running} 项，已结束 ${terminal} 项，已归档 ${archived} 项。`
})

const bulkActions = computed<BulkActionItem[]>(() => [
  {
    key: 'cancel',
    label: '批量取消',
    icon: 'x',
    variant: 'danger',
    disabled: bulkPending.value || selectedRunningOperationIds.value.length === 0 || !canMutateCurrentScope.value,
    onSelect: handleBulkCancel
  },
  {
    key: 'archive',
    label: '批量归档',
    icon: 'archive',
    variant: 'secondary',
    disabled: bulkPending.value || selectedTerminalOperationIds.value.length === 0 || !canMutateCurrentScope.value,
    onSelect: handleBulkArchive
  },
  {
    key: 'restore',
    label: '恢复归档',
    icon: 'refresh',
    variant: 'secondary',
    disabled: bulkPending.value || selectedArchivedOperationIds.value.length === 0 || !canMutateCurrentScope.value,
    onSelect: handleBulkRestore
  }
])

let refreshTimer: number | null = null
let streamReconnectTimer: number | null = null
let currentStreamAbortController: AbortController | null = null

function startRefreshTimer() {
  if (typeof window === 'undefined' || refreshTimer !== null) {
    return
  }

  refreshTimer = window.setInterval(() => {
    if (liveMode.value === 'stream' || liveMode.value === 'connecting') {
      return
    }
    const shouldRefreshList = items.value.some((item) => !isTerminal(item.status))
    const shouldRefreshDetail =
      detailDialogOpen.value && selectedOperation.value && !isTerminal(selectedOperation.value.status)
    if (shouldRefreshList || shouldRefreshDetail) {
      void loadOperations({ silent: true })
      if (shouldRefreshDetail && selectedOperation.value) {
        void openOperationDetail(selectedOperation.value.id)
      }
    }
  }, 3000)
}

function stopRefreshTimer() {
  if (refreshTimer !== null && typeof window !== 'undefined') {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function stopStreamReconnectTimer() {
  if (streamReconnectTimer !== null && typeof window !== 'undefined') {
    window.clearTimeout(streamReconnectTimer)
    streamReconnectTimer = null
  }
}

function stopOperationStream() {
  stopStreamReconnectTimer()
  currentStreamAbortController?.abort()
  currentStreamAbortController = null
}

function scheduleOperationStreamReconnect() {
  if (typeof window === 'undefined' || streamReconnectTimer !== null) {
    return
  }

  streamReconnectTimer = window.setTimeout(() => {
    streamReconnectTimer = null
    void startOperationStream()
  }, 5000)
}

async function startOperationStream() {
  if (typeof window === 'undefined') {
    return
  }

  stopOperationStream()
  const abortController = new AbortController()
  currentStreamAbortController = abortController
  liveMode.value = 'connecting'

  try {
    const stream = createOperationPageStream({
      projectId: scope.value === 'project' ? activeProjectId.value || undefined : undefined,
      kind: kind.value || undefined,
      status: status.value,
      requestedBy: requestedBy.value || undefined,
      archiveScope: archiveScope.value,
      limit: pagination.pageSize.value,
      offset: pagination.offset.value,
      signal: abortController.signal
    })

    for await (const event of stream) {
      if (event.event === 'heartbeat') {
        liveMode.value = 'stream'
        liveHeartbeatAt.value = event.data.at || new Date().toISOString()
        continue
      }

      applyOperationPage(event.data)
      liveMode.value = 'stream'
      liveHeartbeatAt.value = new Date().toISOString()
    }

    if (!abortController.signal.aborted && currentStreamAbortController === abortController) {
      liveMode.value = 'polling'
      currentStreamAbortController = null
      scheduleOperationStreamReconnect()
    }
  } catch (streamError) {
    if (!abortController.signal.aborted && currentStreamAbortController === abortController) {
      liveMode.value = 'polling'
      if (!error.value) {
        error.value = resolvePlatformHttpErrorMessage(
          streamError,
          '操作中心实时同步失败，当前已切回轮询兜底。',
          '操作中心实时同步'
        )
      }
      currentStreamAbortController = null
      scheduleOperationStreamReconnect()
    }
  }
}

function restartLiveUpdates() {
  void loadOperations()
  void startOperationStream()
}

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  restartLiveUpdates()
})

watch(activeProjectId, (projectId) => {
  if (!projectId && scope.value === 'project') {
    scope.value = 'global'
    return
  }

  if (scope.value === 'project') {
    restartLiveUpdates()
  }
})

watch(scope, (nextScope, previousScope) => {
  if (nextScope === previousScope) {
    return
  }

  if (pagination.page.value === 1) {
    restartLiveUpdates()
    return
  }
  pagination.resetPage()
})

onMounted(() => {
  if (!activeProjectId.value || !canReadProjectOperations.value) {
    scope.value = 'global'
  }
  restartLiveUpdates()
  startRefreshTimer()
})

onBeforeUnmount(() => {
  stopRefreshTimer()
  stopOperationStream()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Governance"
      title="Operations Center"
      description="所有异步或长耗时动作最终都应该回流到这里。现在 runtime refresh、assistant resync 和 testcase export 都已经统一接到同一条治理链路里。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="cleanupPending || !authorization.can('platform.operation.write')"
          @click="handleCleanupExpiredArtifacts"
        >
          <BaseIcon
            name="archive"
            size="sm"
          />
          {{ authorization.can('platform.operation.write') ? (cleanupPending ? '清理中...' : '清理过期产物') : '无清理权限' }}
        </BaseButton>
        <div
          class="mr-2 inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold"
          :title="liveHeartbeatAt ? `最近同步 ${formatDateTime(liveHeartbeatAt)}` : ''"
          :class="liveMode === 'stream'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-200'
            : liveMode === 'connecting'
              ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/40 dark:bg-sky-950/30 dark:text-sky-200'
              : 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200'"
        >
          <span
            class="h-2 w-2 rounded-full"
            :class="liveMode === 'stream'
              ? 'bg-emerald-500'
              : liveMode === 'connecting'
                ? 'bg-sky-500'
                : 'bg-amber-500'"
          />
          {{ liveMode === 'stream' ? '实时同步' : liveMode === 'connecting' ? '连接中' : '轮询兜底' }}
        </div>
        <BaseButton
          variant="secondary"
          :disabled="loading"
          @click="restartLiveUpdates"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新列表
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="操作中心加载失败"
      :description="error"
      variant="danger"
    />
    <StateBanner
      v-else-if="notice"
      title="操作状态已更新"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-4 xl:grid-cols-4">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <TablePageLayout>
      <template #filters>
        <FilterToolbar>
          <div class="grid gap-4 xl:grid-cols-[180px_minmax(0,1fr)_180px_180px_auto_auto]">
            <BaseSelect v-model="scope">
              <option
                v-if="activeProjectId && canReadProjectOperations"
                value="project"
              >
                当前项目
              </option>
              <option
                v-if="canReadGlobalOperations"
                value="global"
              >
                全局
              </option>
            </BaseSelect>
            <BaseInput
              v-model="kindInput"
              placeholder="按 kind 筛选"
            />
            <BaseSelect v-model="statusInput">
              <option value="">
                全部状态
              </option>
              <option value="submitted">
                submitted
              </option>
              <option value="running">
                running
              </option>
              <option value="succeeded">
                succeeded
              </option>
              <option value="failed">
                failed
              </option>
              <option value="cancelled">
                cancelled
              </option>
            </BaseSelect>
            <BaseInput
              v-model="requestedByInput"
              placeholder="按提交人筛选"
            />
            <BaseSelect v-model="archiveScope">
              <option value="exclude">
                仅未归档
              </option>
              <option value="include">
                包含已归档
              </option>
              <option value="only">
                仅已归档
              </option>
            </BaseSelect>
            <BaseButton
              variant="secondary"
              @click="resetFilters"
            >
              重置
            </BaseButton>
            <BaseButton @click="applyFilters">
              应用筛选
            </BaseButton>
          </div>
        </FilterToolbar>
      </template>

      <template #actions>
        <BulkActionsBar
          :selected-count="selectedOperations.length"
          :summary="bulkActionSummary"
          :actions="bulkActions"
          @clear="clearSelection"
        />
      </template>

      <template #table>
        <DataTable
          :columns="columns"
          :rows="rows"
          :loading="loading"
          selectable
          :selected-row-keys="selectedOperationIds"
          row-key="id"
          sort-storage-key="pw:operations:sort"
          column-storage-key="pw:operations:columns"
          empty-title="没有操作记录"
          empty-description="当前筛选范围下还没有操作记录。可以先去 Runtime、Assistants 或 Testcase 触发一次真实异步动作。"
          empty-icon="activity"
          @update:selected-row-keys="updateSelectedOperationIds"
        >
          <template #cell-created_at="{ row }">
            <span class="text-sm text-gray-500 dark:text-dark-300">
              {{ formatDateTime(operationFromRow(row).created_at) }}
            </span>
          </template>

          <template #cell-kind="{ row }">
            <div class="min-w-0">
              <div class="truncate font-semibold text-gray-900 dark:text-white">
                {{ operationFromRow(row).kind }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ shortId(operationFromRow(row).id) }}
              </div>
              <div
                v-if="operationFromRow(row).archived_at"
                class="mt-1 text-[11px] uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500"
              >
                archived
              </div>
            </div>
          </template>

          <template #cell-status="{ row }">
            <StatusPill :tone="statusTone(operationFromRow(row).status)">
              {{ operationFromRow(row).status }}
            </StatusPill>
          </template>

          <template #cell-project_id="{ row }">
            <div class="min-w-0">
              <div class="text-sm font-medium text-gray-900 dark:text-white">
                {{ shortId(operationFromRow(row).project_id) }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                by {{ operationFromRow(row).requested_by || '--' }}
              </div>
            </div>
          </template>

          <template #cell-updated_at="{ row }">
            <span class="text-sm text-gray-500 dark:text-dark-300">
              {{ formatDateTime(operationFromRow(row).updated_at) }}
            </span>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="operationActions(operationFromRow(row))" />
          </template>
        </DataTable>
      </template>

      <template
        v-if="pagination.total.value > 0"
        #footer
      >
        <PaginationBar
          :page="pagination.page.value"
          :page-size="pagination.pageSize.value"
          :total="pagination.total.value"
          :disabled="loading"
          @update:page="pagination.setPage"
          @update:page-size="pagination.setPageSize"
        />
      </template>
    </TablePageLayout>

    <BaseDialog
      :show="detailDialogOpen"
      :title="selectedOperation ? `操作详情 · ${shortId(selectedOperation.id)}` : '操作详情'"
      width="full"
      @close="closeOperationDetail"
    >
      <div
        v-if="detailLoading"
        class="rounded-2xl border border-dashed border-gray-200 px-6 py-12 text-center text-sm text-gray-500 dark:border-dark-700 dark:text-dark-300"
      >
        正在加载操作详情...
      </div>

      <div
        v-else-if="selectedOperation"
        class="space-y-5"
      >
        <div class="grid gap-4 lg:grid-cols-2">
          <div class="rounded-2xl border border-gray-100 bg-gray-50/80 p-4 dark:border-dark-800 dark:bg-dark-900/80">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              基础信息
            </div>
            <div class="mt-3 space-y-2 text-sm text-gray-600 dark:text-dark-300">
              <div><span class="font-semibold text-gray-900 dark:text-white">Kind:</span> {{ selectedOperation.kind }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Status:</span> {{ selectedOperation.status }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Requested By:</span> {{ selectedOperation.requested_by }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Project:</span> {{ shortId(selectedOperation.project_id) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Created:</span> {{ formatDateTime(selectedOperation.created_at) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Updated:</span> {{ formatDateTime(selectedOperation.updated_at) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Started:</span> {{ formatDateTime(selectedOperation.started_at) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Finished:</span> {{ formatDateTime(selectedOperation.finished_at) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Archived:</span> {{ formatDateTime(selectedOperation.archived_at) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Artifact Expires:</span> {{ formatDateTime(artifactExpiresAt(selectedOperation)) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Artifact Backend:</span> {{ artifactStorageBackend(selectedOperation) || '--' }}</div>
            </div>
          </div>

          <div class="rounded-2xl border border-gray-100 bg-gray-50/80 p-4 dark:border-dark-800 dark:bg-dark-900/80">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              快捷动作
            </div>
            <div class="mt-4 flex flex-wrap gap-3">
              <BaseButton
                variant="secondary"
                @click="jumpToAudit(selectedOperation)"
              >
                <BaseIcon
                  name="audit"
                  size="sm"
                />
                查看审计
              </BaseButton>
              <BaseButton
                v-if="hasArtifact(selectedOperation)"
                variant="secondary"
                @click="handleDownloadArtifact(selectedOperation)"
              >
                <BaseIcon
                  name="download"
                  size="sm"
                />
                下载结果
              </BaseButton>
              <span
                v-else-if="artifactExpiresAt(selectedOperation)"
                class="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200"
              >
                产物已过期
              </span>
              <router-link
                v-if="inferResourceRoute(selectedOperation)"
                class="pw-btn pw-btn-ghost"
                :to="inferResourceRoute(selectedOperation)"
              >
                <BaseIcon
                  name="overview"
                  size="sm"
                />
                打开相关页面
              </router-link>
              <BaseButton
                v-if="!isTerminal(selectedOperation.status)"
                variant="danger"
                :disabled="cancellingId === selectedOperation.id || !canMutateOperation(selectedOperation)"
                @click="handleCancel(selectedOperation)"
              >
                <BaseIcon
                  name="x"
                  size="sm"
                />
                {{ cancellingId === selectedOperation.id ? '取消中...' : '取消操作' }}
              </BaseButton>
            </div>
          </div>
        </div>

        <div
          v-if="formatJson(selectedOperation.input_payload)"
          class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-dark-800 dark:bg-dark-950"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            输入载荷
          </div>
          <pre class="mt-3 overflow-x-auto rounded-2xl bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ formatJson(selectedOperation.input_payload) }}</pre>
        </div>

        <div
          v-if="formatJson(selectedOperation.result_payload)"
          class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-dark-800 dark:bg-dark-950"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            结果载荷
          </div>
          <pre class="mt-3 overflow-x-auto rounded-2xl bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ formatJson(selectedOperation.result_payload) }}</pre>
        </div>

        <div
          v-if="formatJson(selectedOperation.error_payload)"
          class="rounded-2xl border border-rose-100 bg-rose-50/80 p-4 dark:border-rose-900/30 dark:bg-rose-950/20"
        >
          <div class="text-sm font-semibold text-rose-700 dark:text-rose-300">
            错误载荷
          </div>
          <pre class="mt-3 overflow-x-auto rounded-2xl bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ formatJson(selectedOperation.error_payload) }}</pre>
        </div>

        <div
          v-if="formatJson(selectedOperation.metadata)"
          class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-dark-800 dark:bg-dark-950"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            元数据
          </div>
          <pre class="mt-3 overflow-x-auto rounded-2xl bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ formatJson(selectedOperation.metadata) }}</pre>
        </div>
      </div>
    </BaseDialog>
  </section>
</template>
