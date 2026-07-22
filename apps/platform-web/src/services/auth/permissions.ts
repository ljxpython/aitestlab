import type {
  LegacyProjectRole,
  ManagementUser,
  PermissionCode,
  PlatformRole,
  ProjectRole
} from '@/types/management'

const PLATFORM_ROLES: PlatformRole[] = [
  'platform_super_admin',
  'platform_operator',
  'platform_viewer'
]

const PROJECT_ROLES: ProjectRole[] = [
  'project_admin',
  'project_editor',
  'project_executor'
]

const LEGACY_PROJECT_ROLE_MAP: Record<LegacyProjectRole, ProjectRole> = {
  admin: 'project_admin',
  editor: 'project_editor',
  executor: 'project_executor'
}

const PLATFORM_PERMISSION_MAP: Partial<Record<PermissionCode, readonly PlatformRole[]>> = {
  'platform.user.read': ['platform_super_admin', 'platform_operator', 'platform_viewer'],
  'platform.user.write': ['platform_super_admin', 'platform_operator'],
  'platform.audit.read': ['platform_super_admin', 'platform_operator', 'platform_viewer'],
  'platform.catalog.refresh': ['platform_super_admin', 'platform_operator'],
  'platform.announcement.write': ['platform_super_admin', 'platform_operator'],
  'platform.operation.read': ['platform_super_admin', 'platform_operator', 'platform_viewer'],
  'platform.operation.write': ['platform_super_admin', 'platform_operator'],
  'platform.config.read': ['platform_super_admin', 'platform_operator', 'platform_viewer'],
  'platform.config.write': ['platform_super_admin', 'platform_operator'],
  'platform.service_account.read': ['platform_super_admin', 'platform_operator', 'platform_viewer'],
  'platform.service_account.write': ['platform_super_admin', 'platform_operator']
}

const PROJECT_PERMISSION_MAP: Partial<Record<PermissionCode, readonly ProjectRole[]>> = {
  'project.member.read': ['project_admin', 'project_editor', 'project_executor'],
  'project.member.write': ['project_admin'],
  'project.audit.read': ['project_admin', 'project_editor'],
  'project.announcement.read': ['project_admin', 'project_editor', 'project_executor'],
  'project.announcement.write': ['project_admin', 'project_editor'],
  'project.assistant.read': ['project_admin', 'project_editor', 'project_executor'],
  'project.assistant.write': ['project_admin', 'project_editor'],
  'project.runtime.read': ['project_admin', 'project_editor', 'project_executor'],
  'project.runtime.write': ['project_admin', 'project_editor', 'project_executor'],
  'project.knowledge.read': ['project_admin', 'project_editor', 'project_executor'],
  'project.knowledge.write': ['project_admin', 'project_editor'],
  'project.knowledge.admin': ['project_admin'],
  'project.testcase.read': ['project_admin', 'project_editor', 'project_executor'],
  'project.testcase.write': ['project_admin', 'project_editor'],
  'project.operation.read': ['project_admin', 'project_editor', 'project_executor'],
  'project.operation.write': ['project_admin', 'project_editor', 'project_executor']
}

export function normalizePlatformRole(value: unknown): PlatformRole | null {
  return typeof value === 'string' && PLATFORM_ROLES.includes(value as PlatformRole)
    ? (value as PlatformRole)
    : null
}

export function normalizeProjectRole(value: unknown): ProjectRole | null {
  if (typeof value !== 'string') {
    return null
  }

  if (PROJECT_ROLES.includes(value as ProjectRole)) {
    return value as ProjectRole
  }

  return LEGACY_PROJECT_ROLE_MAP[value as LegacyProjectRole] ?? null
}

export function normalizeProjectRoleMap(value: unknown): Record<string, ProjectRole[]> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }

  return Object.entries(value as Record<string, unknown>).reduce<Record<string, ProjectRole[]>>(
    (accumulator, [projectId, roles]) => {
      const normalizedRoles = Array.isArray(roles)
        ? Array.from(new Set(roles.map((item) => normalizeProjectRole(item)).filter(Boolean))) as ProjectRole[]
        : []

      if (projectId.trim() && normalizedRoles.length > 0) {
        accumulator[projectId.trim()] = normalizedRoles
      }
      return accumulator
    },
    {}
  )
}

type ManagementUserPayload = Partial<Omit<ManagementUser, 'platform_roles' | 'project_roles'>> & {
  platform_roles?: unknown
  project_roles?: unknown
}

export function normalizeManagementUser(payload: ManagementUserPayload): ManagementUser {
  const platformRoles = Array.isArray(payload.platform_roles)
    ? Array.from(
        new Set(
          payload.platform_roles
            .map((item) => normalizePlatformRole(item))
            .filter(Boolean)
        )
      ) as PlatformRole[]
    : []

  const projectRoles = normalizeProjectRoleMap(payload.project_roles)
  const isSuperAdmin = platformRoles.includes('platform_super_admin') || Boolean(payload.is_super_admin)

  return {
    id: String(payload.id || ''),
    username: String(payload.username || ''),
    email: payload.email ?? null,
    status: String(payload.status || 'active'),
    is_super_admin: isSuperAdmin,
    platform_roles: isSuperAdmin && !platformRoles.includes('platform_super_admin')
      ? ['platform_super_admin', ...platformRoles]
      : platformRoles,
    project_roles: projectRoles,
    created_at: payload.created_at ?? null,
    updated_at: payload.updated_at ?? null
  }
}

export function isProjectPermission(permission: PermissionCode): boolean {
  return permission.startsWith('project.')
}

export function hasPlatformRole(user: ManagementUser | null | undefined, role: PlatformRole): boolean {
  if (!user) {
    return false
  }

  if (role === 'platform_super_admin' && user.is_super_admin) {
    return true
  }

  return user.platform_roles.includes(role)
}

export function projectRolesFor(
  user: ManagementUser | null | undefined,
  projectId: string | null | undefined
): ProjectRole[] {
  const normalizedProjectId = projectId?.trim() || ''
  if (!user || !normalizedProjectId) {
    return []
  }

  return user.project_roles[normalizedProjectId] || []
}

export function projectRoleFor(
  user: ManagementUser | null | undefined,
  projectId: string | null | undefined
): ProjectRole | null {
  return projectRolesFor(user, projectId)[0] || null
}

export function hasPermission(
  user: ManagementUser | null | undefined,
  permission: PermissionCode,
  projectId?: string | null
): boolean {
  if (!user) {
    return false
  }

  if (hasPlatformRole(user, 'platform_super_admin')) {
    return true
  }

  const platformRoles = PLATFORM_PERMISSION_MAP[permission]
  if (platformRoles) {
    return platformRoles.some((role) => hasPlatformRole(user, role))
  }

  const projectRoles = PROJECT_PERMISSION_MAP[permission]
  if (!projectRoles) {
    return false
  }

  const currentRoles = projectRolesFor(user, projectId)
  return projectRoles.some((role) => currentRoles.includes(role))
}

export function hasAnyProjectPermission(
  user: ManagementUser | null | undefined,
  permission: PermissionCode
): boolean {
  if (!user) {
    return false
  }

  if (hasPermission(user, permission)) {
    return true
  }

  if (!isProjectPermission(permission)) {
    return false
  }

  return Object.keys(user.project_roles).some((projectId) =>
    hasPermission(user, permission, projectId)
  )
}

export function formatPlatformRoleLabel(role: PlatformRole): string {
  if (role === 'platform_super_admin') {
    return '平台超级管理员'
  }
  if (role === 'platform_operator') {
    return '平台运维'
  }
  return '平台只读'
}

export function primaryPlatformRole(user: ManagementUser | null | undefined): PlatformRole | null {
  if (!user) {
    return null
  }

  if (hasPlatformRole(user, 'platform_super_admin')) {
    return 'platform_super_admin'
  }
  if (hasPlatformRole(user, 'platform_operator')) {
    return 'platform_operator'
  }
  if (hasPlatformRole(user, 'platform_viewer')) {
    return 'platform_viewer'
  }
  return null
}

export function formatProjectRoleLabel(role: ProjectRole | null | undefined): string {
  if (role === 'project_admin') {
    return '项目管理员'
  }
  if (role === 'project_editor') {
    return '项目编辑'
  }
  if (role === 'project_executor') {
    return '项目执行'
  }
  return '成员'
}

export function describePlatformRole(user: ManagementUser | null | undefined): string {
  const role = primaryPlatformRole(user)
  return role ? formatPlatformRoleLabel(role) : '成员'
}

export function describePrimaryRole(
  user: ManagementUser | null | undefined,
  projectId?: string | null
): string {
  if (!user) {
    return '成员'
  }

  const platformRole = describePlatformRole(user)
  if (platformRole !== '成员') {
    return platformRole
  }

  return formatProjectRoleLabel(projectRoleFor(user, projectId))
}

export function isProjectAdminRole(role: ProjectRole | null | undefined): boolean {
  return role === 'project_admin'
}

export function isProjectEditorRole(role: ProjectRole | null | undefined): boolean {
  return role === 'project_editor'
}
