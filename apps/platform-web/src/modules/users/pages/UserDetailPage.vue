<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import {
  describePlatformRole,
  formatPlatformRoleLabel,
  formatProjectRoleLabel,
  isProjectAdminRole,
  isProjectEditorRole,
  primaryPlatformRole
} from '@/services/auth/permissions'
import { listAudit } from '@/services/audit/audit.service'
import { useUiStore } from '@/stores/ui'
import type { ManagementAuditRow, ManagementUser, ManagementUserProject, PlatformRole, ProjectRole } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { formatDateTime, shortId } from '@/utils/format'
import { getUser, listUserProjects, resetUserPassword, updateUser } from '@/services/users/users.service'

function getRoleTone(role: string): 'info' | 'success' | 'warning' {
  if (isProjectAdminRole(role as ProjectRole)) {
    return 'warning'
  }
  if (isProjectEditorRole(role as ProjectRole)) {
    return 'info'
  }
  return 'success'
}

function getStatusTone(statusCode: number): 'success' | 'warning' | 'danger' {
  if (statusCode >= 500) {
    return 'danger'
  }
  if (statusCode >= 400) {
    return 'warning'
  }
  return 'success'
}

const route = useRoute()
const router = useRouter()
const uiStore = useUiStore()
const authorization = useAuthorization()

const userId = computed(() =>
  typeof route.params.userId === 'string' ? route.params.userId.trim() : ''
)

const user = ref<ManagementUser | null>(null)
const projects = ref<ManagementUserProject[]>([])
const audits = ref<ManagementAuditRow[]>([])
const loading = ref(false)
const savingProfile = ref(false)
const updatingPassword = ref(false)
const error = ref('')
const notice = ref('')

const username = ref('')
const status = ref<'active' | 'disabled'>('active')
const platformRole = ref<PlatformRole | ''>('')
const newPassword = ref('')
const confirmNewPassword = ref('')
const projectSearchInput = ref('')
const projectQuery = ref('')
const auditSearchInput = ref('')
const auditQuery = ref('')
const canEditProfile = computed(() => authorization.can('platform.user.profile.write'))
const canEditStatus = computed(() => authorization.can('platform.user.status.write'))
const canAssignRole = computed(() => authorization.can('platform.user.role.write'))
const canResetPassword = computed(() => authorization.can('platform.user.credential.reset'))
const platformRoleOptions: Array<{ value: PlatformRole | ''; label: string }> = [
  { value: '', label: '无平台角色' },
  { value: 'platform_viewer', label: formatPlatformRoleLabel('platform_viewer') },
  { value: 'platform_operator', label: formatPlatformRoleLabel('platform_operator') },
  { value: 'platform_super_admin', label: formatPlatformRoleLabel('platform_super_admin') }
]

const filteredProjects = computed(() => {
  const keyword = projectQuery.value.trim().toLowerCase()
  if (!keyword) {
    return projects.value
  }

  return projects.value.filter((item) => {
    return (
      item.project_name.toLowerCase().includes(keyword) ||
      item.project_description.toLowerCase().includes(keyword) ||
      item.role.toLowerCase().includes(keyword)
    )
  })
})

const filteredAudits = computed(() => {
  const keyword = auditQuery.value.trim().toLowerCase()
  if (!keyword) {
    return audits.value
  }

  return audits.value.filter((item) => {
    const action = item.action?.toLowerCase() || ''
    const path = item.path.toLowerCase()
    const method = item.method.toLowerCase()
    return action.includes(keyword) || path.includes(keyword) || method.includes(keyword)
  })
})

const stats = computed(() => [
  {
    label: '账号',
    value: user.value?.username || '--',
    hint: user.value?.email || '未填写邮箱',
    icon: 'user',
    tone: 'primary'
  },
  {
    label: '状态',
    value: user.value?.status || '--',
    hint: describePlatformRole(user.value),
    icon: 'shield',
    tone: primaryPlatformRole(user.value) === 'platform_super_admin' ? 'warning' : 'success'
  },
  {
    label: '项目访问',
    value: projects.value.length,
    hint: '用户拥有成员关系的项目数',
    icon: 'folder',
    tone: 'info'
  },
  {
    label: '最近审计',
    value: audits.value.length,
    hint: '最近 10 条命中 target_id 的审计记录',
    icon: 'audit',
    tone: 'danger'
  }
])

async function reload() {
  if (!userId.value) {
    user.value = null
    projects.value = []
    audits.value = []
    return
  }

  loading.value = true
  error.value = ''
  notice.value = ''

  try {
    const [userRow, projectsPayload, auditPayload] = await Promise.all([
      getUser(userId.value),
      listUserProjects(userId.value),
      listAudit(null, { limit: 10, offset: 0, targetId: userId.value })
    ])

    user.value = userRow
    projects.value = projectsPayload.items
    audits.value = auditPayload.items
    username.value = userRow.username
    status.value = userRow.status === 'disabled' ? 'disabled' : 'active'
    platformRole.value = primaryPlatformRole(userRow) || ''
  } catch (loadError) {
    user.value = null
    projects.value = []
    audits.value = []
    error.value = loadError instanceof Error ? loadError.message : '用户详情加载失败'
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  if (!user.value) {
    return
  }

  if (!canEditProfile.value && !canEditStatus.value && !canAssignRole.value) {
    error.value = '当前账号没有用户治理写权限'
    return
  }

  const normalizedUsername = username.value.trim()
  if (!normalizedUsername) {
    error.value = '用户名不能为空'
    return
  }

  savingProfile.value = true
  error.value = ''
  notice.value = ''

  try {
    const updated = await updateUser(user.value.id, {
      username: canEditProfile.value ? normalizedUsername : undefined,
      status: canEditStatus.value ? status.value : undefined,
      platform_roles: canAssignRole.value ? (platformRole.value ? [platformRole.value] : []) : undefined,
      is_super_admin: canAssignRole.value ? platformRole.value === 'platform_super_admin' : undefined
    })
    user.value = updated
    platformRole.value = primaryPlatformRole(updated) || ''
    notice.value = '资料已更新'
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : '用户资料更新失败'
  } finally {
    savingProfile.value = false
  }
}

async function updatePassword() {
  if (!user.value) {
    return
  }

  if (!canResetPassword.value) {
    error.value = '当前账号没有用户治理写权限'
    return
  }

  if (newPassword.value.length < 8) {
    error.value = '新密码至少 8 位'
    return
  }

  if (newPassword.value !== confirmNewPassword.value) {
    error.value = '两次输入的新密码不一致'
    return
  }

  updatingPassword.value = true
  error.value = ''
  notice.value = ''

  try {
    user.value = await resetUserPassword(user.value.id, newPassword.value)
    newPassword.value = ''
    confirmNewPassword.value = ''
    notice.value = '密码已更新'
  } catch (updateError) {
    error.value = updateError instanceof Error ? updateError.message : '密码更新失败'
  } finally {
    updatingPassword.value = false
  }
}

function clearPasswordInputs() {
  newPassword.value = ''
  confirmNewPassword.value = ''
}

async function handleCopyValue(label: string, value: string | null | undefined) {
  const normalized = value?.trim() || ''
  const copied = normalized ? await copyText(normalized) : false

  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? `已复制${label}` : '复制失败',
    message: copied ? normalized : `${label} 当前不可复制`
  })
}

watch(
  () => userId.value,
  () => {
    void reload()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Users"
      :title="user ? `${user.username}` : '用户详情'"
      description="用户详情页集中展示资料、状态、密码、项目访问和最近审计，方便在一个入口内完成日常管理。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/users')"
        >
          返回列表
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="!user"
          @click="handleCopyValue('用户 ID', user?.id)"
        >
          <BaseIcon
            name="copy"
            size="sm"
          />
          复制用户 ID
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="用户详情处理失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作已完成"
      :description="notice"
      variant="success"
    />

    <EmptyState
      v-if="!loading && !user"
      icon="users"
      title="未找到这个用户"
      description="当前环境下没有这条用户记录，或者你没有访问它的权限。"
    />

    <template v-else-if="user">
      <div class="grid gap-4 xl:grid-cols-4">
        <MetricCard
          v-for="itemStat in stats"
          :key="itemStat.label"
          :label="itemStat.label"
          :value="itemStat.value"
          :hint="itemStat.hint"
          :icon="itemStat.icon"
          :tone="itemStat.tone"
        />
      </div>

      <div class="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
        <div class="space-y-6">
          <SurfaceCard class="space-y-5">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="text-lg font-semibold text-gray-900 dark:text-white">
                  资料信息
                </div>
                <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                  对应旧版 User Detail 的基础资料编辑区。
                </div>
              </div>
              <StatusPill :tone="primaryPlatformRole(user) === 'platform_super_admin' ? 'warning' : 'info'">
                {{ describePlatformRole(user) }}
              </StatusPill>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="pw-input-label">用户名</span>
                <input
                  v-model="username"
                  class="pw-input"
                  :disabled="savingProfile || !canEditProfile"
                >
              </label>
              <label class="block">
                <span class="pw-input-label">状态</span>
                <BaseSelect
                  v-model="status"
                  :disabled="savingProfile || !canEditStatus"
                >
                  <option value="active">active</option>
                  <option value="disabled">disabled</option>
                </BaseSelect>
              </label>
            </div>

            <label class="block">
              <span class="pw-input-label">平台角色</span>
              <BaseSelect
                v-model="platformRole"
                :disabled="savingProfile || !canAssignRole"
                :options="platformRoleOptions"
              />
            </label>

            <div class="grid gap-4 md:grid-cols-2">
              <div class="pw-card-glass p-4">
                <div class="text-xs text-gray-400 dark:text-dark-400">
                  邮箱
                </div>
                <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                  {{ user.email || '--' }}
                </div>
              </div>
              <div class="pw-card-glass p-4">
                <div class="text-xs text-gray-400 dark:text-dark-400">
                  用户 ID
                </div>
                <div class="mt-2 break-all text-sm font-semibold text-gray-900 dark:text-white">
                  {{ user.id }}
                </div>
              </div>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <div class="pw-card-glass p-4">
                <div class="text-xs text-gray-400 dark:text-dark-400">
                  创建时间
                </div>
                <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                  {{ user.created_at ? formatDateTime(user.created_at) : '--' }}
                </div>
              </div>
              <div class="pw-card-glass p-4">
                <div class="text-xs text-gray-400 dark:text-dark-400">
                  更新时间
                </div>
                <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                  {{ user.updated_at ? formatDateTime(user.updated_at) : '--' }}
                </div>
              </div>
            </div>

            <div class="flex justify-end">
              <BaseButton
                :disabled="savingProfile || (!canEditProfile && !canEditStatus && !canAssignRole)"
                @click="saveProfile"
              >
                {{ (canEditProfile || canEditStatus || canAssignRole) ? (savingProfile ? '保存中...' : '保存资料') : '当前账号只读' }}
              </BaseButton>
            </div>
          </SurfaceCard>

          <SurfaceCard class="space-y-5">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                安全与密码
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                这里承接旧版的密码更新链路。
              </div>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="pw-input-label">新密码</span>
                <input
                  v-model="newPassword"
                  type="password"
                  class="pw-input"
                  :disabled="updatingPassword || !canResetPassword"
                >
              </label>
              <label class="block">
                <span class="pw-input-label">确认新密码</span>
                <input
                  v-model="confirmNewPassword"
                  type="password"
                  class="pw-input"
                  :disabled="updatingPassword || !canResetPassword"
                >
              </label>
            </div>

            <div class="flex flex-wrap justify-end gap-3">
              <BaseButton
                variant="secondary"
                :disabled="updatingPassword || !canResetPassword"
                @click="clearPasswordInputs"
              >
                清空
              </BaseButton>
              <BaseButton
                :disabled="updatingPassword || !canResetPassword"
                @click="updatePassword"
              >
                {{ canResetPassword ? (updatingPassword ? '更新中...' : '重置密码') : '当前账号无凭据重置权限' }}
              </BaseButton>
            </div>
          </SurfaceCard>
        </div>

        <div class="space-y-6">
          <SurfaceCard class="space-y-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <div class="text-lg font-semibold text-gray-900 dark:text-white">
                  项目访问
                </div>
                <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                  这个用户当前拥有哪些项目成员关系。
                </div>
              </div>
            </div>

            <SearchInput
              v-model="projectSearchInput"
              placeholder="搜索项目访问"
            />

            <div class="flex justify-end">
              <BaseButton
                variant="secondary"
                @click="projectQuery = projectSearchInput.trim()"
              >
                应用搜索
              </BaseButton>
            </div>

            <div
              v-if="filteredProjects.length === 0"
              class="rounded-2xl border border-dashed border-gray-200 px-4 py-5 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
            >
              当前没有项目访问记录。
            </div>

            <div
              v-else
              class="space-y-3"
            >
              <div
                v-for="projectItem in filteredProjects"
                :key="projectItem.project_id"
                class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-dark-700 dark:bg-dark-900/70"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                      {{ projectItem.project_name }}
                    </div>
                    <div class="mt-1 break-all text-xs text-gray-500 dark:text-dark-300">
                      {{ projectItem.project_id }}
                    </div>
                    <div class="mt-2 text-sm leading-7 text-gray-600 dark:text-dark-200">
                      {{ projectItem.project_description || '暂无描述' }}
                    </div>
                  </div>
                  <div class="flex flex-col items-end gap-2">
                    <StatusPill :tone="getRoleTone(projectItem.role)">
                      {{ formatProjectRoleLabel(projectItem.role) }}
                    </StatusPill>
                    <StatusPill :tone="projectItem.project_status === 'active' ? 'success' : 'warning'">
                      {{ projectItem.project_status }}
                    </StatusPill>
                  </div>
                </div>
                <div class="mt-2 text-xs text-gray-400 dark:text-dark-400">
                  加入时间：{{ formatDateTime(projectItem.joined_at) }}
                </div>
              </div>
            </div>
          </SurfaceCard>

          <SurfaceCard class="space-y-4">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                最近审计
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                取最近 10 条命中当前用户 `target_id` 的审计记录。
              </div>
            </div>

            <SearchInput
              v-model="auditSearchInput"
              placeholder="搜索审计记录"
            />

            <div class="flex justify-end">
              <BaseButton
                variant="secondary"
                @click="auditQuery = auditSearchInput.trim()"
              >
                应用搜索
              </BaseButton>
            </div>

            <div
              v-if="filteredAudits.length === 0"
              class="rounded-2xl border border-dashed border-gray-200 px-4 py-5 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
            >
              当前没有匹配的审计记录。
            </div>

            <div
              v-else
              class="space-y-3"
            >
              <div
                v-for="audit in filteredAudits"
                :key="audit.id"
                class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-dark-700 dark:bg-dark-900/70"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      {{ audit.action || 'unknown' }}
                    </div>
                    <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                      {{ audit.method }} · {{ audit.path }}
                    </div>
                    <div class="mt-2 text-xs text-gray-400 dark:text-dark-400">
                      {{ formatDateTime(audit.created_at) }} · request {{ shortId(audit.request_id) }}
                    </div>
                  </div>
                  <StatusPill :tone="getStatusTone(audit.status_code)">
                    {{ audit.status_code }}
                  </StatusPill>
                </div>
              </div>
            </div>

            <div class="flex justify-end">
              <BaseButton
                variant="secondary"
                @click="handleCopyValue('用户 ID', user.id)"
              >
                <BaseIcon
                  name="copy"
                  size="sm"
                />
                再复制一次用户 ID
              </BaseButton>
            </div>
          </SurfaceCard>
        </div>
      </div>
    </template>
  </section>
</template>
