import { platformHttpClient } from '@/services/http/client'
import type { ManagementProject, ManagementProjectListResponse, ProjectAccess } from '@/types/management'

export async function listProjectsPage(options?: {
  limit?: number
  offset?: number
  query?: string
}): Promise<ManagementProjectListResponse> {
  const response = await platformHttpClient.get('/api/projects', {
    params: {
      limit: options?.limit ?? 100,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined
    }
  })

  return response.data as ManagementProjectListResponse
}

export async function listProjects(
): Promise<ManagementProject[]> {
  const payload = await listProjectsPage()
  return payload.items
}

export async function listRuntimeProjectsPage(options?: {
  limit?: number
  offset?: number
  query?: string
}): Promise<ManagementProjectListResponse> {
  return listProjectsPage(options)
}

export async function listRuntimeProjects(): Promise<ManagementProject[]> {
  return listProjects()
}

export async function createProject(payload: {
  name: string
  description?: string
}): Promise<ManagementProject> {
  const response = await platformHttpClient.post('/api/projects', payload)
  return response.data as ManagementProject
}

export async function createRuntimeProject(payload: {
  name: string
  description?: string
}): Promise<ManagementProject> {
  return createProject(payload)
}

export async function deleteProject(
  projectId: string
): Promise<{ ok: boolean }> {
  const response = await platformHttpClient.delete(`/api/projects/${projectId}`)
  return response.data as { ok: boolean }
}

export async function archiveProject(projectId: string): Promise<ManagementProject> {
  const response = await platformHttpClient.post(`/api/projects/${projectId}/archive`)
  return response.data as ManagementProject
}

export async function restoreProject(projectId: string): Promise<ManagementProject> {
  const response = await platformHttpClient.post(`/api/projects/${projectId}/restore`)
  return response.data as ManagementProject
}

export async function getProjectAccess(projectId: string): Promise<ProjectAccess> {
  const response = await platformHttpClient.get(`/api/projects/${projectId}/access`)
  return response.data as ProjectAccess
}

export async function takeoverProject(projectId: string, reason: string) {
  const response = await platformHttpClient.post(`/api/projects/${projectId}/takeover`, {
    reason: reason.trim()
  })
  return response.data
}

export async function restoreProjectAdmin(projectId: string, userId: string) {
  const response = await platformHttpClient.post(`/api/projects/${projectId}/admin-recovery`, {
    user_id: userId
  })
  return response.data
}
