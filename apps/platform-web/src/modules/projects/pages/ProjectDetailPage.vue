<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { formatProjectRoleLabel, isProjectAdminRole, isProjectEditorRole } from '@/services/auth/permissions'
import {
  archiveProject,
  deleteProject,
  restoreProjectAdmin,
  restoreProject,
  takeoverProject
} from '@/services/projects/projects.service'
import { listProjectMembers } from '@/services/members/members.service'
import { useUiStore } from '@/stores/ui'
import type { ManagementProjectMember, ProjectRole } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { shortId } from '@/utils/format'

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
const { workspaceStore, activeProjectId, activeProjects, setActiveProjectId } = useWorkspaceProjectContext()
const uiStore = useUiStore()
const authorization = useAuthorization()

const projectId = computed(() =>
  typeof route.params.projectId === 'string' ? route.params.projectId.trim() : ''
)

const project = computed(() =>
  activeProjects.value.find((item) => item.id === projectId.value) ?? null
)

const members = ref<ManagementProjectMember[]>([])
const loadingMembers = ref(false)
const membersError = ref('')
const deletingProject = ref(false)
const showDeleteDialog = ref(false)
const lifecycleDialogOpen = ref(false)
const lifecycleAction = ref<'archive' | 'restore'>('archive')
const takeoverDialogOpen = ref(false)
const recoveryDialogOpen = ref(false)
const governingProject = ref(false)
const takeoverReason = ref('')
const recoveryUserId = ref('')
const canManageProject = computed(() => authorization.can('platform.project.write'))
const canTakeoverProject = computed(() => authorization.can('platform.project.takeover'))
const canReadMembers = computed(() => authorization.currentProjectCan('project.member.read'))
const canReadKnowledge = computed(() => authorization.currentProjectCan('project.knowledge.read'))
const canReadAudit = computed(() =>
  authorization.can('platform.audit.read') || authorization.currentProjectCan('project.audit.read')
)

const stats = computed(() => [
  {
    label: '项目名称',
    value: project.value?.name || '未找到',
    hint: project.value?.id || '--',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '成员数量',
    value: members.value.length,
    hint: '来自项目成员接口',
    icon: 'users',
    tone: 'success'
  },
  {
    label: '管理员',
    value: members.value.filter((item) => isProjectAdminRole(item.role)).length,
    hint: '当前项目管理员角色成员',
    icon: 'shield',
    tone: 'warning'
  },
  {
    label: '当前工作区',
    value: activeProjectId.value === project.value?.id ? '已对齐' : '未对齐',
    hint:
      activeProjectId.value === project.value?.id
        ? '当前工作区已指向本项目'
        : '可在这里切换工作区项目',
    icon: 'project',
    tone: 'danger'
  }
])

async function handleCopyProjectId() {
  if (!project.value) {
    return
  }

  const copied = await copyText(project.value.id)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制项目 ID' : '复制失败',
    message: copied ? project.value.id : '当前环境不支持自动复制，请手动复制。'
  })
}

async function focusProject() {
  if (!project.value) {
    return
  }

  await setActiveProjectId(project.value.id)
  uiStore.pushToast({
    type: 'success',
    title: '已切换当前项目',
    message: project.value.name
  })
}

async function openAudit() {
  if (!project.value || !canReadAudit.value) {
    return
  }

  await setActiveProjectId(project.value.id)
  void router.push('/workspace/audit')
}

async function openKnowledgeWorkspace() {
  if (!project.value || !canReadKnowledge.value) {
    return
  }

  await setActiveProjectId(project.value.id)
  void router.push(`/workspace/projects/${project.value.id}/knowledge/documents`)
}

async function refreshProjectAccess() {
  if (!project.value) {
    return
  }
  await setActiveProjectId(project.value.id)
  await loadMembers()
}

async function confirmTakeoverProject() {
  if (!project.value || !takeoverReason.value.trim() || !canTakeoverProject.value) {
    return
  }

  governingProject.value = true
  membersError.value = ''
  try {
    await takeoverProject(project.value.id, takeoverReason.value)
    takeoverDialogOpen.value = false
    takeoverReason.value = ''
    await refreshProjectAccess()
    uiStore.pushToast({
      type: 'success',
      title: '项目接管完成',
      message: `你已成为 ${project.value.name} 的项目管理员`
    })
  } catch (takeoverError) {
    membersError.value = takeoverError instanceof Error ? takeoverError.message : '项目接管失败'
  } finally {
    governingProject.value = false
  }
}

async function confirmRestoreProjectAdmin() {
  if (!project.value || !recoveryUserId.value.trim() || !canManageProject.value) {
    return
  }

  governingProject.value = true
  membersError.value = ''
  try {
    await restoreProjectAdmin(project.value.id, recoveryUserId.value.trim())
    recoveryDialogOpen.value = false
    recoveryUserId.value = ''
    await loadMembers()
    uiStore.pushToast({
      type: 'success',
      title: '项目管理员已恢复',
      message: project.value.name
    })
  } catch (recoveryError) {
    membersError.value = recoveryError instanceof Error ? recoveryError.message : '项目管理员恢复失败'
  } finally {
    governingProject.value = false
  }
}

function openLifecycleDialog(action: 'archive' | 'restore') {
  if (!project.value || !canManageProject.value) {
    return
  }
  lifecycleAction.value = action
  lifecycleDialogOpen.value = true
}

async function confirmProjectLifecycle() {
  if (!project.value || !canManageProject.value) {
    return
  }

  governingProject.value = true
  membersError.value = ''
  try {
    if (lifecycleAction.value === 'archive') {
      await archiveProject(project.value.id)
    } else {
      await restoreProject(project.value.id)
    }
    lifecycleDialogOpen.value = false
    await workspaceStore.hydrateContext()
    uiStore.pushToast({
      type: 'success',
      title: lifecycleAction.value === 'archive' ? '项目已归档' : '项目已恢复',
      message: project.value?.name || projectId.value
    })
  } catch (lifecycleError) {
    membersError.value = lifecycleError instanceof Error ? lifecycleError.message : '项目生命周期更新失败'
  } finally {
    governingProject.value = false
  }
}

async function loadMembers() {
  if (!projectId.value || !canReadMembers.value) {
    members.value = []
    membersError.value = ''
    return
  }

  loadingMembers.value = true
  membersError.value = ''

  try {
    members.value = await listProjectMembers(projectId.value)
  } catch (loadError) {
    members.value = []
    membersError.value =
      loadError instanceof Error ? loadError.message : '项目成员加载失败'
  } finally {
    loadingMembers.value = false
  }
}

function openDeleteDialog() {
  if (!project.value || !canManageProject.value) {
    return
  }

  showDeleteDialog.value = true
}

function closeDeleteDialog() {
  showDeleteDialog.value = false
}

async function confirmDeleteProject() {
  if (!project.value) {
    closeDeleteDialog()
    return
  }

  deletingProject.value = true
  membersError.value = ''

  try {
    await deleteProject(project.value.id)
    if (activeProjectId.value === project.value.id) {
      setActiveProjectId('')
    }
    await workspaceStore.hydrateContext()
    uiStore.pushToast({
      type: 'success',
      title: '项目已删除',
      message: project.value.name
    })
    closeDeleteDialog()
    await router.replace('/workspace/projects')
  } catch (deleteError) {
    membersError.value = deleteError instanceof Error ? deleteError.message : '项目删除失败'
  } finally {
    deletingProject.value = false
  }
}

watch(
  () => projectId.value,
  () => {
    void loadMembers()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Projects"
      :title="project?.name || '项目详情'"
      description="项目详情页负责承接正式项目信息、成员预览、工作区切换与删除治理，不再伪装不存在的编辑能力。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/projects')"
        >
          返回列表
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="!project || !canReadKnowledge"
          @click="handleCopyProjectId"
        >
          <BaseIcon
            name="copy"
            size="sm"
          />
          复制项目 ID
        </BaseButton>
        <BaseButton
          :disabled="!project"
          @click="focusProject"
        >
          <BaseIcon
            name="project"
            size="sm"
          />
          设为当前项目
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="!project"
          @click="openKnowledgeWorkspace"
        >
          <BaseIcon
            name="file"
            size="sm"
          />
          知识库工作台
        </BaseButton>
        <BaseButton
          v-if="canTakeoverProject"
          variant="secondary"
          :disabled="!project || project.status !== 'active' || governingProject"
          @click="takeoverDialogOpen = true"
        >
          接管项目
        </BaseButton>
        <BaseButton
          v-if="canManageProject"
          variant="secondary"
          :disabled="!project || project.status !== 'active' || governingProject"
          @click="recoveryDialogOpen = true"
        >
          恢复管理员
        </BaseButton>
        <BaseButton
          v-if="canManageProject && project?.status === 'active'"
          variant="secondary"
          :disabled="governingProject"
          @click="openLifecycleDialog('archive')"
        >
          归档项目
        </BaseButton>
        <BaseButton
          v-if="canManageProject && project?.status === 'disabled'"
          variant="secondary"
          :disabled="governingProject"
          @click="openLifecycleDialog('restore')"
        >
          恢复项目
        </BaseButton>
        <BaseButton
          v-if="canManageProject"
          variant="danger"
          :disabled="!project || deletingProject"
          @click="openDeleteDialog"
        >
          {{ deletingProject ? '删除中...' : '删除项目' }}
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
        v-if="membersError"
        title="项目成员加载失败"
        :description="membersError"
        variant="warning"
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

      <div class="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
        <SurfaceCard class="space-y-5">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                基础信息
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                旧版这里本来就是项目级入口，不承担复杂编辑。Vue 版保持这个口径，但把信息密度和入口动作做完整。
              </div>
            </div>
            <StatusPill tone="success">
              {{ project.status }}
            </StatusPill>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <div class="pw-card-glass p-4">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                项目 ID
              </div>
              <div class="mt-2 break-all text-sm font-semibold text-gray-900 dark:text-white">
                {{ project.id }}
              </div>
            </div>
            <div class="pw-card-glass p-4">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                短标识
              </div>
              <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                {{ shortId(project.id) }}
              </div>
            </div>
          </div>

          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              项目名称
            </div>
            <div class="mt-2 text-base font-semibold text-gray-900 dark:text-white">
              {{ project.name }}
            </div>
          </div>

          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              项目描述
            </div>
            <div class="mt-2 whitespace-pre-wrap text-sm leading-7 text-gray-700 dark:text-dark-100">
              {{ project.description || '暂无描述' }}
            </div>
          </div>

          <div class="flex flex-wrap gap-3">
            <BaseButton
              variant="secondary"
              :disabled="!canReadMembers"
              @click="void router.push(`/workspace/projects/${projectId}/members`)"
            >
              <BaseIcon
                name="users"
                size="sm"
              />
              成员管理
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="!canReadAudit"
              @click="openAudit"
            >
              <BaseIcon
                name="audit"
                size="sm"
              />
              查看审计
            </BaseButton>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                成员预览
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                后续正式成员管理页会在这里继续展开。
              </div>
            </div>
            <BaseButton
              variant="ghost"
              :disabled="loadingMembers || !canReadMembers"
              @click="loadMembers"
            >
              <BaseIcon
                name="refresh"
                size="sm"
              />
              刷新成员
            </BaseButton>
          </div>

          <div
            v-if="loadingMembers"
            class="space-y-3"
          >
            <div
              v-for="index in 3"
              :key="index"
              class="pw-card-glass h-20 animate-pulse"
            />
          </div>

          <EmptyState
            v-else-if="members.length === 0"
            icon="users"
            title="当前没有可展示的成员"
            :description="canReadMembers
              ? '如果这是新项目，成员列表可能还没建立；可进入成员管理页继续治理。'
              : '平台治理权限不等于项目成员权限；接管项目后才可查看项目成员和内容。'"
          />

          <div
            v-else
            class="space-y-3"
          >
            <div
              v-for="member in members"
              :key="member.user_id"
              class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-dark-700 dark:bg-dark-900/70"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                    {{ member.username }}
                  </div>
                  <div class="mt-1 break-all text-xs text-gray-500 dark:text-dark-300">
                    {{ member.user_id }}
                  </div>
                </div>
                <StatusPill :tone="getRoleTone(member.role)">
                  {{ formatProjectRoleLabel(member.role) }}
                </StatusPill>
              </div>
            </div>
          </div>
        </SurfaceCard>
      </div>

      <ConfirmDialog
        :show="showDeleteDialog"
        title="删除项目"
        :message="project ? `删除后项目 ${project.name} 将进入删除态，确认继续吗？` : ''"
        confirm-text="确认删除"
        cancel-text="取消"
        danger
        @cancel="closeDeleteDialog"
        @confirm="confirmDeleteProject"
      />

      <BaseDialog
        :show="takeoverDialogOpen"
        title="接管项目"
        width="normal"
        @close="takeoverDialogOpen = false"
      >
        <div class="space-y-4">
          <p class="text-sm leading-6 text-gray-600 dark:text-dark-200">
            接管后你会成为显式项目管理员，并获得项目内容权限。原因会写入审计记录。
          </p>
          <label class="block space-y-2">
            <span class="text-sm font-medium text-gray-700 dark:text-dark-100">接管原因</span>
            <BaseInput
              v-model="takeoverReason"
              placeholder="请输入非空接管原因"
            />
          </label>
        </div>
        <template #footer>
          <div class="flex gap-3">
            <BaseButton
              variant="secondary"
              @click="takeoverDialogOpen = false"
            >
              取消
            </BaseButton>
            <BaseButton
              :disabled="governingProject || !takeoverReason.trim()"
              @click="confirmTakeoverProject"
            >
              {{ governingProject ? '接管中...' : '确认接管' }}
            </BaseButton>
          </div>
        </template>
      </BaseDialog>

      <BaseDialog
        :show="recoveryDialogOpen"
        title="恢复项目管理员"
        width="normal"
        @close="recoveryDialogOpen = false"
      >
        <div class="space-y-4">
          <p class="text-sm leading-6 text-gray-600 dark:text-dark-200">
            输入活动用户 ID，将其新增或提升为本项目管理员。
          </p>
          <label class="block space-y-2">
            <span class="text-sm font-medium text-gray-700 dark:text-dark-100">用户 ID</span>
            <BaseInput
              v-model="recoveryUserId"
              placeholder="请输入用户 UUID"
            />
          </label>
        </div>
        <template #footer>
          <div class="flex gap-3">
            <BaseButton
              variant="secondary"
              @click="recoveryDialogOpen = false"
            >
              取消
            </BaseButton>
            <BaseButton
              :disabled="governingProject || !recoveryUserId.trim()"
              @click="confirmRestoreProjectAdmin"
            >
              {{ governingProject ? '恢复中...' : '确认恢复' }}
            </BaseButton>
          </div>
        </template>
      </BaseDialog>

      <ConfirmDialog
        :show="lifecycleDialogOpen"
        :title="lifecycleAction === 'archive' ? '归档项目' : '恢复项目'"
        :message="lifecycleAction === 'archive'
          ? '归档后项目内容和机器身份访问会立即停止，确认继续吗？'
          : '恢复后项目成员和有效服务账号授权会重新生效，确认继续吗？'"
        :confirm-text="lifecycleAction === 'archive' ? '确认归档' : '确认恢复'"
        cancel-text="取消"
        :danger="lifecycleAction === 'archive'"
        @cancel="lifecycleDialogOpen = false"
        @confirm="confirmProjectLifecycle"
      />
    </template>
  </section>
</template>
