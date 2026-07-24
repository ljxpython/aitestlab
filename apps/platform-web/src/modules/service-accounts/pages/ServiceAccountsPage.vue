<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseDrawer from '@/components/base/BaseDrawer.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import GuidePanel from '@/components/platform/GuidePanel.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { usePagination } from '@/composables/usePagination'
import {
  createServiceAccount,
  createServiceAccountToken,
  deleteServiceAccountProjectGrant,
  listServiceAccountProjectGrants,
  listServiceAccounts,
  revokeServiceAccountToken,
  upsertServiceAccountProjectGrant,
  updateServiceAccount
} from '@/services/system/service-accounts.service'
import { formatPlatformRoleLabel, formatProjectRoleLabel } from '@/services/auth/permissions'
import { getPlatformConfigSnapshot } from '@/services/system/platform-config.service'
import { useUiStore } from '@/stores/ui'
import type {
  ManagementServiceAccount,
  ManagementServiceAccountToken,
  ProjectRole,
  ServiceAccountProjectGrant
} from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { formatDateTime, shortId } from '@/utils/format'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

type RevokeTokenTarget = {
  accountId: string
  accountName: string
  tokenId: string
  tokenName: string
}

type DeleteGrantTarget = {
  accountId: string
  accountName: string
  projectId: string
}

const uiStore = useUiStore()
const authorization = useAuthorization()
const loading = ref(false)
const submitting = ref(false)
const savingAccount = ref(false)
const error = ref('')
const notice = ref('')
const query = ref('')
const statusFilter = ref('all')
const tokenSearch = ref('')
const accounts = ref<ManagementServiceAccount[]>([])
const summary = ref<{
  total_accounts: number
  active_accounts: number
  active_tokens: number
  revoked_tokens: number
  default_token_ttl_days: number
  api_key_header: string
} | null>(null)

const createDialogOpen = ref(false)
const tokenDialogOpen = ref(false)
const detailDrawerOpen = ref(false)
const editDialogOpen = ref(false)
const revokeConfirmOpen = ref(false)
const deleteGrantConfirmOpen = ref(false)
const selectedAccount = ref<ManagementServiceAccount | null>(null)
const pendingRevokeTarget = ref<RevokeTokenTarget | null>(null)
const pendingDeleteGrant = ref<DeleteGrantTarget | null>(null)
const tokenSecret = ref('')
const projectGrants = ref<ServiceAccountProjectGrant[]>([])
const loadingProjectGrants = ref(false)
const savingProjectGrant = ref(false)
const projectGrantError = ref('')
const SERVICE_ACCOUNTS_FETCH_LIMIT = 200
const pagination = usePagination({
  initialPageSize: 10,
  storageKey: 'pw:service-accounts:page-size'
})
const canManageServiceAccounts = computed(() => authorization.can('platform.service_account.write'))
const canManageProjectGrants = computed(() => authorization.can('platform.service_account.grant.write'))

const createForm = ref({
  name: '',
  description: '',
  platform_roles: ['platform_viewer']
})

const editForm = ref({
  description: '',
  platform_roles: ['platform_viewer']
})

const tokenForm = ref({
  name: '',
  expires_in_days: '90'
})

const projectGrantForm = ref<{ project_id: string; role: ProjectRole }>({
  project_id: '',
  role: 'project_executor'
})

const roleOptions = [
  { value: 'platform_viewer', label: formatPlatformRoleLabel('platform_viewer') },
  { value: 'platform_operator', label: formatPlatformRoleLabel('platform_operator') },
  { value: 'platform_super_admin', label: formatPlatformRoleLabel('platform_super_admin') }
]

const projectRoleOptions = [
  { value: 'project_admin', label: formatProjectRoleLabel('project_admin') },
  { value: 'project_editor', label: formatProjectRoleLabel('project_editor') },
  { value: 'project_executor', label: formatProjectRoleLabel('project_executor') }
]

const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'active', label: 'active' },
  { value: 'disabled', label: 'disabled' }
]

const stats = computed(() => {
  const total = summary.value?.total_accounts ?? accounts.value.length
  const active = summary.value?.active_accounts ?? accounts.value.filter((item) => item.status === 'active').length
  const tokens = summary.value?.active_tokens ?? accounts.value.reduce((sum, item) => sum + item.tokens.length, 0)
  const recentlyUsed = accounts.value.filter((item) => item.last_used_at).length

  return [
    {
      label: '当前账号',
      value: total,
      hint: '本页当前结果集中的 service account 数量',
      icon: 'users',
      tone: 'primary'
    },
    {
      label: '激活账号',
      value: active,
      hint: 'status = active',
      icon: 'check',
      tone: 'success'
    },
    {
      label: 'Token 数量',
      value: tokens,
      hint: '当前列表中可见 token 总数',
      icon: 'lock',
      tone: 'warning'
    },
    {
      label: '最近使用',
      value: recentlyUsed,
      hint: '至少有一次 last_used_at 记录',
      icon: 'activity',
      tone: 'danger'
    }
  ]
})

const filteredAccounts = computed(() => {
  const keyword = query.value.trim().toLowerCase()

  return accounts.value.filter((item) => {
    const matchesStatus = statusFilter.value === 'all' || item.status === statusFilter.value
    if (!matchesStatus) {
      return false
    }

    if (!keyword) {
      return true
    }

    const tokenText = item.tokens
      .map((token) => `${token.name} ${token.token_prefix} ${token.status}`)
      .join(' ')

    return [item.name, item.description || '', item.platform_roles.join(' '), tokenText]
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  })
})

const paginatedAccounts = computed(() => {
  return filteredAccounts.value.slice(pagination.offset.value, pagination.offset.value + pagination.pageSize.value)
})

const filteredSelectedTokens = computed<ManagementServiceAccountToken[]>(() => {
  const account = selectedAccount.value
  if (!account) {
    return []
  }

  const keyword = tokenSearch.value.trim().toLowerCase()
  if (!keyword) {
    return account.tokens
  }

  return account.tokens.filter((token) =>
    [token.name, token.token_prefix, token.status].join(' ').toLowerCase().includes(keyword)
  )
})

watch(
  () => filteredAccounts.value.length,
  (total) => {
    pagination.setTotal(total)
  },
  { immediate: true }
)

watch([query, statusFilter], () => {
  pagination.resetPage()
})

async function loadAccounts() {
  loading.value = true
  error.value = ''

  try {
    const payload = await listServiceAccounts({
      limit: SERVICE_ACCOUNTS_FETCH_LIMIT,
      offset: 0
    })
    accounts.value = payload.items

    if (selectedAccount.value) {
      const matched = payload.items.find((item) => item.id === selectedAccount.value?.id) ?? null
      selectedAccount.value = matched
      if (!matched) {
        detailDrawerOpen.value = false
      }
    }

    const configPayload = await getPlatformConfigSnapshot()
    summary.value = configPayload.security.service_accounts
  } catch (loadError) {
    accounts.value = []
    summary.value = null
    selectedAccount.value = null
    error.value = resolvePlatformHttpErrorMessage(loadError, 'Service account 加载失败', 'service account')
  } finally {
    loading.value = false
  }
}

function resetCreateForm() {
  createForm.value = {
    name: '',
    description: '',
    platform_roles: ['platform_viewer']
  }
}

function openCreateDialog() {
  if (!canManageServiceAccounts.value) {
    return
  }
  resetCreateForm()
  createDialogOpen.value = true
}

function openEditDialog(account: ManagementServiceAccount) {
  if (!canManageServiceAccounts.value) {
    return
  }
  selectedAccount.value = account
  editForm.value = {
    description: account.description || '',
    platform_roles: account.platform_roles.length ? [...account.platform_roles] : ['platform_viewer']
  }
  editDialogOpen.value = true
}

async function loadProjectGrants(accountId: string) {
  loadingProjectGrants.value = true
  projectGrantError.value = ''
  try {
    projectGrants.value = await listServiceAccountProjectGrants(accountId)
  } catch (loadError) {
    projectGrants.value = []
    projectGrantError.value = resolvePlatformHttpErrorMessage(
      loadError,
      '项目授权加载失败',
      'service account project grant'
    )
  } finally {
    loadingProjectGrants.value = false
  }
}

function openAccountDetail(account: ManagementServiceAccount) {
  selectedAccount.value = account
  tokenSearch.value = ''
  projectGrantForm.value = { project_id: '', role: 'project_executor' }
  projectGrants.value = []
  projectGrantError.value = ''
  detailDrawerOpen.value = true
  if (canManageProjectGrants.value) {
    void loadProjectGrants(account.id)
  }
}

async function saveProjectGrant() {
  const account = selectedAccount.value
  const projectId = projectGrantForm.value.project_id.trim()
  if (!account || !projectId || !canManageProjectGrants.value) {
    return
  }

  savingProjectGrant.value = true
  projectGrantError.value = ''
  try {
    await upsertServiceAccountProjectGrant(account.id, projectId, projectGrantForm.value.role)
    projectGrantForm.value = { project_id: '', role: 'project_executor' }
    await loadProjectGrants(account.id)
    uiStore.pushToast({
      type: 'success',
      title: '项目授权已保存',
      message: `${account.name} / ${projectId}`
    })
  } catch (saveError) {
    projectGrantError.value = resolvePlatformHttpErrorMessage(
      saveError,
      '项目授权保存失败',
      'service account project grant'
    )
  } finally {
    savingProjectGrant.value = false
  }
}

function requestDeleteProjectGrant(grant: ServiceAccountProjectGrant) {
  const account = selectedAccount.value
  if (!account || !canManageProjectGrants.value) {
    return
  }
  pendingDeleteGrant.value = {
    accountId: account.id,
    accountName: account.name,
    projectId: grant.project_id
  }
  deleteGrantConfirmOpen.value = true
}

async function confirmDeleteProjectGrant() {
  const target = pendingDeleteGrant.value
  if (!target || !canManageProjectGrants.value) {
    return
  }

  projectGrantError.value = ''
  try {
    await deleteServiceAccountProjectGrant(target.accountId, target.projectId)
    deleteGrantConfirmOpen.value = false
    pendingDeleteGrant.value = null
    await loadProjectGrants(target.accountId)
    uiStore.pushToast({
      type: 'success',
      title: '项目授权已删除',
      message: `${target.accountName} / ${target.projectId}`
    })
  } catch (deleteError) {
    projectGrantError.value = resolvePlatformHttpErrorMessage(
      deleteError,
      '项目授权删除失败',
      'service account project grant'
    )
  }
}

function closeDeleteProjectGrantDialog() {
  deleteGrantConfirmOpen.value = false
  pendingDeleteGrant.value = null
}

async function submitCreateForm() {
  if (!canManageServiceAccounts.value) {
    error.value = '当前账号没有 service account 写权限'
    return
  }
  submitting.value = true
  error.value = ''
  notice.value = ''

  try {
    await createServiceAccount({
      name: createForm.value.name.trim(),
      description: createForm.value.description.trim() || undefined,
      platform_roles: createForm.value.platform_roles
    })
    createDialogOpen.value = false
    notice.value = 'Service account 已创建。'
    await loadAccounts()
  } catch (submitError) {
    error.value = resolvePlatformHttpErrorMessage(submitError, 'Service account 创建失败', 'service account')
  } finally {
    submitting.value = false
  }
}

async function submitEditForm() {
  if (!selectedAccount.value) {
    return
  }
  if (!canManageServiceAccounts.value) {
    error.value = '当前账号没有 service account 写权限'
    return
  }

  savingAccount.value = true
  error.value = ''
  notice.value = ''

  try {
    await updateServiceAccount(selectedAccount.value.id, {
      description: editForm.value.description.trim() || null,
      platform_roles: editForm.value.platform_roles
    })
    editDialogOpen.value = false
    notice.value = `${selectedAccount.value.name} 已更新描述和角色。`
    uiStore.pushToast({
      type: 'success',
      title: 'Service account 已更新',
      message: `${selectedAccount.value.name} 的治理信息已保存`
    })
    await loadAccounts()
  } catch (saveError) {
    error.value = resolvePlatformHttpErrorMessage(saveError, 'Service account 更新失败', 'service account')
  } finally {
    savingAccount.value = false
  }
}

async function toggleAccountStatus(account: ManagementServiceAccount) {
  if (!canManageServiceAccounts.value) {
    error.value = '当前账号没有 service account 写权限'
    return
  }
  error.value = ''
  notice.value = ''

  try {
    const nextStatus = account.status === 'active' ? 'disabled' : 'active'
    await updateServiceAccount(account.id, {
      status: nextStatus,
      description: account.description,
      platform_roles: account.platform_roles
    })
    notice.value = `${account.name} 已切换为 ${nextStatus}。`
    uiStore.pushToast({
      type: 'success',
      title: 'Service account 状态已更新',
      message: `${account.name} -> ${nextStatus}`
    })
    await loadAccounts()
  } catch (toggleError) {
    error.value = resolvePlatformHttpErrorMessage(toggleError, 'Service account 状态更新失败', 'service account')
  }
}

function openTokenDialog(account: ManagementServiceAccount) {
  if (!canManageServiceAccounts.value) {
    return
  }
  selectedAccount.value = account
  tokenForm.value = {
    name: '',
    expires_in_days: '90'
  }
  tokenSecret.value = ''
  tokenDialogOpen.value = true
}

async function submitTokenForm() {
  if (!selectedAccount.value) {
    return
  }
  if (!canManageServiceAccounts.value) {
    error.value = '当前账号没有 service account 写权限'
    return
  }

  submitting.value = true
  error.value = ''
  notice.value = ''

  try {
    const payload = await createServiceAccountToken(selectedAccount.value.id, {
      name: tokenForm.value.name.trim(),
      expires_in_days: Number(tokenForm.value.expires_in_days) || undefined
    })
    tokenSecret.value = payload.plain_text_token
    notice.value = `Token 已为 ${selectedAccount.value.name} 创建。`
    await loadAccounts()
  } catch (submitError) {
    error.value = resolvePlatformHttpErrorMessage(submitError, 'Token 创建失败', 'service account token')
  } finally {
    submitting.value = false
  }
}

function requestRevokeToken(account: ManagementServiceAccount, token: ManagementServiceAccountToken) {
  if (!canManageServiceAccounts.value) {
    return
  }
  pendingRevokeTarget.value = {
    accountId: account.id,
    accountName: account.name,
    tokenId: token.id,
    tokenName: token.name
  }
  revokeConfirmOpen.value = true
}

async function confirmRevokeToken() {
  const target = pendingRevokeTarget.value
  if (!target) {
    return
  }
  if (!canManageServiceAccounts.value) {
    error.value = '当前账号没有 service account 写权限'
    return
  }

  error.value = ''
  notice.value = ''

  try {
    await revokeServiceAccountToken(target.accountId, target.tokenId)
    revokeConfirmOpen.value = false
    pendingRevokeTarget.value = null
    notice.value = `Token ${target.tokenName} 已撤销。`
    uiStore.pushToast({
      type: 'success',
      title: 'Token 已撤销',
      message: `${target.accountName} / ${target.tokenName}`
    })
    await loadAccounts()
  } catch (revokeError) {
    error.value = resolvePlatformHttpErrorMessage(revokeError, 'Token 撤销失败', 'service account token')
  }
}

function closeRevokeDialog() {
  revokeConfirmOpen.value = false
  pendingRevokeTarget.value = null
}

async function copyTokenSecret() {
  const copied = tokenSecret.value ? await copyText(tokenSecret.value) : false
  notice.value = copied ? 'Token 已复制。' : 'Token 复制失败，请手动记录。'
}

onMounted(() => {
  void loadAccounts()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Governance"
      title="Service Accounts"
      description="这里是平台级 API key / service account 正式治理入口。别再靠临时 header 手搓联调了，该建账号、发 token、停用和撤销都在这里收口。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="loading"
          @click="loadAccounts"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新
        </BaseButton>
        <BaseButton
          :disabled="!canManageServiceAccounts"
          @click="openCreateDialog"
        >
          <BaseIcon
            name="users"
            size="sm"
          />
          {{ canManageServiceAccounts ? '新建账号' : '当前账号只读' }}
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="Service account 操作失败"
      :description="error"
      variant="danger"
    />
    <StateBanner
      v-else-if="notice"
      title="Service account 已更新"
      :description="notice"
      variant="success"
    />

    <GuidePanel
      guide-id="service-account-governance"
      title="治理边界说明"
      description="平台角色、项目授权和 API key 生命周期分开治理。项目访问必须显式授予，token 明文仍只在创建当下返回一次。"
      tone="info"
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

    <div
      v-if="summary"
      class="grid gap-4 xl:items-start xl:grid-cols-3"
    >
      <SurfaceCard class="space-y-2">
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
          API Key Header
        </div>
        <div class="text-sm font-semibold text-gray-900 dark:text-white">
          {{ summary.api_key_header }}
        </div>
      </SurfaceCard>
      <SurfaceCard class="space-y-2">
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
          Default TTL
        </div>
        <div class="text-sm font-semibold text-gray-900 dark:text-white">
          {{ summary.default_token_ttl_days }} 天
        </div>
      </SurfaceCard>
      <SurfaceCard class="space-y-2">
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
          Revoked Tokens
        </div>
        <div class="text-sm font-semibold text-gray-900 dark:text-white">
          {{ summary.revoked_tokens }}
        </div>
      </SurfaceCard>
    </div>

    <SurfaceCard class="space-y-4">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            过滤与检索
          </div>
          <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
            支持按账号状态、名称、角色以及 token 名称或前缀检索。
          </div>
        </div>
        <div class="grid gap-3 sm:grid-cols-[minmax(0,320px)_160px]">
          <BaseInput
            v-model="query"
            placeholder="搜索名称、描述、角色或 token 前缀"
          />
          <BaseSelect
            v-model="statusFilter"
            :options="statusOptions"
          />
        </div>
      </div>
    </SurfaceCard>

    <EmptyState
      v-if="!filteredAccounts.length && !loading"
      title="当前没有 service account"
      description="先创建一个平台级 service account，再用 token 去接 metrics、脚本或自动化调用。"
      icon="users"
      action-label="新建账号"
      @action="openCreateDialog"
    />

    <div
      v-else
      class="space-y-5"
    >
      <SurfaceCard
        v-for="account in paginatedAccounts"
        :key="account.id"
        class="space-y-5"
      >
        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <div class="text-base font-semibold text-gray-900 dark:text-white">
                {{ account.name }}
              </div>
              <span
                class="rounded-full px-2.5 py-1 text-xs font-semibold"
                :class="account.status === 'active'
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200'
                  : 'bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-dark-200'"
              >
                {{ account.status }}
              </span>
              <span class="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600 dark:bg-dark-800 dark:text-dark-200">
                {{ account.tokens.length }} tokens
              </span>
            </div>
            <div class="mt-2 text-sm text-gray-500 dark:text-dark-300">
              {{ account.description || '暂无描述' }}
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <span
                v-for="role in account.platform_roles"
                :key="role"
                class="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 dark:bg-primary-950/30 dark:text-primary-200"
              >
                {{ formatPlatformRoleLabel(role) }}
              </span>
            </div>
            <div class="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-gray-500 dark:text-dark-300">
              <span>ID {{ shortId(account.id) }}</span>
              <span>创建于 {{ formatDateTime(account.created_at) }}</span>
              <span>最近使用 {{ formatDateTime(account.last_used_at) }}</span>
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <BaseButton
              variant="secondary"
              @click="openAccountDetail(account)"
            >
              详情
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="!canManageServiceAccounts"
              @click="openEditDialog(account)"
            >
              编辑
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="!canManageServiceAccounts"
              @click="openTokenDialog(account)"
            >
              发 Token
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="!canManageServiceAccounts"
              @click="toggleAccountStatus(account)"
            >
              {{ account.status === 'active' ? '停用' : '启用' }}
            </BaseButton>
          </div>
        </div>

        <div class="space-y-3">
          <div>
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Project Grants
            </div>
            <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
              项目授权与 API key 分开管理；删除授权后现有 key 无需轮换。
            </div>
          </div>

          <div
            v-if="!canManageProjectGrants"
            class="pw-card-subtle px-4 py-4 text-sm text-gray-500 dark:text-dark-300"
          >
            当前账号没有管理项目授权的权限。
          </div>

          <StateBanner
            v-if="projectGrantError"
            title="项目授权操作失败"
            :description="projectGrantError"
            variant="danger"
          />

          <div
            v-if="canManageProjectGrants"
            class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_200px_auto]"
          >
            <BaseInput
              v-model="projectGrantForm.project_id"
              placeholder="项目 UUID"
            />
            <BaseSelect
              v-model="projectGrantForm.role"
              :options="projectRoleOptions"
            />
            <BaseButton
              :disabled="savingProjectGrant || !projectGrantForm.project_id.trim()"
              @click="saveProjectGrant"
            >
              {{ savingProjectGrant ? '保存中...' : '保存授权' }}
            </BaseButton>
          </div>

          <div
            v-if="canManageProjectGrants && loadingProjectGrants"
            class="pw-card-subtle h-20 animate-pulse"
          />
          <EmptyState
            v-else-if="canManageProjectGrants && !projectGrants.length"
            title="该账号暂无项目授权"
            description="没有 grant 时，API key 不能访问任何项目内容。"
            icon="project"
          />
          <template v-else-if="canManageProjectGrants">
            <article
              v-for="grant in projectGrants"
              :key="grant.project_id"
              class="pw-card-subtle px-4 py-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="break-all text-sm font-semibold text-gray-900 dark:text-white">
                    {{ grant.project_id }}
                  </div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                    {{ formatProjectRoleLabel(grant.role) }} · 更新于 {{ formatDateTime(grant.updated_at) }}
                  </div>
                </div>
                <BaseButton
                  variant="secondary"
                  :disabled="!canManageProjectGrants"
                  @click="requestDeleteProjectGrant(grant)"
                >
                  删除授权
                </BaseButton>
              </div>
            </article>
          </template>
        </div>

        <div class="space-y-3">
          <div class="flex items-center justify-between gap-3">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Tokens
            </div>
            <div class="text-xs text-gray-500 dark:text-dark-300">
              {{ account.tokens.length }} total
            </div>
          </div>
          <EmptyState
            v-if="!account.tokens.length"
            title="该账号暂无 token"
            description="当前 service account 还没有可用 token。"
            icon="lock"
            action-label="发 Token"
            @action="openTokenDialog(account)"
          />
          <div
            v-else
            class="grid gap-3 xl:items-start xl:grid-cols-2"
          >
            <article
              v-for="token in account.tokens"
              :key="token.id"
              class="pw-card-subtle px-4 py-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">
                    {{ token.name }}
                  </div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                    {{ token.token_prefix }}
                  </div>
                  <div class="mt-3 grid gap-1 text-xs text-gray-500 dark:text-dark-300">
                    <span>status {{ token.status }}</span>
                    <span>created {{ formatDateTime(token.created_at) }}</span>
                    <span>expires {{ formatDateTime(token.expires_at) }}</span>
                    <span>last used {{ formatDateTime(token.last_used_at) }}</span>
                  </div>
                </div>
                <BaseButton
                  variant="secondary"
                  :disabled="token.status !== 'active' || !canManageServiceAccounts"
                  @click="requestRevokeToken(account, token)"
                >
                  撤销
                </BaseButton>
              </div>
            </article>
          </div>
        </div>
      </SurfaceCard>

      <PaginationBar
        :page="pagination.page.value"
        :page-size="pagination.pageSize.value"
        :total="pagination.total.value"
        @update:page="pagination.setPage"
        @update:page-size="pagination.setPageSize"
      />
    </div>

    <BaseDialog
      :show="createDialogOpen"
      title="新建 Service Account"
      width="normal"
      @close="createDialogOpen = false"
    >
      <div class="space-y-4">
        <label class="block space-y-2">
          <span class="text-sm font-medium text-gray-700 dark:text-dark-100">名称</span>
          <BaseInput
            v-model="createForm.name"
            placeholder="例如 metrics-reader"
          />
        </label>
        <label class="block space-y-2">
          <span class="text-sm font-medium text-gray-700 dark:text-dark-100">描述</span>
          <BaseInput
            v-model="createForm.description"
            placeholder="说明这个账号给谁用、干什么"
          />
        </label>
        <label class="block space-y-2">
          <span class="text-sm font-medium text-gray-700 dark:text-dark-100">默认角色</span>
          <BaseSelect
            :model-value="createForm.platform_roles[0] || 'platform_viewer'"
            :options="roleOptions"
            @update:model-value="(value) => (createForm.platform_roles = [value])"
          />
        </label>
      </div>

      <template #footer>
        <div class="flex gap-3">
          <BaseButton
            variant="secondary"
            @click="createDialogOpen = false"
          >
            取消
          </BaseButton>
          <BaseButton
            :disabled="submitting || !createForm.name.trim() || !canManageServiceAccounts"
            @click="submitCreateForm"
          >
            {{ submitting ? '创建中...' : '确认创建' }}
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <BaseDialog
      :show="editDialogOpen"
      title="编辑 Service Account"
      width="normal"
      @close="editDialogOpen = false"
    >
      <div class="space-y-4">
        <div
          v-if="selectedAccount"
          class="rounded-2xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-dark-800/80 dark:text-dark-200"
        >
          当前账号：{{ selectedAccount.name }}
        </div>
        <label class="block space-y-2">
          <span class="text-sm font-medium text-gray-700 dark:text-dark-100">描述</span>
          <BaseInput
            v-model="editForm.description"
            placeholder="描述账号用途、归属与责任人"
          />
        </label>
        <label class="block space-y-2">
          <span class="text-sm font-medium text-gray-700 dark:text-dark-100">平台角色</span>
          <BaseSelect
            :model-value="editForm.platform_roles[0] || 'platform_viewer'"
            :options="roleOptions"
            @update:model-value="(value) => (editForm.platform_roles = [value])"
          />
        </label>
      </div>

      <template #footer>
        <div class="flex gap-3">
          <BaseButton
            variant="secondary"
            @click="editDialogOpen = false"
          >
            取消
          </BaseButton>
          <BaseButton
            :disabled="savingAccount || !canManageServiceAccounts"
            @click="submitEditForm"
          >
            {{ savingAccount ? '保存中...' : '确认保存' }}
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <BaseDialog
      :show="tokenDialogOpen"
      title="创建 Token"
      width="normal"
      @close="tokenDialogOpen = false"
    >
      <div class="space-y-4">
        <div
          v-if="selectedAccount"
          class="rounded-2xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-dark-800/80 dark:text-dark-200"
        >
          当前账号：{{ selectedAccount.name }}
        </div>
        <label class="block space-y-2">
          <span class="text-sm font-medium text-gray-700 dark:text-dark-100">Token 名称</span>
          <BaseInput
            v-model="tokenForm.name"
            placeholder="例如 default"
          />
        </label>
        <label class="block space-y-2">
          <span class="text-sm font-medium text-gray-700 dark:text-dark-100">过期天数</span>
          <BaseInput
            v-model="tokenForm.expires_in_days"
            type="number"
            placeholder="90"
          />
        </label>

        <div
          v-if="tokenSecret"
          class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 dark:border-emerald-900/40 dark:bg-emerald-950/20"
        >
          <div class="text-sm font-semibold text-emerald-700 dark:text-emerald-200">
            明文 Token 只展示这一次
          </div>
          <div class="mt-2 break-all text-sm text-emerald-700 dark:text-emerald-200">
            {{ tokenSecret }}
          </div>
          <div class="mt-3">
            <BaseButton
              variant="secondary"
              @click="copyTokenSecret"
            >
              复制 Token
            </BaseButton>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex gap-3">
          <BaseButton
            variant="secondary"
            @click="tokenDialogOpen = false"
          >
            关闭
          </BaseButton>
          <BaseButton
            :disabled="submitting || !tokenForm.name.trim() || !canManageServiceAccounts"
            @click="submitTokenForm"
          >
            {{ submitting ? '创建中...' : '确认创建' }}
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <BaseDrawer
      :show="detailDrawerOpen"
      title="Service Account 详情"
      width="wide"
      @close="detailDrawerOpen = false"
    >
      <div
        v-if="selectedAccount"
        class="space-y-5"
      >
        <div class="pw-card p-5">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div class="flex flex-wrap items-center gap-2">
                <div class="text-base font-semibold text-gray-900 dark:text-white">
                  {{ selectedAccount.name }}
                </div>
                <span
                  class="rounded-full px-2.5 py-1 text-xs font-semibold"
                  :class="selectedAccount.status === 'active'
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200'
                    : 'bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-dark-200'"
                >
                  {{ selectedAccount.status }}
                </span>
              </div>
              <div class="mt-3 text-sm text-gray-500 dark:text-dark-300">
                {{ selectedAccount.description || '暂无描述' }}
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <BaseButton
                variant="secondary"
                :disabled="!canManageServiceAccounts"
                @click="openEditDialog(selectedAccount)"
              >
                编辑
              </BaseButton>
              <BaseButton
                variant="secondary"
                :disabled="!canManageServiceAccounts"
                @click="openTokenDialog(selectedAccount)"
              >
                发 Token
              </BaseButton>
            </div>
          </div>
          <div class="mt-4 grid gap-2 text-sm text-gray-600 dark:text-dark-200">
            <div>ID: {{ selectedAccount.id }}</div>
            <div>Created by: {{ selectedAccount.created_by || '--' }}</div>
            <div>Updated by: {{ selectedAccount.updated_by || '--' }}</div>
            <div>Created at: {{ formatDateTime(selectedAccount.created_at) }}</div>
            <div>Updated at: {{ formatDateTime(selectedAccount.updated_at) }}</div>
            <div>Last used at: {{ formatDateTime(selectedAccount.last_used_at) }}</div>
          </div>
        </div>

        <div>
          <div class="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
            Roles
          </div>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="role in selectedAccount.platform_roles"
              :key="role"
              class="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 dark:bg-primary-950/30 dark:text-primary-200"
            >
              {{ formatPlatformRoleLabel(role) }}
            </span>
          </div>
        </div>

        <div class="space-y-3">
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Tokens
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ filteredSelectedTokens.length }} / {{ selectedAccount.tokens.length }} 可见
              </div>
            </div>
            <div class="w-full sm:w-[260px]">
              <BaseInput
                v-model="tokenSearch"
                placeholder="搜索 token 名称或前缀"
              />
            </div>
          </div>

          <EmptyState
            v-if="!selectedAccount.tokens.length"
            title="该账号暂无 token"
            description="还没有签发任何 token。"
            icon="lock"
            action-label="发 Token"
            @action="openTokenDialog(selectedAccount)"
          />

          <EmptyState
            v-else-if="!filteredSelectedTokens.length"
            title="没有匹配的 token"
            description="换个名称或前缀关键字再试。"
            icon="search"
          />

          <template v-else>
            <article
              v-for="token in filteredSelectedTokens"
              :key="token.id"
              class="pw-card-subtle px-4 py-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">
                    {{ token.name }}
                  </div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                    {{ token.token_prefix }} · {{ token.status }}
                  </div>
                  <div class="mt-3 grid gap-1 text-xs text-gray-500 dark:text-dark-300">
                    <span>created {{ formatDateTime(token.created_at) }}</span>
                    <span>expires {{ formatDateTime(token.expires_at) }}</span>
                    <span>last used {{ formatDateTime(token.last_used_at) }}</span>
                    <span>revoked {{ formatDateTime(token.revoked_at) }}</span>
                  </div>
                </div>
                <BaseButton
                  variant="secondary"
                  :disabled="token.status !== 'active' || !canManageServiceAccounts"
                  @click="requestRevokeToken(selectedAccount, token)"
                >
                  撤销
                </BaseButton>
              </div>
            </article>
          </template>
        </div>
      </div>
    </BaseDrawer>

    <ConfirmDialog
      :show="revokeConfirmOpen"
      title="撤销 Token"
      :message="pendingRevokeTarget
        ? `撤销后 ${pendingRevokeTarget.accountName} / ${pendingRevokeTarget.tokenName} 将立即失效，确定继续吗？`
        : '撤销后该 token 将立即失效。'"
      confirm-text="确认撤销"
      cancel-text="取消"
      danger
      @cancel="closeRevokeDialog"
      @confirm="confirmRevokeToken"
    />

    <ConfirmDialog
      :show="deleteGrantConfirmOpen"
      title="删除项目授权"
      :message="pendingDeleteGrant
        ? `删除后 ${pendingDeleteGrant.accountName} 将立即失去项目 ${pendingDeleteGrant.projectId} 的访问权，确定继续吗？`
        : '删除后该项目授权将立即失效。'"
      confirm-text="确认删除"
      cancel-text="取消"
      danger
      @cancel="closeDeleteProjectGrantDialog"
      @confirm="confirmDeleteProjectGrant"
    />
  </section>
</template>
