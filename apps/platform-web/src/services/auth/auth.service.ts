import { platformHttpClient } from '@/services/http/client'

export async function login(payload: {
  username: string
  password: string
}): Promise<{
  access_token: string
  refresh_token: string
  token_type: string
  user: { must_change_password: boolean }
}> {
  const response = await platformHttpClient.post('/api/identity/session', payload)
  const tokens = response.data?.tokens
  return {
    access_token: String(tokens?.access_token || ''),
    refresh_token: String(tokens?.refresh_token || ''),
    token_type: String(tokens?.token_type || 'bearer'),
    user: { must_change_password: Boolean(response.data?.user?.must_change_password) }
  }
}

export async function changePassword(payload: {
  oldPassword: string
  newPassword: string
}): Promise<{ access_token: string; refresh_token: string; token_type: string }> {
  const response = await platformHttpClient.post('/api/identity/password/change', {
    old_password: payload.oldPassword,
    new_password: payload.newPassword
  })

  return response.data as { access_token: string; refresh_token: string; token_type: string }
}

export async function logout(refreshToken: string): Promise<void> {
  if (!refreshToken.trim()) {
    return
  }

  await platformHttpClient.delete('/api/identity/session', {
    data: {
      refresh_token: refreshToken
    }
  })
}
