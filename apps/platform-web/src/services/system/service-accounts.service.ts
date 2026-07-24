import { platformHttpClient } from '@/services/http/client'
import type {
  CreatedServiceAccountToken,
  ManagementServiceAccount,
  ManagementServiceAccountPage,
  ServiceAccountProjectGrant
} from '@/types/management'

export async function listServiceAccounts(options?: {
  limit?: number
  offset?: number
  query?: string
  status?: string
}): Promise<ManagementServiceAccountPage> {
  const response = await platformHttpClient.get('/api/service-accounts', {
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined,
      status: options?.status?.trim() || undefined
    }
  })
  return response.data as ManagementServiceAccountPage
}

export async function createServiceAccount(payload: {
  name: string
  description?: string
  platform_roles: string[]
}): Promise<ManagementServiceAccount> {
  const response = await platformHttpClient.post('/api/service-accounts', payload)
  return response.data as ManagementServiceAccount
}

export async function updateServiceAccount(
  serviceAccountId: string,
  payload: {
    description?: string | null
    status?: 'active' | 'disabled'
    platform_roles?: string[]
  }
): Promise<ManagementServiceAccount> {
  const response = await platformHttpClient.patch(`/api/service-accounts/${serviceAccountId}`, payload)
  return response.data as ManagementServiceAccount
}

export async function createServiceAccountToken(
  serviceAccountId: string,
  payload: {
    name: string
    expires_in_days?: number
  }
): Promise<CreatedServiceAccountToken> {
  const response = await platformHttpClient.post(
    `/api/service-accounts/${serviceAccountId}/tokens`,
    payload
  )
  return response.data as CreatedServiceAccountToken
}

export async function revokeServiceAccountToken(
  serviceAccountId: string,
  tokenId: string
): Promise<void> {
  await platformHttpClient.delete(`/api/service-accounts/${serviceAccountId}/tokens/${tokenId}`)
}

export async function listServiceAccountProjectGrants(
  serviceAccountId: string
): Promise<ServiceAccountProjectGrant[]> {
  const response = await platformHttpClient.get(
    `/api/service-accounts/${serviceAccountId}/project-grants`
  )
  return response.data as ServiceAccountProjectGrant[]
}

export async function upsertServiceAccountProjectGrant(
  serviceAccountId: string,
  projectId: string,
  role: ServiceAccountProjectGrant['role']
): Promise<ServiceAccountProjectGrant> {
  const response = await platformHttpClient.put(
    `/api/service-accounts/${serviceAccountId}/project-grants/${projectId}`,
    { role }
  )
  return response.data as ServiceAccountProjectGrant
}

export async function deleteServiceAccountProjectGrant(
  serviceAccountId: string,
  projectId: string
): Promise<void> {
  await platformHttpClient.delete(
    `/api/service-accounts/${serviceAccountId}/project-grants/${projectId}`
  )
}
