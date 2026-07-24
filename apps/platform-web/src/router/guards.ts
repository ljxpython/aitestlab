import type { Router } from 'vue-router'
import { hasPermission, isProjectPermission } from '@/services/auth/permissions'
import { getAccessToken, hasStoredAuthSession } from '@/services/auth/token'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import type { PermissionCode } from '@/types/management'

function resolveRoutePermissionProjectId(
  params: Record<string, unknown>,
  workspaceStore: ReturnType<typeof useWorkspaceStore>,
  source?: 'workspace' | 'route'
): string {
  if (source === 'route') {
    if (typeof params.projectId === 'string') {
      return params.projectId.trim()
    }
    return ''
  }

  return workspaceStore.currentProjectId
}

function hasRoutePermission(
  requiredPermissions: PermissionCode[],
  mode: 'all' | 'any',
  projectId: string,
  allowWithoutProject: boolean,
  authStore: ReturnType<typeof useAuthStore>,
  workspaceStore: ReturnType<typeof useWorkspaceStore>
): boolean {
  const evaluator = (permission: PermissionCode) => {
    if (!isProjectPermission(permission)) {
      return hasPermission(authStore.user, permission)
    }

    if (projectId) {
      return workspaceStore.currentProjectAccess?.project_id === projectId
        && workspaceStore.currentProjectAccess.permissions.includes(permission)
    }

    return allowWithoutProject
      ? Boolean(workspaceStore.currentProjectAccess?.permissions.includes(permission))
      : false
  }

  return mode === 'any'
    ? requiredPermissions.some((permission) => evaluator(permission))
    : requiredPermissions.every((permission) => evaluator(permission))
}

export function registerRouterGuards(router: Router) {
  router.beforeEach(async (to) => {
    const authStore = useAuthStore()
    const workspaceStore = useWorkspaceStore()
    const uiStore = useUiStore()

    await authStore.hydrate()
    if (hasStoredAuthSession() && (!authStore.user || !getAccessToken())) {
      await authStore.fetchCurrentUser()
    }

    const isAuthenticated = hasStoredAuthSession() && Boolean(authStore.user)

    if (to.path.startsWith('/workspace') && !isAuthenticated) {
      return {
        path: '/auth/login',
        query: { redirect: to.fullPath }
      }
    }

    if (to.path.startsWith('/auth') && isAuthenticated) {
      if (typeof to.query.redirect === 'string' && to.query.redirect.startsWith('/workspace')) {
        return to.query.redirect
      }

      return '/workspace/overview'
    }

    if (to.path.startsWith('/workspace') && isAuthenticated && !workspaceStore.projects.length) {
      await workspaceStore.hydrateContext()
    }

    if (to.path.startsWith('/workspace')) {
      const requiredPermissions = Array.isArray(to.meta.requiredPermissions)
        ? (to.meta.requiredPermissions as PermissionCode[])
        : []

      if (requiredPermissions.length > 0) {
        const permissionMode = to.meta.permissionMode === 'any' ? 'any' : 'all'
        const projectId = resolveRoutePermissionProjectId(
          to.params as Record<string, unknown>,
          workspaceStore,
          to.meta.permissionProjectSource
        )
        if (
          to.meta.permissionProjectSource === 'route'
          && projectId
          && workspaceStore.currentProjectAccess?.project_id !== projectId
        ) {
          await workspaceStore.setProjectId(projectId)
        }
        const allowed = hasRoutePermission(
          requiredPermissions,
          permissionMode,
          projectId,
          Boolean(to.meta.allowWithoutProject),
          authStore,
          workspaceStore
        )

        if (!allowed) {
          uiStore.pushToast({
            type: 'warning',
            title: '无访问权限',
            message: '当前账号没有访问该页面所需的权限。'
          })
          return '/workspace/overview'
        }
      }
    }

    return true
  })
}
