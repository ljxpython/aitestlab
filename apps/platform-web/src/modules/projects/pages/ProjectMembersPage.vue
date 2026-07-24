<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import {
  deleteProjectMember,
  listProjectMemberCandidates,
  listProjectMembers,
  upsertProjectMember
} from '@/services/members/members.service'
import type { ManagementProjectMember, ProjectMemberCandidate, ProjectRole } from '@/types/management'
import { formatProjectRoleLabel, isProjectAdminRole, isProjectEditorRole } from '@/services/auth/permissions'

function getRoleTone(role: string): 'info' | 'success' | 'warning' {
  if (isProjectAdminRole(role as ProjectRole)) {
    return 'warning'
  }
  if (isProjectEditorRole(role as ProjectRole)) {
    return 'info'
  }
  return 'success'
}

const route = useRoute()
const router = useRouter()
const { activeProjects } = useWorkspaceProjectContext()
const authorization = useAuthorization()

const projectId = computed(() =>
  typeof route.params.projectId === 'string' ? route.params.projectId.trim() : ''
)
const project = computed(() =>
  activeProjects.value.find((item) => item.id === projectId.value) ?? null
)

const items = ref<ManagementProjectMember[]>([])
const memberQuery = ref('')
const memberSearchInput = ref('')
const userId = ref('')
const userSearch = ref('')
const userCandidates = ref<ProjectMemberCandidate[]>([])
const searchingUsers = ref(false)
const role = ref<ProjectRole>('project_executor')
const loading = ref(false)
const saving = ref(false)
const removingUserId = ref('')
const pendingDeleteMember = ref<ManagementProjectMember | null>(null)
const error = ref('')
const notice = ref('')

const adminCount = computed(() => items.value.filter((item) => isProjectAdminRole(item.role)).length)
const targetExistingMember = computed(() =>
  items.value.find((item) => item.user_id === userId.value.trim())
)
const downgradeLastAdminBlocked = computed(
  () =>
    isProjectAdminRole(targetExistingMember.value?.role) &&
    !isProjectAdminRole(role.value) &&
    adminCount.value <= 1
)
const canManageMembers = computed(() => authorization.currentProjectCan('project.member.write'))
const roleOptions: Array<{ value: ProjectRole; label: string }> = [
  { value: 'project_admin', label: formatProjectRoleLabel('project_admin') },
  { value: 'project_editor', label: formatProjectRoleLabel('project_editor') },
  { value: 'project_executor', label: formatProjectRoleLabel('project_executor') }
]

const stats = computed(() => [
  {
    label: '项目',
    value: project.value?.name || '未找到',
    hint: project.value?.id || '--',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '成员数量',
    value: items.value.length,
    hint: memberQuery.value ? `筛选：${memberQuery.value}` : '当前项目全部成员',
    icon: 'users',
    tone: 'success'
  },
  {
    label: '管理员',
    value: adminCount.value,
    hint: adminCount.value <= 1 ? '最后一个项目管理员受保护' : '可正常调整',
    icon: 'shield',
    tone: 'warning'
  },
  {
    label: '候选用户',
    value: userCandidates.value.length,
    hint: searchingUsers.value ? '搜索中...' : '按用户名搜索可添加成员',
    icon: 'search',
    tone: 'danger'
  }
])

async function refreshMembers() {
  if (!projectId.value) {
    items.value = []
    error.value = ''
    return
  }

  loading.value = true
  error.value = ''

  try {
    items.value = await listProjectMembers(
      projectId.value,
      { query: memberQuery.value }
    )
  } catch (loadError) {
    items.value = []
    error.value = loadError instanceof Error ? loadError.message : '项目成员加载失败'
  } finally {
    loading.value = false
  }
}

async function saveMember() {
  if (!projectId.value) {
    return
  }

  if (!userId.value.trim()) {
    error.value = '请输入用户 ID 或从候选用户中选择'
    return
  }

  if (downgradeLastAdminBlocked.value) {
    error.value = '不能降级最后一个项目管理员'
    return
  }

  saving.value = true
  error.value = ''
  notice.value = ''

  try {
    const row = await upsertProjectMember({
      projectId: projectId.value,
      userId: userId.value.trim(),
      role: role.value
    })
    notice.value = `已保存成员：${row.username}`
    userId.value = ''
    userSearch.value = ''
    await refreshMembers()
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : '成员保存失败'
  } finally {
    saving.value = false
  }
}

async function confirmDelete(member: ManagementProjectMember) {
  removingUserId.value = member.user_id
  error.value = ''
  notice.value = ''

  try {
    await deleteProjectMember(projectId.value, member.user_id)
    notice.value = `已移除成员：${member.username}`
    await refreshMembers()
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : '成员移除失败'
  } finally {
    pendingDeleteMember.value = null
    removingUserId.value = ''
  }
}

function selectCandidate(candidate: ProjectMemberCandidate) {
  userId.value = candidate.user_id
  userSearch.value = candidate.username
}

function resetMemberFilter() {
  memberSearchInput.value = ''
  memberQuery.value = ''
  void refreshMembers()
}

function applyMemberFilter() {
  memberQuery.value = memberSearchInput.value.trim()
  void refreshMembers()
}

watch(
  () => projectId.value,
  () => {
    void refreshMembers()
  },
  { immediate: true }
)

watch(
  () => userSearch.value,
  (nextValue, _, onCleanup) => {
    if (!nextValue.trim()) {
      userCandidates.value = []
      return
    }

    let cancelled = false
    const timerId = window.setTimeout(async () => {
      searchingUsers.value = true
      try {
        const payload = await listProjectMemberCandidates(projectId.value, {
          limit: 20,
          offset: 0,
          query: nextValue
        })
        if (!cancelled) {
          userCandidates.value = payload.items
        }
      } catch {
        if (!cancelled) {
          userCandidates.value = []
        }
      } finally {
        if (!cancelled) {
          searchingUsers.value = false
        }
      }
    }, 300)

    onCleanup(() => {
      cancelled = true
      window.clearTimeout(timerId)
    })
  }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Projects"
      :title="project ? `${project.name} · 成员管理` : '项目成员管理'"
      description="项目成员页负责搜索候选用户、设置项目角色、保护最后一个管理员并支持移除成员。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push(`/workspace/projects/${projectId}`)"
        >
          返回项目详情
        </BaseButton>
      </template>
    </PageHeader>

    <EmptyState
      v-if="!project"
      icon="folder"
      title="未找到这个项目"
      description="当前工作区没有这条项目记录，或者你没有访问它的权限。"
    />

    <template v-else>
      <StateBanner
        v-if="error"
        title="项目成员操作失败"
        :description="error"
        variant="danger"
      />

      <StateBanner
        v-if="notice"
        title="操作已完成"
        :description="notice"
        variant="success"
      />

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

      <div class="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.2fr)]">
        <SurfaceCard class="space-y-5">
          <div>
            <div class="text-lg font-semibold text-gray-900 dark:text-white">
              成员表单
            </div>
            <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
              支持直接输入用户 ID，也支持按用户名搜索候选用户。
            </div>
          </div>

          <div class="space-y-3">
            <label class="block">
              <span class="pw-input-label">搜索用户名</span>
              <input
                v-model="userSearch"
                class="pw-input"
                placeholder="输入用户名搜索"
              >
            </label>

            <div
              v-if="searchingUsers"
              class="text-xs text-gray-400 dark:text-dark-400"
            >
              正在搜索用户...
            </div>

            <div
              v-else-if="userCandidates.length > 0"
              class="max-h-56 space-y-2 overflow-auto rounded-2xl border border-gray-100 bg-gray-50/70 p-3 dark:border-dark-700 dark:bg-dark-900/60"
            >
              <button
                v-for="candidate in userCandidates"
                :key="candidate.user_id"
                type="button"
                class="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition hover:bg-white dark:hover:bg-dark-800"
                @click="selectCandidate(candidate)"
              >
                <span class="font-medium text-gray-900 dark:text-white">{{ candidate.username }}</span>
                <span class="font-mono text-[11px] text-gray-400 dark:text-dark-400">{{ candidate.user_id }}</span>
              </button>
            </div>
          </div>

          <label class="block">
            <span class="pw-input-label">用户 ID</span>
            <input
              v-model="userId"
              class="pw-input"
              placeholder="支持手动输入用户 ID"
            >
          </label>

          <label class="block">
            <span class="pw-input-label">角色</span>
            <BaseSelect
              v-model="role"
              :disabled="!canManageMembers"
            >
              <option
                v-for="item in roleOptions"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </option>
            </BaseSelect>
          </label>

          <div
            v-if="downgradeLastAdminBlocked"
            class="rounded-2xl border border-amber-100 bg-amber-50/80 px-4 py-4 text-sm leading-7 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-100"
          >
            当前项目的最后一个管理员不能被降级。
          </div>

          <div class="flex justify-end">
            <BaseButton
              :disabled="saving || !canManageMembers"
              @click="saveMember"
            >
              <BaseIcon
                name="check"
                size="sm"
              />
              {{ canManageMembers ? (saving ? '保存中...' : '保存成员') : '当前账号不可写' }}
            </BaseButton>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-5">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                当前成员
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                支持按用户名筛选，删除时会做最后一个项目管理员保护。
              </div>
            </div>
            <BaseButton
              variant="secondary"
              :disabled="loading"
              @click="refreshMembers"
            >
              <BaseIcon
                name="refresh"
                size="sm"
              />
              刷新
            </BaseButton>
          </div>

          <SearchInput
            v-model="memberSearchInput"
            placeholder="按用户名筛选成员"
          />

          <div class="flex justify-end gap-3">
            <BaseButton
              variant="secondary"
              @click="resetMemberFilter"
            >
              重置
            </BaseButton>
            <BaseButton
              @click="applyMemberFilter"
            >
              应用筛选
            </BaseButton>
          </div>

          <div
            v-if="loading"
            class="space-y-3"
          >
            <div
              v-for="index in 4"
              :key="index"
              class="pw-card-glass h-20 animate-pulse"
            />
          </div>

          <EmptyState
            v-else-if="items.length === 0"
            icon="users"
            title="当前没有成员记录"
            description="可以直接在左侧表单里添加第一个成员。"
          />

          <div
            v-else
            class="space-y-3"
          >
            <div
              v-for="(member, index) in items"
              :key="member.user_id"
              class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-dark-700 dark:bg-dark-900/70"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="text-xs text-gray-400 dark:text-dark-400">
                    #{{ index + 1 }}
                  </div>
                  <div class="mt-1 truncate text-sm font-semibold text-gray-900 dark:text-white">
                    {{ member.username }}
                  </div>
                  <div class="mt-1 break-all text-xs text-gray-500 dark:text-dark-300">
                    {{ member.user_id }}
                  </div>
                </div>
                <div class="flex flex-col items-end gap-2">
                  <StatusPill :tone="getRoleTone(member.role)">
                    {{ formatProjectRoleLabel(member.role) }}
                  </StatusPill>
                  <BaseButton
                    variant="danger"
                    :disabled="(!canManageMembers) || (isProjectAdminRole(member.role) && adminCount <= 1) || removingUserId === member.user_id"
                    @click="pendingDeleteMember = member"
                  >
                    {{
                      !canManageMembers
                        ? '当前账号不可写'
                        : isProjectAdminRole(member.role) && adminCount <= 1
                          ? '最后一个管理员'
                          : removingUserId === member.user_id
                            ? '移除中...'
                            : '移除'
                    }}
                  </BaseButton>
                </div>
              </div>
            </div>
          </div>
        </SurfaceCard>
      </div>

      <ConfirmDialog
        :show="pendingDeleteMember !== null"
        title="移除项目成员"
        :message="pendingDeleteMember ? `确认将 ${pendingDeleteMember.username} 移出当前项目吗？` : ''"
        confirm-text="移除"
        danger
        @cancel="pendingDeleteMember = null"
        @confirm="pendingDeleteMember && confirmDelete(pendingDeleteMember)"
      />
    </template>
  </section>
</template>
