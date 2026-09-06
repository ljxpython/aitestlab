<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import { appMeta } from '@/config/app-meta'
import BrandMark from '@/components/layout/BrandMark.vue'
import { useThemeStore } from '@/stores/theme'
import { useUiStore } from '@/stores/ui'
import type { PermissionCode } from '@/types/management'

const route = useRoute()
const { t } = useI18n()
const uiStore = useUiStore()
const themeStore = useThemeStore()
const isDev = import.meta.env.DEV
const authorization = useAuthorization()
const { activeProjectId } = useWorkspaceProjectContext()

type SidebarItem = {
  to: string
  label: string
  icon: string
  sectionTitle?: string
  exact?: boolean
  requiredPermissions?: PermissionCode[]
  permissionMode?: 'all' | 'any'
}

type SidebarGroup = {
  id: string
  label: string
  items: SidebarItem[]
}

const groups = computed(() => {
  const resolveKnowledgePath = (suffix: 'documents' | 'retrieval' | 'graph' | 'settings') =>
    activeProjectId.value
      ? `/workspace/projects/${activeProjectId.value}/knowledge/${suffix}`
      : '/workspace/projects'
  const baseGroups: SidebarGroup[] = [
    {
      id: 'workspace',
      label: 'Workspace',
      items: [
        { to: '/workspace/overview', label: t('nav.overview'), icon: 'overview' },
        { to: '/workspace/projects', label: t('nav.projects'), icon: 'folder' },
        {
          to: '/workspace/users',
          label: t('nav.users'),
          icon: 'users',
          requiredPermissions: ['platform.user.read']
        }
      ]
    },
    {
      id: 'agent',
      label: 'Agent Workspace',
      items: [
        {
          to: '/workspace/assistants',
          label: t('nav.assistants'),
          icon: 'assistant',
          requiredPermissions: ['project.assistant.read']
        },
        {
          to: '/workspace/models',
          label: 'Models',
          icon: 'runtime',
          requiredPermissions: ['project.runtime.read']
        },
        {
          to: '/workspace/chat',
          label: t('nav.chat'),
          icon: 'chat',
          requiredPermissions: ['project.runtime.read']
        },
        {
          to: '/workspace/threads',
          label: t('nav.threads'),
          icon: 'threads',
          requiredPermissions: ['project.runtime.read']
        },
        {
          to: '/workspace/sql-agent',
          label: t('nav.sqlAgent'),
          icon: 'sql-agent',
          sectionTitle: t('nav.agentApps'),
          requiredPermissions: ['project.runtime.read']
        },
        {
          to: '/workspace/testcase',
          label: t('nav.testcase'),
          icon: 'testcase',
          requiredPermissions: ['project.testcase.read']
        },
        {
          to: '/workspace/testcase-v2',
          label: 'Testcase V2',
          icon: 'testcase',
          requiredPermissions: ['project.testcase.read']
        }
      ]
    },
    {
      id: 'knowledge',
      label: 'Knowledge',
      items: [
        {
          to: resolveKnowledgePath('documents'),
          label: '知识文档',
          icon: 'file',
          requiredPermissions: ['project.knowledge.read']
        },
        {
          to: resolveKnowledgePath('retrieval'),
          label: '知识检索',
          icon: 'search',
          requiredPermissions: ['project.knowledge.read']
        },
        {
          to: resolveKnowledgePath('graph'),
          label: '知识图谱',
          icon: 'graph',
          requiredPermissions: ['project.knowledge.read']
        },
        {
          to: resolveKnowledgePath('settings'),
          label: '知识设置',
          icon: 'shield',
          requiredPermissions: ['project.knowledge.read']
        }
      ]
    },
    {
      id: 'governance',
      label: 'Governance',
      items: [
        {
          to: '/workspace/control-plane',
          label: t('nav.controlPlane'),
          icon: 'overview',
          requiredPermissions: ['platform.config.read']
        },
        {
          to: '/workspace/operations',
          label: t('nav.operations'),
          icon: 'activity',
          requiredPermissions: ['platform.operation.read', 'project.operation.read'],
          permissionMode: 'any'
        },
        {
          to: '/workspace/announcements',
          label: t('nav.announcements'),
          icon: 'bell',
          requiredPermissions: ['platform.announcement.write', 'project.announcement.write'],
          permissionMode: 'any'
        },
        {
          to: '/workspace/platform-config',
          label: t('nav.platformConfig'),
          icon: 'lock',
          requiredPermissions: ['platform.config.read']
        },
        {
          to: '/workspace/service-accounts',
          label: t('nav.serviceAccounts'),
          icon: 'users',
          requiredPermissions: ['platform.service_account.read']
        },
        {
          to: '/workspace/system-governance',
          label: t('nav.systemGovernance'),
          icon: 'shield',
          requiredPermissions: ['platform.config.read']
        },
        {
          to: '/workspace/audit',
          label: t('nav.audit'),
          icon: 'audit',
          requiredPermissions: ['platform.audit.read', 'project.audit.read'],
          permissionMode: 'any'
        }
      ]
    },
  ]

  if (isDev) {
    baseGroups.push({
      id: 'resources',
      label: 'Resources',
      items: [
        { to: '/workspace/resources', label: t('nav.resourcesOverview'), icon: 'sparkle', exact: true },
        { to: '/workspace/resources/playbook', label: t('nav.resourcePlaybook'), icon: 'overview' },
        { to: '/workspace/resources/pages', label: t('nav.resourcePages'), icon: 'folder' },
        { to: '/workspace/resources/components', label: t('nav.resourceComponents'), icon: 'users' },
        { to: '/workspace/resources/engineering', label: t('nav.resourceEngineering'), icon: 'runtime' }
      ]
    })
  }

  return baseGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => {
        if (!item.requiredPermissions?.length) {
          return true
        }

        const mode = item.permissionMode === 'any' ? 'any' : 'all'
        const evaluator = (permission: PermissionCode) =>
          permission.startsWith('project.')
            ? authorization.currentProjectCan(permission) || authorization.canAnyProject(permission)
            : authorization.can(permission)

        return mode === 'any'
          ? item.requiredPermissions.some((permission) => evaluator(permission))
          : item.requiredPermissions.every((permission) => evaluator(permission))
      })
    }))
    .filter((group) => group.items.length > 0)
})

function isActive(path: string, exact = false): boolean {
  if (exact) {
    return route.path === path
  }

  return route.path === path || route.path.startsWith(`${path}/`)
}

function isGroupExpanded(groupId: string): boolean {
  if (uiStore.sidebarCollapsed) {
    return true
  }

  return uiStore.isSidebarGroupExpanded(groupId)
}

function isGroupActive(group: SidebarGroup): boolean {
  return group.items.some((item) => isActive(item.to, item.exact))
}

function toggleGroup(groupId: string) {
  if (uiStore.sidebarCollapsed) {
    return
  }

  uiStore.toggleSidebarGroup(groupId)
}

watch(
  groups,
  (nextGroups) => {
    uiStore.ensureSidebarExpandedGroups(nextGroups.map((group) => group.id))
  },
  { immediate: true },
)
</script>

<template>
  <aside
    class="pw-sidebar transition-[width] duration-300"
    :class="uiStore.sidebarCollapsed ? 'w-[72px]' : 'w-64'"
  >
    <div class="pw-sidebar-header">
      <div class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl shadow-glow">
        <BrandMark
          alt="Agent Platform mark"
          class="scale-[1.08]"
        />
      </div>
      <div
        v-if="!uiStore.sidebarCollapsed"
        class="flex min-w-0 flex-col"
      >
        <div class="truncate text-[17px] font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">
          {{ appMeta.name }}
        </div>
        <div class="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
          {{ appMeta.versionLabel }}
        </div>
      </div>
    </div>

    <nav class="pw-sidebar-nav">
      <section
        v-for="group in groups"
        :key="group.id"
        class="mb-6"
      >
        <button
          v-if="!uiStore.sidebarCollapsed"
          type="button"
          class="mb-2 flex w-full items-center px-3 pb-1 pt-0.5 text-left transition-colors duration-150 hover:text-gray-700 dark:hover:text-dark-200"
          :class="isGroupActive(group) ? 'text-gray-700 dark:text-dark-100' : 'text-gray-400 dark:text-dark-500'"
          :aria-expanded="isGroupExpanded(group.id)"
          @click="toggleGroup(group.id)"
        >
          <span class="pw-sidebar-section-title mb-0 px-0">
            {{ group.label }}
          </span>
        </button>
        <div
          v-else
          class="mx-4 my-3 h-px bg-gray-200 dark:bg-dark-800"
        />
        <div
          v-show="isGroupExpanded(group.id)"
          class="space-y-1"
        >
          <template
            v-for="item in group.items"
            :key="item.to"
          >
            <div
              v-if="!uiStore.sidebarCollapsed && item.sectionTitle"
              class="pw-sidebar-subsection-title"
            >
              {{ item.sectionTitle }}
            </div>
            <router-link
              :to="item.to"
              class="pw-sidebar-link"
              :class="isActive(item.to, item.exact) ? 'pw-sidebar-link-active' : ''"
              :title="uiStore.sidebarCollapsed ? item.label : undefined"
            >
              <BaseIcon
                :name="item.icon as never"
                size="md"
                class="shrink-0"
              />
              <span v-if="!uiStore.sidebarCollapsed">{{ item.label }}</span>
            </router-link>
          </template>
        </div>
      </section>
    </nav>

    <div class="mt-auto border-t border-gray-100 p-3 dark:border-dark-800">
      <button
        type="button"
        class="pw-sidebar-link mb-2 w-full"
        :title="uiStore.sidebarCollapsed ? (themeStore.mode === 'dark' ? t('common.lightMode') : t('common.darkMode')) : undefined"
        @click="themeStore.toggleMode"
      >
        <BaseIcon
          :name="themeStore.mode === 'dark' ? 'sun' : 'moon'"
          size="md"
          class="shrink-0"
          :class="themeStore.mode === 'dark' ? 'text-amber-500' : ''"
        />
        <span v-if="!uiStore.sidebarCollapsed">
          {{ themeStore.mode === 'dark' ? t('common.lightMode') : t('common.darkMode') }}
        </span>
      </button>

      <button
        type="button"
        class="pw-sidebar-link w-full"
        :title="uiStore.sidebarCollapsed ? '展开' : '收起'"
        @click="uiStore.toggleSidebar"
      >
        <BaseIcon
          :name="uiStore.sidebarCollapsed ? 'expand' : 'collapse'"
          size="md"
          class="shrink-0"
        />
        <span v-if="!uiStore.sidebarCollapsed">
          收起
        </span>
      </button>
    </div>
  </aside>
</template>
