<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import { usePagination } from '@/composables/usePagination'
import ActionMenu from '@/components/platform/ActionMenu.vue'
import DataTable from '@/components/platform/DataTable.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { ActionMenuItem, DataTableColumn } from '@/components/platform/data-table'
import {
  listRuntimeGraphPolicies,
  listRuntimeModelPolicies,
  listRuntimeToolPolicies,
  updateRuntimeGraphPolicy,
  updateRuntimeModelPolicy,
  updateRuntimeToolPolicy
} from '@/services/runtime-policies/runtime-policies.service'
import {
  submitRuntimeRefreshOperation,
  waitForRuntimeRefreshOperation
} from '@/services/runtime/runtime.service'
import { useUiStore } from '@/stores/ui'
import type {
  RuntimeGraphPolicyItem,
  RuntimeModelPolicyItem,
  RuntimeToolPolicyItem
} from '@/types/management'
import { formatDateTime, shortId } from '@/utils/format'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

type PolicyTab = 'models' | 'tools' | 'graphs'

type EditingDraft = {
  is_enabled: boolean
  is_default_for_project: boolean
  display_order: string
  temperature_default: string
  note: string
}

const { activeProjectId, activeProject } = useWorkspaceProjectContext()
const uiStore = useUiStore()
const authorization = useAuthorization()
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:runtime-policies:page-size'
})

const activeTab = ref<PolicyTab>('models')
const loading = ref(false)
const refreshing = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const queryInput = ref('')
const query = ref('')

const modelItems = ref<RuntimeModelPolicyItem[]>([])
const toolItems = ref<RuntimeToolPolicyItem[]>([])
const graphItems = ref<RuntimeGraphPolicyItem[]>([])

const editDialogOpen = ref(false)
const editingTab = ref<PolicyTab>('models')
const editingCatalogId = ref('')
const editingTitle = ref('')
const draft = ref<EditingDraft>({
  is_enabled: true,
  is_default_for_project: false,
  display_order: '',
  temperature_default: '',
  note: ''
})

const currentProjectId = computed(() => activeProjectId.value)
const currentProjectName = computed(() => activeProject.value?.name || '未选择项目')
const canManageRuntimePolicies = computed(() => authorization.currentProjectCan('project.runtime.write'))
const canRefreshRuntimeCatalog = computed(() =>
  authorization.can('platform.catalog.refresh') || authorization.currentProjectCan('project.runtime.write')
)
const activeRefreshResource = computed<'models' | 'tools' | 'graphs'>(() => activeTab.value)
const activeRefreshLabel = computed(() => {
  if (activeTab.value === 'tools') {
    return '运行策略'
  }
  if (activeTab.value === 'graphs') {
    return '图目录'
  }
  return '模型目录'
})

const currentItems = computed(() => {
  if (activeTab.value === 'tools') {
    return toolItems.value
  }
  if (activeTab.value === 'graphs') {
    return graphItems.value
  }
  return modelItems.value
})

const filteredItems = computed(() => {
  const normalized = query.value.trim().toLowerCase()
  if (!normalized) {
    return currentItems.value
  }

  return currentItems.value.filter((item) => {
    if ('model_id' in item) {
      return (
        item.model_id.toLowerCase().includes(normalized) ||
        item.display_name.toLowerCase().includes(normalized) ||
        (item.policy.note || '').toLowerCase().includes(normalized)
      )
    }

    if ('tool_key' in item) {
      return (
        item.tool_key.toLowerCase().includes(normalized) ||
        item.name.toLowerCase().includes(normalized) ||
        (item.source || '').toLowerCase().includes(normalized) ||
        (item.policy.note || '').toLowerCase().includes(normalized)
      )
    }

    return (
      item.graph_id.toLowerCase().includes(normalized) ||
      item.display_name.toLowerCase().includes(normalized) ||
      (item.description || '').toLowerCase().includes(normalized) ||
      (item.policy.note || '').toLowerCase().includes(normalized)
    )
  })
})

const pagedItems = computed(() => {
  return filteredItems.value.slice(pagination.offset.value, pagination.offset.value + pagination.pageSize.value)
})

const tableRows = computed(() => pagedItems.value as unknown as Record<string, unknown>[])

const disabledCount = computed(() => currentItems.value.filter((item) => !item.policy.is_enabled).length)
const overriddenCount = computed(() => {
  if (activeTab.value === 'models') {
    return modelItems.value.filter((item) => item.policy.is_default_for_project).length
  }

  return activeTab.value === 'tools'
    ? toolItems.value.filter((item) => item.policy.display_order != null).length
    : graphItems.value.filter((item) => item.policy.display_order != null).length
})
const updatedAt = computed(() => {
  const candidates = currentItems.value
    .map((item) => item.policy.updated_at || null)
    .filter((item): item is string => Boolean(item))
    .sort()
  return candidates.length > 0 ? candidates[candidates.length - 1] : null
})

const stats = computed(() => [
  {
    label: '当前项目',
    value: currentProjectName.value,
    hint: '策略覆盖按项目生效，不会污染全局目录。',
    icon: 'project',
    tone: 'primary'
  },
  {
    label: '当前分类',
    value: currentItems.value.length,
    hint:
      activeTab.value === 'models'
        ? '模型策略项总数'
        : activeTab.value === 'tools'
          ? '工具策略项总数'
          : '图策略项总数',
    icon: activeTab.value === 'models' ? 'runtime' : activeTab.value === 'tools' ? 'activity' : 'graph',
    tone: 'success'
  },
  {
    label: '禁用项',
    value: disabledCount.value,
    hint: '禁用后该项目下不再默认展示或使用该项。',
    icon: 'shield',
    tone: disabledCount.value > 0 ? 'warning' : 'success'
  },
  {
    label: activeTab.value === 'models' ? '默认模型覆盖' : '排序覆盖',
    value: overriddenCount.value,
    hint:
      activeTab.value === 'models'
        ? '项目级默认模型指定次数'
        : '当前显式设置 display order 的数量',
    icon: 'overview',
    tone: 'danger'
  }
])

const columns = computed<DataTableColumn[]>(() => {
  if (activeTab.value === 'models') {
    return [
      {
        key: 'display_name',
        label: 'Model',
        sortable: true,
        alwaysVisible: true,
        sortValue: (row) => row.display_name || row.model_id || ''
      },
      {
        key: 'policy_state',
        label: '策略',
        sortable: true,
        sortValue: (row) => ((row.policy as { is_enabled?: boolean } | undefined)?.is_enabled ? 1 : 0)
      },
      {
        key: 'default_state',
        label: '默认覆盖',
        sortable: true,
        sortValue: (row) =>
          ((row.policy as { is_default_for_project?: boolean } | undefined)?.is_default_for_project ? 1 : 0)
      },
      {
        key: 'temperature_default',
        label: '温度',
        sortable: true,
        sortValue: (row) =>
          (row.policy as { temperature_default?: number | null } | undefined)?.temperature_default ?? -1
      },
      {
        key: 'sync_status',
        label: '同步状态',
        sortable: true,
        sortValue: (row) => row.sync_status || ''
      }
    ]
  }

  if (activeTab.value === 'tools') {
    return [
      {
        key: 'name',
        label: 'Tool',
        sortable: true,
        alwaysVisible: true,
        sortValue: (row) => row.name || row.tool_key || ''
      },
      {
        key: 'source',
        label: 'Source',
        sortable: true,
        sortValue: (row) => row.source || ''
      },
      {
        key: 'policy_state',
        label: '策略',
        sortable: true,
        sortValue: (row) => ((row.policy as { is_enabled?: boolean } | undefined)?.is_enabled ? 1 : 0)
      },
      {
        key: 'display_order',
        label: '排序',
        sortable: true,
        sortValue: (row) => (row.policy as { display_order?: number | null } | undefined)?.display_order ?? -1
      },
      {
        key: 'sync_status',
        label: '同步状态',
        sortable: true,
        sortValue: (row) => row.sync_status || ''
      }
    ]
  }

  return [
    {
      key: 'display_name',
      label: 'Graph',
      sortable: true,
      alwaysVisible: true,
      sortValue: (row) => row.display_name || row.graph_id || ''
    },
    {
      key: 'source_type',
      label: 'Source Type',
      sortable: true,
      sortValue: (row) => row.source_type || ''
    },
    {
      key: 'policy_state',
      label: '策略',
      sortable: true,
      sortValue: (row) => ((row.policy as { is_enabled?: boolean } | undefined)?.is_enabled ? 1 : 0)
    },
    {
      key: 'display_order',
      label: '排序',
      sortable: true,
      sortValue: (row) => (row.policy as { display_order?: number | null } | undefined)?.display_order ?? -1
    },
    {
      key: 'sync_status',
      label: '同步状态',
      sortable: true,
      sortValue: (row) => row.sync_status || ''
    }
  ]
})

function isSyncTone(status: string): 'neutral' | 'success' | 'warning' | 'danger' {
  if (status === 'ready' || status === 'synced') {
    return 'success'
  }
  if (status === 'failed' || status === 'error') {
    return 'danger'
  }
  if (status === 'pending') {
    return 'warning'
  }
  return 'neutral'
}

function openEditor(item: RuntimeModelPolicyItem | RuntimeToolPolicyItem | RuntimeGraphPolicyItem, tab: PolicyTab) {
  if (!canManageRuntimePolicies.value) {
    error.value = '当前账号没有运行策略写权限'
    return
  }

  editingTab.value = tab
  editingCatalogId.value = item.catalog_id
  editingTitle.value =
    'model_id' in item ? item.display_name || item.model_id : 'tool_key' in item ? item.name || item.tool_key : item.display_name || item.graph_id
  draft.value = {
    is_enabled: item.policy.is_enabled,
    is_default_for_project: 'model_id' in item ? item.policy.is_default_for_project : false,
    display_order:
      'model_id' in item
        ? ''
        : item.policy.display_order == null
          ? ''
          : String(item.policy.display_order),
    temperature_default:
      'model_id' in item
        ? item.policy.temperature_default == null
          ? ''
          : String(item.policy.temperature_default)
        : '',
    note: item.policy.note || ''
  }
  editDialogOpen.value = true
}

function actionItems(item: RuntimeModelPolicyItem | RuntimeToolPolicyItem | RuntimeGraphPolicyItem, tab: PolicyTab): ActionMenuItem[] {
  return [
    {
      key: 'edit',
      label: '编辑策略',
      icon: 'shield',
      disabled: !canManageRuntimePolicies.value,
      onSelect: () => openEditor(item, tab)
    }
  ]
}

async function loadPolicies() {
  const projectId = currentProjectId.value
  if (!projectId) {
    modelItems.value = []
    toolItems.value = []
    graphItems.value = []
    pagination.setTotal(0)
    return
  }

  loading.value = true
  error.value = ''

  const results = await Promise.allSettled([
    listRuntimeModelPolicies(projectId),
    listRuntimeToolPolicies(projectId),
    listRuntimeGraphPolicies(projectId)
  ])

  const [modelsResult, toolsResult, graphsResult] = results
  const failedSections: string[] = []

  if (modelsResult.status === 'fulfilled') {
    modelItems.value = modelsResult.value.items
  } else {
    modelItems.value = []
    failedSections.push('models')
  }

  if (toolsResult.status === 'fulfilled') {
    toolItems.value = toolsResult.value.items
  } else {
    toolItems.value = []
    failedSections.push('tools')
  }

  if (graphsResult.status === 'fulfilled') {
    graphItems.value = graphsResult.value.items
  } else {
    graphItems.value = []
    failedSections.push('graphs')
  }

  if (failedSections.length > 0) {
    error.value = `部分策略列表加载失败：${failedSections.join('、')}。请确认当前账号具备项目访问权限，并检查 platform-api 日志。`
  }

  loading.value = false
}

async function handleRefreshCatalog() {
  const projectId = currentProjectId.value
  if (!projectId) {
    error.value = '当前没有项目上下文，无法刷新目录'
    return
  }
  if (!canRefreshRuntimeCatalog.value) {
    error.value = '当前账号没有刷新 Runtime 目录的权限'
    return
  }

  refreshing.value = true
  error.value = ''
  notice.value = ''

  try {
    const operation = await submitRuntimeRefreshOperation(activeRefreshResource.value, projectId)
    notice.value = `${activeRefreshLabel.value}刷新任务已提交，任务号 ${shortId(operation.id)}`
    const finalOperation = await waitForRuntimeRefreshOperation(operation.id, {
      timeoutMs: 90000
    })
    if (finalOperation.status !== 'succeeded') {
      throw new Error(
        (finalOperation.error_payload?.message as string | undefined) || `${activeRefreshLabel.value}刷新未成功完成`
      )
    }

    const count = Number(finalOperation.result_payload?.count || 0)
    notice.value = `${activeRefreshLabel.value}已刷新，当前同步 ${count} 条记录`
    await loadPolicies()
    uiStore.pushToast({
      type: 'success',
      title: `${activeRefreshLabel.value}已刷新`,
      message: notice.value
    })
  } catch (refreshError) {
    error.value = resolvePlatformHttpErrorMessage(refreshError, `${activeRefreshLabel.value}刷新失败`, 'Runtime 目录')
  } finally {
    refreshing.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  if (pagination.page.value === 1) {
    return
  }
  pagination.resetPage()
}

function resetFilters() {
  queryInput.value = ''
  query.value = ''
  if (pagination.page.value === 1) {
    return
  }
  pagination.resetPage()
}

function switchTab(tab: PolicyTab) {
  if (activeTab.value === tab) {
    return
  }
  activeTab.value = tab
  queryInput.value = ''
  query.value = ''
  pagination.resetPage()
}

async function savePolicy() {
  const projectId = currentProjectId.value
  if (!projectId || !editingCatalogId.value) {
    return
  }
  if (!canManageRuntimePolicies.value) {
    error.value = '当前账号没有运行策略写权限'
    return
  }

  saving.value = true
  error.value = ''
  notice.value = ''

  try {
    if (editingTab.value === 'models') {
      await updateRuntimeModelPolicy(projectId, editingCatalogId.value, {
        is_enabled: draft.value.is_enabled,
        is_default_for_project: draft.value.is_default_for_project,
        temperature_default: draft.value.temperature_default.trim()
          ? Number(draft.value.temperature_default)
          : null,
        note: draft.value.note.trim() || null
      })
    } else if (editingTab.value === 'tools') {
      await updateRuntimeToolPolicy(projectId, editingCatalogId.value, {
        is_enabled: draft.value.is_enabled,
        display_order: draft.value.display_order.trim() ? Number(draft.value.display_order) : null,
        note: draft.value.note.trim() || null
      })
    } else {
      await updateRuntimeGraphPolicy(projectId, editingCatalogId.value, {
        is_enabled: draft.value.is_enabled,
        display_order: draft.value.display_order.trim() ? Number(draft.value.display_order) : null,
        note: draft.value.note.trim() || null
      })
    }

    notice.value = `${editingTitle.value} 的策略已更新`
    editDialogOpen.value = false
    await loadPolicies()
    uiStore.pushToast({
      type: 'success',
      title: '策略已保存',
      message: notice.value
    })
  } catch (saveError) {
    error.value = resolvePlatformHttpErrorMessage(saveError, '策略保存失败', '运行策略')
  } finally {
    saving.value = false
  }
}

watch(
  () => filteredItems.value.length,
  (count) => {
    pagination.setTotal(count)
  },
  { immediate: true }
)

watch(currentProjectId, () => {
  void loadPolicies()
})

onMounted(() => {
  void loadPolicies()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Runtime"
      title="运行策略覆盖"
      description="项目级 runtime overlay 在这里集中治理。模型默认项、工具启停、图排序都不再散落在各个页面里临时处理。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="refreshing || !currentProjectId || !canRefreshRuntimeCatalog"
          @click="handleRefreshCatalog"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          {{ refreshing ? `${activeRefreshLabel}刷新中...` : `刷新${activeRefreshLabel}` }}
        </BaseButton>
        <router-link
          class="pw-btn pw-btn-ghost"
          to="/workspace/operations"
        >
          <BaseIcon
            name="activity"
            size="sm"
          />
          查看 Operations
        </router-link>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="运行策略存在缺口"
      :description="error"
      variant="danger"
    />
    <StateBanner
      v-else-if="currentProjectId && !canManageRuntimePolicies"
      title="当前账号只读"
      description="你可以查看项目级运行策略，但编辑动作已经收口到 project.runtime.write 权限。"
      variant="info"
    />
    <StateBanner
      v-else-if="notice"
      title="策略更新完成"
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

    <EmptyState
      v-if="!currentProjectId"
      title="还没有项目上下文"
      description="先在顶部切一个项目，再配置这个项目的模型、工具和图策略覆盖。"
      icon="project"
    />

    <template v-else>
      <div class="flex flex-wrap gap-3">
        <button
          type="button"
          class="rounded-full border px-4 py-2 text-sm font-semibold transition"
          :class="activeTab === 'models'
            ? 'border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-800 dark:bg-primary-950/30 dark:text-primary-300'
            : 'border-gray-200 bg-white text-gray-600 hover:border-primary-200 hover:text-primary-700 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300'"
          @click="switchTab('models')"
        >
          模型策略
        </button>
        <button
          type="button"
          class="rounded-full border px-4 py-2 text-sm font-semibold transition"
          :class="activeTab === 'tools'
            ? 'border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-800 dark:bg-primary-950/30 dark:text-primary-300'
            : 'border-gray-200 bg-white text-gray-600 hover:border-primary-200 hover:text-primary-700 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300'"
          @click="switchTab('tools')"
        >
          工具策略
        </button>
        <button
          type="button"
          class="rounded-full border px-4 py-2 text-sm font-semibold transition"
          :class="activeTab === 'graphs'
            ? 'border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-800 dark:bg-primary-950/30 dark:text-primary-300'
            : 'border-gray-200 bg-white text-gray-600 hover:border-primary-200 hover:text-primary-700 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300'"
          @click="switchTab('graphs')"
        >
          图策略
        </button>
      </div>

      <TablePageLayout>
        <template #filters>
          <FilterToolbar>
            <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_auto]">
              <SearchInput
                v-model="queryInput"
                icon="search"
                :placeholder="activeTab === 'models' ? '按模型名 / Model ID / 备注筛选' : activeTab === 'tools' ? '按 Tool / Source / 备注筛选' : '按 Graph / 描述 / 备注筛选'"
              />
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

        <template #table>
          <DataTable
            :columns="columns"
            :rows="tableRows"
            :loading="loading"
            row-key="catalog_id"
            sort-storage-key="pw:runtime-policies:sort"
            column-storage-key="pw:runtime-policies:columns"
            empty-title="没有策略数据"
            empty-description="当前项目下还没有加载到对应的目录策略，先确认 runtime 目录已经同步。"
            empty-icon="shield"
          >
            <template #cell-display_name="{ row }">
              <div
                v-if="activeTab === 'models'"
                class="min-w-0"
              >
                <div class="truncate font-semibold text-gray-900 dark:text-white">
                  {{ (row as RuntimeModelPolicyItem).display_name }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                  {{ (row as RuntimeModelPolicyItem).model_id }}
                </div>
              </div>
              <div
                v-else-if="activeTab === 'graphs'"
                class="min-w-0"
              >
                <div class="truncate font-semibold text-gray-900 dark:text-white">
                  {{ (row as RuntimeGraphPolicyItem).display_name }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                  {{ (row as RuntimeGraphPolicyItem).graph_id }}
                </div>
              </div>
            </template>

            <template #cell-policy_state="{ row }">
              <StatusPill
                :tone="(row as RuntimeModelPolicyItem | RuntimeToolPolicyItem | RuntimeGraphPolicyItem).policy.is_enabled ? 'success' : 'warning'"
              >
                {{ (row as RuntimeModelPolicyItem | RuntimeToolPolicyItem | RuntimeGraphPolicyItem).policy.is_enabled ? 'enabled' : 'disabled' }}
              </StatusPill>
            </template>

            <template
              v-if="activeTab === 'models'"
              #cell-default_state="{ row }"
            >
              <StatusPill :tone="(row as RuntimeModelPolicyItem).policy.is_default_for_project ? 'info' : 'neutral'">
                {{ (row as RuntimeModelPolicyItem).policy.is_default_for_project ? 'project default' : 'follow runtime' }}
              </StatusPill>
            </template>

            <template
              v-if="activeTab === 'models'"
              #cell-temperature_default="{ row }"
            >
              <span class="text-sm text-gray-500 dark:text-dark-300">
                {{ (row as RuntimeModelPolicyItem).policy.temperature_default ?? '--' }}
              </span>
            </template>

            <template
              v-if="activeTab === 'tools'"
              #cell-name="{ row }"
            >
              <div class="min-w-0">
                <div class="truncate font-semibold text-gray-900 dark:text-white">
                  {{ (row as RuntimeToolPolicyItem).name }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                  {{ (row as RuntimeToolPolicyItem).tool_key }}
                </div>
              </div>
            </template>

            <template
              v-if="activeTab === 'tools'"
              #cell-source="{ row }"
            >
              <span class="text-sm text-gray-500 dark:text-dark-300">
                {{ (row as RuntimeToolPolicyItem).source || '--' }}
              </span>
            </template>

            <template
              v-if="activeTab !== 'models'"
              #cell-display_order="{ row }"
            >
              <span class="text-sm text-gray-500 dark:text-dark-300">
                {{ (row as RuntimeToolPolicyItem | RuntimeGraphPolicyItem).policy.display_order ?? '--' }}
              </span>
            </template>

            <template
              v-if="activeTab === 'graphs'"
              #cell-source_type="{ row }"
            >
              <span class="text-sm text-gray-500 dark:text-dark-300">
                {{ (row as RuntimeGraphPolicyItem).source_type }}
              </span>
            </template>

            <template #cell-sync_status="{ row }">
              <div class="min-w-0">
                <StatusPill :tone="isSyncTone(String(row.sync_status || ''))">
                  {{ row.sync_status || 'unknown' }}
                </StatusPill>
                <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
                  {{ formatDateTime((row as RuntimeModelPolicyItem | RuntimeToolPolicyItem | RuntimeGraphPolicyItem).last_synced_at || updatedAt) }}
                </div>
              </div>
            </template>

            <template #cell-actions="{ row }">
              <ActionMenu
                :items="actionItems(
                  row as RuntimeModelPolicyItem | RuntimeToolPolicyItem | RuntimeGraphPolicyItem,
                  activeTab
                )"
              />
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
    </template>

    <BaseDialog
      :show="editDialogOpen"
      :title="`编辑策略 · ${editingTitle || shortId(editingCatalogId)}`"
      width="wide"
      @close="editDialogOpen = false"
    >
      <div class="space-y-5">
        <div class="rounded-2xl border border-gray-100 bg-gray-50/80 p-4 text-sm text-gray-600 dark:border-dark-800 dark:bg-dark-900/80 dark:text-dark-300">
          <div class="font-semibold text-gray-900 dark:text-white">
            {{ editingTitle }}
          </div>
          <div class="mt-1">
            Catalog ID: {{ editingCatalogId }}
          </div>
        </div>

        <label class="flex items-center gap-3 rounded-2xl border border-gray-100 px-4 py-3 text-sm dark:border-dark-800">
          <input
            v-model="draft.is_enabled"
            type="checkbox"
            class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          >
          <span class="font-medium text-gray-800 dark:text-white">项目内启用该项</span>
        </label>

        <label
          v-if="editingTab === 'models'"
          class="flex items-center gap-3 rounded-2xl border border-gray-100 px-4 py-3 text-sm dark:border-dark-800"
        >
          <input
            v-model="draft.is_default_for_project"
            type="checkbox"
            class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          >
          <span class="font-medium text-gray-800 dark:text-white">设为项目默认模型</span>
        </label>

        <div
          v-if="editingTab !== 'models'"
          class="grid gap-4 md:grid-cols-2"
        >
          <label class="block">
            <span class="pw-input-label">Display Order</span>
            <input
              v-model="draft.display_order"
              type="number"
              min="0"
              class="pw-input"
              placeholder="留空表示不覆盖"
            >
          </label>
        </div>

        <div
          v-if="editingTab === 'models'"
          class="grid gap-4 md:grid-cols-2"
        >
          <label class="block">
            <span class="pw-input-label">Temperature Default</span>
            <input
              v-model="draft.temperature_default"
              type="number"
              min="0"
              max="2"
              step="0.1"
              class="pw-input"
              placeholder="留空表示跟随调用侧"
            >
          </label>
        </div>

        <label class="block">
          <span class="pw-input-label">备注</span>
          <textarea
            v-model="draft.note"
            rows="5"
            class="pw-input min-h-[132px] resize-y"
            placeholder="说明为什么对这个项目做覆盖，别让后面的人一脸懵。"
          />
        </label>
      </div>

      <template #footer>
        <div class="flex items-center gap-3">
          <BaseButton
            variant="secondary"
            @click="editDialogOpen = false"
          >
            取消
          </BaseButton>
          <BaseButton
            :disabled="saving || !canManageRuntimePolicies"
            @click="savePolicy"
          >
            {{ canManageRuntimePolicies ? (saving ? '保存中...' : '保存策略') : '当前账号只读' }}
          </BaseButton>
        </div>
      </template>
    </BaseDialog>
  </section>
</template>
