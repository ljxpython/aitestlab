import { computed } from 'vue'
import {
  describePrimaryRole,
  describePlatformRole,
  hasPermission,
  isProjectPermission
} from '@/services/auth/permissions'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import type { PermissionCode } from '@/types/management'

export function useAuthorization() {
  const authStore = useAuthStore()
  const { activeProjectId, workspaceStore } = useWorkspaceProjectContext()

  const currentProjectRole = computed(() => workspaceStore.currentProjectAccess?.roles[0] || null)
  const platformRoleLabel = computed(() => describePlatformRole(authStore.user))
  const roleLabel = computed(() => describePrimaryRole(authStore.user, currentProjectRole.value))

  function can(permission: PermissionCode, projectId?: string | null) {
    if (isProjectPermission(permission)) {
      const targetProjectId = projectId?.trim() || activeProjectId.value
      return workspaceStore.currentProjectAccess?.project_id === targetProjectId
        && workspaceStore.currentProjectAccess.permissions.includes(permission)
    }
    return hasPermission(authStore.user, permission)
  }

  function canAnyProject(permission: PermissionCode) {
    return workspaceStore.currentProjectAccess?.permissions.includes(permission) ?? false
  }

  function currentProjectCan(permission: PermissionCode) {
    return workspaceStore.currentProjectAccess?.permissions.includes(permission) ?? false
  }

  return {
    currentProjectId: activeProjectId,
    currentProjectRole,
    platformRoleLabel,
    roleLabel,
    can,
    canAnyProject,
    currentProjectCan
  }
}
