import { beforeEach, describe, expect, it, vi } from 'vitest'

const { platformHttpClientMock } = vi.hoisted(() => ({
  platformHttpClientMock: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('@/services/http/client', () => ({
  platformHttpClient: platformHttpClientMock
}))

import {
  deleteServiceAccountProjectGrant,
  listServiceAccountProjectGrants,
  upsertServiceAccountProjectGrant
} from './service-accounts.service'

describe('service account project grants', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses the dedicated grant endpoints for list, upsert and delete', async () => {
    platformHttpClientMock.get.mockResolvedValue({ data: [] })
    platformHttpClientMock.put.mockResolvedValue({ data: { role: 'project_executor' } })
    platformHttpClientMock.delete.mockResolvedValue({})

    await listServiceAccountProjectGrants('account-1')
    await upsertServiceAccountProjectGrant('account-1', 'project-1', 'project_executor')
    await deleteServiceAccountProjectGrant('account-1', 'project-1')

    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/service-accounts/account-1/project-grants'
    )
    expect(platformHttpClientMock.put).toHaveBeenCalledWith(
      '/api/service-accounts/account-1/project-grants/project-1',
      { role: 'project_executor' }
    )
    expect(platformHttpClientMock.delete).toHaveBeenCalledWith(
      '/api/service-accounts/account-1/project-grants/project-1'
    )
  })
})
