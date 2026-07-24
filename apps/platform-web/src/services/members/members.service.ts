import { platformHttpClient } from '@/services/http/client'
import { normalizeProjectRole } from '@/services/auth/permissions'
import type { ManagementProjectMember, PaginatedResponse, ProjectMemberCandidate } from '@/types/management'

type MemberListResponse = {
  items: ManagementProjectMember[]
}

function normalizeProjectMember(payload: ManagementProjectMember): ManagementProjectMember {
  return {
    ...payload,
    role: normalizeProjectRole(payload.role) || 'project_executor'
  }
}

export async function listProjectMembers(
  projectId: string,
  options?: { query?: string }
): Promise<ManagementProjectMember[]> {
  if (!projectId) {
    return []
  }

  const response = await platformHttpClient.get(`/api/projects/${projectId}/members`, {
    params: {
      query: options?.query?.trim() || undefined
    }
  })

  const payload = response.data as MemberListResponse
  return Array.isArray(payload.items) ? payload.items.map((item) => normalizeProjectMember(item)) : []
}

export async function upsertProjectMember(payload: {
  projectId: string
  userId: string
  role: ManagementProjectMember['role']
}): Promise<ManagementProjectMember> {
  const response = await platformHttpClient.put(
    `/api/projects/${payload.projectId}/members/${payload.userId}`,
    {
      role: normalizeProjectRole(payload.role)
    }
  )

  return normalizeProjectMember(response.data as ManagementProjectMember)
}

export async function deleteProjectMember(
  projectId: string,
  userId: string
): Promise<{ ok: boolean }> {
  const response = await platformHttpClient.delete(`/api/projects/${projectId}/members/${userId}`)

  return response.data as { ok: boolean }
}

export async function listProjectMemberCandidates(
  projectId: string,
  options?: { query?: string; limit?: number; offset?: number }
): Promise<PaginatedResponse<ProjectMemberCandidate>> {
  const response = await platformHttpClient.get(`/api/projects/${projectId}/member-candidates`, {
    params: {
      query: options?.query?.trim() || undefined,
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0
    }
  })
  return response.data as PaginatedResponse<ProjectMemberCandidate>
}
