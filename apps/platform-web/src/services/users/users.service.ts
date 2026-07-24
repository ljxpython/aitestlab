import { platformHttpClient } from '@/services/http/client'
import { normalizeManagementUser, normalizeProjectRole } from '@/services/auth/permissions'
import type {
  ManagementUser,
  ManagementUserListResponse,
  ManagementUserProject,
  PlatformRole
} from '@/types/management'

function normalizeUserProject(payload: ManagementUserProject): ManagementUserProject {
  return {
    ...payload,
    role: normalizeProjectRole(payload.role) || 'project_executor'
  }
}

export async function listUsersPage(options?: {
  limit?: number
  offset?: number
  query?: string
  status?: string
  excludeUserIds?: string[]
}): Promise<ManagementUserListResponse> {
  const response = await platformHttpClient.get('/api/users', {
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined,
      status: options?.status?.trim() || undefined,
      exclude_user_ids:
        Array.isArray(options?.excludeUserIds) && options.excludeUserIds.length > 0
          ? options.excludeUserIds.map((item) => item.trim()).filter(Boolean).join(',')
          : undefined
    }
  })

  const payload = response.data as ManagementUserListResponse
  return {
    items: Array.isArray(payload.items) ? payload.items.map((item) => normalizeManagementUser(item)) : [],
    total: typeof payload.total === 'number' ? payload.total : 0
  }
}

export async function createUser(payload: {
  username: string
  password: string
  platform_roles?: PlatformRole[]
  is_super_admin?: boolean
}): Promise<ManagementUser> {
  const response = await platformHttpClient.post('/api/users', payload)
  return normalizeManagementUser(response.data as ManagementUser)
}

export async function getUser(
  userId: string
): Promise<ManagementUser> {
  const response = await platformHttpClient.get(`/api/users/${userId}`)
  return normalizeManagementUser(response.data as ManagementUser)
}

export async function listUserProjects(
  userId: string
): Promise<{
  items: ManagementUserProject[]
  total: number
}> {
  const response = await platformHttpClient.get(`/api/users/${userId}/projects`)
  const payload = response.data as {
    items?: ManagementUserProject[]
    total?: number
  }

  return {
    items: Array.isArray(payload.items) ? payload.items.map((item) => normalizeUserProject(item)) : [],
    total: typeof payload.total === 'number' ? payload.total : Array.isArray(payload.items) ? payload.items.length : 0
  }
}

export async function updateUser(
  userId: string,
  payload: {
    username?: string
    password?: string
    status?: 'active' | 'disabled'
    platform_roles?: PlatformRole[]
    is_super_admin?: boolean
  }
): Promise<ManagementUser> {
  const response = await platformHttpClient.patch(`/api/users/${userId}`, payload)
  return normalizeManagementUser(response.data as ManagementUser)
}

export async function resetUserPassword(
  userId: string,
  temporaryPassword: string
): Promise<ManagementUser> {
  const response = await platformHttpClient.post(`/api/users/${userId}/credentials/reset`, {
    temporary_password: temporaryPassword
  })
  return normalizeManagementUser(response.data as ManagementUser)
}
