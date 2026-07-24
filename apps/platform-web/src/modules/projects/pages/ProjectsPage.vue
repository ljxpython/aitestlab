<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import { usePagination } from '@/composables/usePagination'
import ActionMenu from '@/components/platform/ActionMenu.vue'
import BulkActionsBar from '@/components/platform/BulkActionsBar.vue'
import DataTable from '@/components/platform/DataTable.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import GuidePanel from '@/components/platform/GuidePanel.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { ActionMenuItem, BulkActionItem, DataTableColumn } from '@/components/platform/data-table'
import { deleteProject, listProjectsPage } from '@/services/projects/projects.service'
import { useUiStore } from '@/stores/ui'
import type { ManagementProject } from '@/types/management'
import { downloadBlob } from '@/utils/browser-download'
import { copyText } from '@/utils/clipboard'
import { shortId } from '@/utils/format'

const router = useRouter()
const { workspaceStore, activeProjectId, setActiveProjectId } = useWorkspaceProjectContext()
const uiStore = useUiStore()
const authorization = useAuthorization()

const queryInput = ref('')
const query = ref('')
const loading = ref(false)
const deletingProjectId = ref('')
const error = ref('')
const items = ref<ManagementProject[]>([])
const selectedProjectIds = ref<string[]>([])
const pendingDeleteProject = ref<ManagementProject | null>(null)
const projectRows = computed(() => items.value as unknown as Record<string, unknown>[])
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:projects:page-size'
})
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'name',
    label: '项目',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.name
  },
  {
    key: 'description',
    label: '描述',
    sortable: true,
    sortValue: (row) => row.description || '',
    cellClass: 'max-w-[420px]'
  },
  {
    key: 'status',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.status
  },
  {
    key: 'id',
    label: 'ID',
    sortable: true,
    sortValue: (row) => row.id
  }
])

function projectFromRow(row: Record<string, unknown>) {
  return row as ManagementProject
}

const activeCount = computed(() => items.value.filter((item) => item.status === 'active').length)
const selectedProjects = computed(() =>
  items.value.filter((item) => selectedProjectIds.value.includes(item.id))
)
const stats = computed(() => [
  {
    label: '当前结果',
    value: items.value.length,
    hint: query.value ? `按关键词“${query.value}”筛选` : '展示最近返回的项目列表',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '项目总量',
    value: pagination.total.value,
    hint: '来自管理端项目分页接口',
    icon: 'overview',
    tone: 'success'
  },
  {
    label: '活跃项目',
    value: activeCount.value,
    hint: '当前结果集中状态为 active 的项目',
    icon: 'activity',
    tone: 'warning'
  }
])

const bulkActionSummary = computed(() => {
  const names = selectedProjects.value.slice(0, 3).map((item) => item.name)
  if (!names.length) {
    return ''
  }

  const suffix =
    selectedProjects.value.length > names.length
      ? ` 等 ${selectedProjects.value.length} 个项目`
      : ` 共 ${selectedProjects.value.length} 个项目`

  return `${names.join('、')}${suffix}`
})

async function loadProjects() {
  loading.value = true
  error.value = ''

  try {
    const payload = await listProjectsPage({
      limit: pagination.pageSize.value,
      offset: pagination.offset.value,
      query: query.value
    })

    items.value = payload.items
    pagination.setTotal(payload.total)
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value = loadError instanceof Error ? loadError.message : '项目列表加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  if (pagination.page.value === 1) {
    void loadProjects()
    return
  }

  pagination.resetPage()
}

function resetFilters() {
  queryInput.value = ''
  query.value = ''
  if (pagination.page.value === 1) {
    void loadProjects()
    return
  }

  pagination.resetPage()
}

async function handleCopyProjectId(project: ManagementProject) {
  const copied = await copyText(project.id)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制项目 ID' : '复制失败',
    message: copied ? shortId(project.id) : '当前环境不支持自动复制，请手动复制。'
  })
}

function openDeleteDialog(project: ManagementProject) {
  pendingDeleteProject.value = project
}

function closeDeleteDialog() {
  pendingDeleteProject.value = null
}

async function confirmDeleteProject() {
  const project = pendingDeleteProject.value
  if (!project) {
    return
  }

  deletingProjectId.value = project.id
  error.value = ''

  try {
    await deleteProject(project.id)
    if (activeProjectId.value === project.id) {
      setActiveProjectId('')
    }
    await workspaceStore.hydrateContext()
    await loadProjects()
    uiStore.pushToast({
      type: 'success',
      title: '项目已删除',
      message: project.name
    })
    closeDeleteDialog()
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : '项目删除失败'
  } finally {
    deletingProjectId.value = ''
  }
}

function handleFocusProject(project: ManagementProject) {
  setActiveProjectId(project.id)
  uiStore.pushToast({
    type: 'success',
    title: '已切换当前项目',
    message: `当前工作区已切换到 ${project.name}`
  })
}

function clearProjectSelection() {
  selectedProjectIds.value = []
}

function updateSelectedProjectIds(keys: Array<string | number>) {
  selectedProjectIds.value = keys.map(String)
}

async function handleCopySelectedProjectIds() {
  const content = selectedProjects.value.map((item) => item.id).join('\n')
  const copied = await copyText(content)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制所选项目 ID' : '复制失败',
    message: copied ? `${selectedProjects.value.length} 个项目 ID 已写入剪贴板。` : '当前环境不支持自动复制，请手动复制。'
  })
}

function handleExportProjectSummary() {
  const rows = selectedProjects.value.map((item) =>
    [item.id, item.name, item.status, item.description || ''].join('\t')
  )
  const content = ['id\tname\tstatus\tdescription', ...rows].join('\n')
  downloadBlob(
    new Blob([content], { type: 'text/tab-separated-values;charset=utf-8' }),
    `projects-summary-${new Date().toISOString().slice(0, 10)}.tsv`
  )
  uiStore.pushToast({
    type: 'success',
    title: '项目摘要已导出',
    message: `已导出 ${selectedProjects.value.length} 个项目的摘要文件。`
  })
}

function projectActions(project: ManagementProject): ActionMenuItem[] {
  const actions: ActionMenuItem[] = [
    {
      key: 'focus',
      label:
        activeProjectId.value === project.id ? '当前工作台项目' : '设为当前项目',
      icon: 'project',
      disabled: activeProjectId.value === project.id,
      onSelect: () => handleFocusProject(project)
    },
    {
      key: 'copy-id',
      label: '复制项目 ID',
      icon: 'copy',
      onSelect: () => handleCopyProjectId(project)
    },
    {
      key: 'detail',
      label: '项目详情',
      icon: 'eye',
      onSelect: () => void router.push(`/workspace/projects/${project.id}`)
    }
  ]

  if (authorization.can('platform.project.write')) {
    actions.push({
      key: 'delete',
      label: deletingProjectId.value === project.id ? '删除中...' : '删除项目',
      icon: 'trash',
      disabled: deletingProjectId.value === project.id,
      danger: true,
      onSelect: () => openDeleteDialog(project)
    })
  }

  return actions
}

const bulkActions = computed<BulkActionItem[]>(() => [
  {
    key: 'focus',
    label: '设为当前项目',
    icon: 'project',
    variant: 'secondary',
    disabled: selectedProjects.value.length !== 1,
    onSelect: () => handleFocusProject(selectedProjects.value[0] as ManagementProject)
  },
  {
    key: 'copy-ids',
    label: '复制项目 ID',
    icon: 'copy',
    variant: 'secondary',
    onSelect: handleCopySelectedProjectIds
  },
  {
    key: 'export',
    label: '导出摘要',
    icon: 'download',
    variant: 'primary',
    onSelect: handleExportProjectSummary
  }
  ])

watch(items, (nextItems) => {
  const validIds = new Set(nextItems.map((item) => item.id))
  selectedProjectIds.value = selectedProjectIds.value.filter((id) => validIds.has(id))
})

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadProjects()
})

onMounted(() => {
  void loadProjects()
})
</script>

<template>
  <section class="pw-page-shell h-full min-h-0 overflow-y-auto">
    <PageHeader
      eyebrow="Projects"
      title="项目管理"
      description="这里是正式项目治理入口，负责项目切换、列表检索、创建与删除闭环。"
    >
      <template #actions>
        <BaseButton
          :disabled="!authorization.can('platform.project.create')"
          @click="void router.push('/workspace/projects/new')"
        >
          <BaseIcon
            name="folder"
            size="sm"
          />
          新建项目
        </BaseButton>
        <BaseButton
          variant="secondary"
          @click="loadProjects"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="项目列表加载失败"
      :description="error"
      variant="danger"
    />

    <GuidePanel
      guide-id="projects-entry-guide"
      title="项目页怎么用最快"
      description="推荐这样用：1. 新建项目 2. 设为当前项目 3. 进入项目详情看成员和审计入口。后面 assistants、graphs、chat、testcase 都会跟着当前项目上下文走。"
      tone="info"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/projects/new')"
        >
          去新建项目
        </BaseButton>
      </template>
    </GuidePanel>

    <div class="grid gap-4 xl:grid-cols-3">
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
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_auto]">
            <SearchInput
              v-model="queryInput"
              placeholder="按项目名或描述搜索"
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

      <template #actions>
        <BulkActionsBar
          :selected-count="selectedProjects.length"
          :summary="bulkActionSummary"
          :actions="bulkActions"
          @clear="clearProjectSelection"
        />
      </template>

      <template #table>
        <DataTable
          :columns="columns"
          :rows="projectRows"
          :loading="loading"
          selectable
          :selected-row-keys="selectedProjectIds"
          row-key="id"
          sort-storage-key="pw:projects:sort"
          column-storage-key="pw:projects:columns"
          empty-title="没有找到项目"
          empty-description="当前筛选条件下没有项目数据。后续创建、详情和成员管理会在这张列表页母版上继续展开。"
          empty-icon="folder"
          @update:selected-row-keys="updateSelectedProjectIds"
        >
          <template #cell-name="{ row }">
            <div
              v-if="projectFromRow(row)"
              class="flex items-start gap-3"
            >
              <div class="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-300">
                <BaseIcon
                  name="folder"
                  size="sm"
                />
              </div>
              <div>
                <div class="text-sm font-semibold text-gray-900 dark:text-white">
                  {{ projectFromRow(row).name }}
                </div>
                <div
                  v-if="activeProjectId === projectFromRow(row).id"
                  class="mt-1 text-xs uppercase tracking-[0.14em] text-primary-600 dark:text-primary-300"
                >
                  当前工作台项目
                </div>
              </div>
            </div>
          </template>

          <template #cell-description="{ row }">
            <div class="leading-6 text-gray-500 dark:text-dark-300">
              {{ projectFromRow(row).description || '暂无描述' }}
            </div>
          </template>

          <template #cell-status="{ row }">
            <StatusPill :tone="projectFromRow(row).status === 'active' ? 'success' : 'neutral'">
              {{ projectFromRow(row).status }}
            </StatusPill>
          </template>

          <template #cell-id="{ row }">
            <span class="text-gray-400 dark:text-dark-400">
              {{ shortId(projectFromRow(row).id) }}
            </span>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="projectActions(projectFromRow(row))" />
          </template>
        </DataTable>
      </template>

      <template
        v-if="pagination.total.value > 0"
        #footer
      >
        <PaginationBar
          :total="pagination.total.value"
          :page="pagination.page.value"
          :page-size="pagination.pageSize.value"
          :disabled="loading"
          @update:page="pagination.setPage"
          @update:page-size="pagination.setPageSize"
        />
      </template>
    </TablePageLayout>

    <ConfirmDialog
      :show="Boolean(pendingDeleteProject)"
      title="删除项目"
      :message="pendingDeleteProject
        ? `删除后项目 ${pendingDeleteProject.name} 将进入删除态，项目成员与治理入口也会一起失效。确定继续吗？`
        : '删除后项目将进入删除态。'"
      confirm-text="确认删除"
      cancel-text="取消"
      danger
      @confirm="confirmDeleteProject"
      @cancel="closeDeleteDialog"
    />
  </section>
</template>
