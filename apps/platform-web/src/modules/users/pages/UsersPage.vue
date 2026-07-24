<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import BaseSelect from '@/components/base/BaseSelect.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import { usePagination } from '@/composables/usePagination'
import ActionMenu from '@/components/platform/ActionMenu.vue'
import BulkActionsBar from '@/components/platform/BulkActionsBar.vue'
import DataTable from '@/components/platform/DataTable.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { ActionMenuItem, BulkActionItem, DataTableColumn } from '@/components/platform/data-table'
import { describePlatformRole, primaryPlatformRole } from '@/services/auth/permissions'
import { listUsersPage } from '@/services/users/users.service'
import { useUiStore } from '@/stores/ui'
import type { ManagementUser } from '@/types/management'
import { downloadBlob } from '@/utils/browser-download'
import { copyText } from '@/utils/clipboard'
import { formatDateTime, shortId } from '@/utils/format'

const router = useRouter()
const uiStore = useUiStore()
const authorization = useAuthorization()

const queryInput = ref('')
const statusInput = ref('')
const query = ref('')
const status = ref('')
const loading = ref(false)
const error = ref('')
const items = ref<ManagementUser[]>([])
const selectedUserIds = ref<string[]>([])
const userRows = computed(() => items.value as unknown as Record<string, unknown>[])
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:users:page-size'
})
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'username',
    label: '账号',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.username
  },
  {
    key: 'email',
    label: '邮箱',
    sortable: true,
    defaultHidden: false,
    sortValue: (row) => row.email || ''
  },
  {
    key: 'role',
    label: '角色',
    sortable: true,
    sortValue: (row) => {
      const user = row as ManagementUser
      const role = primaryPlatformRole(user)
      if (role === 'platform_super_admin') {
        return 3
      }
      if (role === 'platform_operator') {
        return 2
      }
      if (role === 'platform_viewer') {
        return 1
      }
      return 0
    }
  },
  {
    key: 'status',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.status
  },
  {
    key: 'created_at',
    label: '创建时间',
    sortable: true,
    defaultHidden: true,
    sortValue: (row) => row.created_at || ''
  },
  {
    key: 'id',
    label: 'ID',
    sortable: true,
    defaultHidden: true,
    sortValue: (row) => row.id
  }
])

function userFromRow(row: Record<string, unknown>) {
  return row as ManagementUser
}

const adminCount = computed(
  () => items.value.filter((item) => primaryPlatformRole(item) === 'platform_super_admin').length
)
const activeCount = computed(() => items.value.filter((item) => item.status === 'active').length)
const selectedUsers = computed(() => items.value.filter((item) => selectedUserIds.value.includes(item.id)))
const stats = computed(() => [
  {
    label: '当前结果',
    value: items.value.length,
    hint: '展示最新查询返回的用户',
    icon: 'users',
    tone: 'primary'
  },
  {
    label: '管理员',
    value: adminCount.value,
    hint: '当前结果集中拥有超级管理员权限的用户',
    icon: 'shield',
    tone: 'success'
  },
  {
    label: '活跃成员',
    value: activeCount.value,
    hint: '当前结果集中状态为 active 的用户',
    icon: 'activity',
    tone: 'warning'
  }
])

const bulkActionSummary = computed(() => {
  const names = selectedUsers.value.slice(0, 3).map((item) => item.username)
  if (!names.length) {
    return ''
  }

  const suffix =
    selectedUsers.value.length > names.length
      ? ` 等 ${selectedUsers.value.length} 个账号`
      : ` 共 ${selectedUsers.value.length} 个账号`

  return `${names.join('、')}${suffix}`
})

async function loadUsers() {
  loading.value = true
  error.value = ''

  try {
    const payload = await listUsersPage({
      limit: pagination.pageSize.value,
      offset: pagination.offset.value,
      query: query.value,
      status: status.value
    })

    items.value = payload.items
    pagination.setTotal(payload.total)
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value = loadError instanceof Error ? loadError.message : '用户列表加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  status.value = statusInput.value
  if (pagination.page.value === 1) {
    void loadUsers()
    return
  }

  pagination.resetPage()
}

function resetFilters() {
  queryInput.value = ''
  statusInput.value = ''
  query.value = ''
  status.value = ''
  if (pagination.page.value === 1) {
    void loadUsers()
    return
  }

  pagination.resetPage()
}

async function handleCopyValue(label: string, value: string) {
  const copied = await copyText(value)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? `已复制${label}` : '复制失败',
    message: copied ? value : '当前环境不支持自动复制，请手动复制。'
  })
}

function clearUserSelection() {
  selectedUserIds.value = []
}

function updateSelectedUserIds(keys: Array<string | number>) {
  selectedUserIds.value = keys.map(String)
}

async function handleCopySelectedUserIds() {
  const content = selectedUsers.value.map((item) => item.id).join('\n')
  const copied = await copyText(content)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制所选用户 ID' : '复制失败',
    message: copied ? `${selectedUsers.value.length} 个用户 ID 已写入剪贴板。` : '当前环境不支持自动复制，请手动复制。'
  })
}

async function handleCopySelectedEmails() {
  const emails = selectedUsers.value.map((item) => item.email?.trim() || '').filter(Boolean)
  const copied = await copyText(emails.join('\n'))
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制所选邮箱' : '复制失败',
    message: copied ? `${emails.length} 个邮箱已写入剪贴板。` : '当前环境不支持自动复制，请手动复制。'
  })
}

function handleExportUserSummary() {
  const rows = selectedUsers.value.map((item) =>
    [
      item.id,
      item.username,
      item.email || '',
      describePlatformRole(item),
      item.status,
      item.created_at || ''
    ].join('\t')
  )
  const content = ['id\tusername\temail\trole\tstatus\tcreated_at', ...rows].join('\n')
  downloadBlob(
    new Blob([content], { type: 'text/tab-separated-values;charset=utf-8' }),
    `users-summary-${new Date().toISOString().slice(0, 10)}.tsv`
  )
  uiStore.pushToast({
    type: 'success',
    title: '用户摘要已导出',
    message: `已导出 ${selectedUsers.value.length} 个用户的摘要文件。`
  })
}

function userActions(user: ManagementUser): ActionMenuItem[] {
  return [
    {
      key: 'copy-id',
      label: '复制用户 ID',
      icon: 'copy',
      onSelect: () => handleCopyValue('用户 ID', user.id)
    },
    {
      key: 'copy-email',
      label: user.email ? '复制邮箱' : '邮箱未填写',
      icon: 'copy',
      disabled: !user.email,
      onSelect: () => handleCopyValue('邮箱', user.email || '')
    },
    {
      key: 'detail',
      label: '用户详情',
      icon: 'eye',
      onSelect: () => void router.push(`/workspace/users/${user.id}`)
    }
  ]
}

const selectedEmailsCount = computed(
  () => selectedUsers.value.filter((item) => Boolean(item.email?.trim())).length
)

const bulkActions = computed<BulkActionItem[]>(() => [
  {
    key: 'copy-ids',
    label: '复制用户 ID',
    icon: 'copy',
    variant: 'secondary',
    onSelect: handleCopySelectedUserIds
  },
  {
    key: 'copy-emails',
    label: '复制邮箱',
    icon: 'copy',
    variant: 'secondary',
    disabled: selectedEmailsCount.value === 0,
    onSelect: handleCopySelectedEmails
  },
  {
    key: 'export',
    label: '导出摘要',
    icon: 'download',
    variant: 'primary',
    onSelect: handleExportUserSummary
  }
])

watch(items, (nextItems) => {
  const validIds = new Set(nextItems.map((item) => item.id))
  selectedUserIds.value = selectedUserIds.value.filter((id) => validIds.has(id))
})

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadUsers()
})

onMounted(() => {
  void loadUsers()
})
</script>

<template>
  <section class="pw-page-shell h-full min-h-0 overflow-y-auto">
    <PageHeader
      eyebrow="Users"
      title="用户管理"
      description="用户页承担账号盘点和权限可视化。这里先把列表、筛选和状态表达统一到新的页面母版里。"
    >
      <template #actions>
        <BaseButton
          :disabled="!authorization.can('platform.user.create')"
          @click="void router.push('/workspace/users/new')"
        >
          <BaseIcon
            name="users"
            size="sm"
          />
          {{ authorization.can('platform.user.create') ? '新建用户' : '当前账号只读' }}
        </BaseButton>
        <BaseButton
          variant="secondary"
          @click="loadUsers"
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
      title="用户列表加载失败"
      :description="error"
      variant="danger"
    />

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
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px_auto_auto]">
            <SearchInput
              v-model="queryInput"
              placeholder="按用户名搜索"
            />
            <BaseSelect v-model="statusInput">
              <option value="">
                全部状态
              </option>
              <option value="active">
                active
              </option>
              <option value="disabled">
                disabled
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
          :selected-count="selectedUsers.length"
          :summary="bulkActionSummary"
          :actions="bulkActions"
          @clear="clearUserSelection"
        />
      </template>

      <template #table>
        <DataTable
          :columns="columns"
          :rows="userRows"
          :loading="loading"
          selectable
          :selected-row-keys="selectedUserIds"
          row-key="id"
          sort-storage-key="pw:users:sort"
          column-storage-key="pw:users:columns"
          empty-title="没有找到用户"
          empty-description="当前筛选条件下没有用户数据。后续创建用户、查看用户详情和项目关系可以继续挂在这套母版上。"
          empty-icon="users"
          @update:selected-row-keys="updateSelectedUserIds"
        >
          <template #cell-username="{ row }">
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-600 shadow-soft dark:bg-primary-950/30 dark:text-primary-300">
                <BaseIcon
                  name="user"
                  size="sm"
                />
              </div>
              <div class="font-semibold text-gray-900 dark:text-white">
                {{ userFromRow(row).username }}
              </div>
            </div>
          </template>

          <template #cell-email="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ userFromRow(row).email || '未填写' }}
            </span>
          </template>

          <template #cell-role="{ row }">
            <StatusPill :tone="primaryPlatformRole(userFromRow(row)) === 'platform_super_admin' ? 'warning' : 'neutral'">
              {{ describePlatformRole(userFromRow(row)) }}
            </StatusPill>
          </template>

          <template #cell-status="{ row }">
            <StatusPill :tone="userFromRow(row).status === 'active' ? 'success' : 'warning'">
              {{ userFromRow(row).status }}
            </StatusPill>
          </template>

          <template #cell-created_at="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ formatDateTime(userFromRow(row).created_at) }}
            </span>
          </template>

          <template #cell-id="{ row }">
            <span class="text-gray-400 dark:text-dark-400">
              {{ shortId(userFromRow(row).id) }}
            </span>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="userActions(userFromRow(row))" />
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
  </section>
</template>
