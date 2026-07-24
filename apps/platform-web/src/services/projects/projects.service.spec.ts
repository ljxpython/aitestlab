import { beforeEach, describe, expect, it, vi } from 'vitest'

const { platformHttpClientMock } = vi.hoisted(() => ({
  platformHttpClientMock: {
    get: vi.fn(),
    post: vi.fn()
  }
}))

vi.mock('@/services/http/client', () => ({
  platformHttpClient: platformHttpClientMock
}))

import {
  archiveProject,
  getProjectAccess,
  restoreProject,
  restoreProjectAdmin,
  takeoverProject
} from './projects.service'

describe('projects.service governance', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads current project access and sends explicit governance commands', async () => {
    platformHttpClientMock.get.mockResolvedValue({ data: { project_id: 'project-1' } })
    platformHttpClientMock.post.mockResolvedValue({ data: { role: 'project_admin' } })

    await getProjectAccess('project-1')
    await archiveProject('project-1')
    await restoreProject('project-1')
    await takeoverProject('project-1', '  emergency recovery  ')
    await restoreProjectAdmin('project-1', 'user-1')

    expect(platformHttpClientMock.get).toHaveBeenCalledWith('/api/projects/project-1/access')
    expect(platformHttpClientMock.post).toHaveBeenNthCalledWith(
      1,
      '/api/projects/project-1/archive'
    )
    expect(platformHttpClientMock.post).toHaveBeenNthCalledWith(
      2,
      '/api/projects/project-1/restore'
    )
    expect(platformHttpClientMock.post).toHaveBeenNthCalledWith(
      3,
      '/api/projects/project-1/takeover',
      { reason: 'emergency recovery' }
    )
    expect(platformHttpClientMock.post).toHaveBeenNthCalledWith(
      4,
      '/api/projects/project-1/admin-recovery',
      { user_id: 'user-1' }
    )
  })
})
