import { beforeEach, describe, expect, it, vi } from 'vitest'

const { platformHttpClientMock } = vi.hoisted(() => ({
  platformHttpClientMock: { get: vi.fn() }
}))

vi.mock('@/services/http/client', () => ({ platformHttpClient: platformHttpClientMock }))

import { listProjectMemberCandidates } from './members.service'

describe('project member candidates', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses the project-scoped paginated candidate endpoint', async () => {
    platformHttpClientMock.get.mockResolvedValue({ data: { items: [], total: 0 } })

    await listProjectMemberCandidates('project-1', {
      query: '  alice  ',
      limit: 20,
      offset: 40
    })

    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/projects/project-1/member-candidates',
      { params: { query: 'alice', limit: 20, offset: 40 } }
    )
  })
})
