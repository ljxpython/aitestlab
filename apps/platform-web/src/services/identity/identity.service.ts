import { platformHttpClient } from '@/services/http/client'
import { normalizeManagementUser } from '@/services/auth/permissions'
import type { ManagementUser } from '@/types/management'

type RuntimeUserProfile = {
  id: string
  username: string
  email?: string | null
  status: string
  platform_roles?: string[]
  must_change_password?: boolean
  is_super_admin?: boolean
  created_at?: string | null
  updated_at?: string | null
}

function normalizeIdentityUserProfile(
  payload: RuntimeUserProfile | ManagementUser
): ManagementUser {
  return normalizeManagementUser(payload)
}

export async function getCurrentProfile(
): Promise<ManagementUser> {
  const response = await platformHttpClient.get('/api/identity/me')
  return normalizeIdentityUserProfile(response.data as RuntimeUserProfile | ManagementUser)
}

export async function updateCurrentProfile(
  payload: {
    username?: string
    email?: string
  }
): Promise<ManagementUser> {
  const response = await platformHttpClient.patch('/api/identity/me', {
    username: payload.username?.trim() || undefined,
    email: payload.email?.trim() || ''
  })
  return normalizeIdentityUserProfile(response.data as RuntimeUserProfile | ManagementUser)
}

export async function changeCurrentPassword(
  payload: {
    oldPassword: string
    newPassword: string
  }
): Promise<{ access_token: string; refresh_token: string; token_type: string }> {
  const response = await platformHttpClient.post('/api/identity/password/change', {
    old_password: payload.oldPassword,
    new_password: payload.newPassword
  })
  return response.data as { access_token: string; refresh_token: string; token_type: string }
}
