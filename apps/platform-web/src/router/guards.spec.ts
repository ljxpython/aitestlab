import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  hasStoredAuthSession: vi.fn(),
  getAccessToken: vi.fn(),
  authStore: {
    user: null as null | { must_change_password: boolean },
    hydrate: vi.fn(),
    fetchCurrentUser: vi.fn()
  },
  workspaceStore: {
    projects: [{ id: 'project-a' }],
    currentProjectId: 'project-a',
    currentProjectAccess: null as null | {
      project_id: string
      permissions: string[]
    },
    hydrateContext: vi.fn(),
    setProjectId: vi.fn()
  },
  uiStore: { pushToast: vi.fn() }
}))

vi.mock('@/services/auth/token', () => ({
  hasStoredAuthSession: mocks.hasStoredAuthSession,
  getAccessToken: mocks.getAccessToken
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.authStore }))
vi.mock('@/stores/workspace', () => ({ useWorkspaceStore: () => mocks.workspaceStore }))
vi.mock('@/stores/ui', () => ({ useUiStore: () => mocks.uiStore }))

import { registerRouterGuards } from './guards'

function captureGuard() {
  let guard: ((to: Record<string, any>) => Promise<unknown>) | undefined
  registerRouterGuards({
    beforeEach(callback: typeof guard) {
      guard = callback
    }
  } as never)
  if (!guard) {
    throw new Error('router guard not registered')
  }
  return guard
}

describe('router guards', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.hasStoredAuthSession.mockReturnValue(true)
    mocks.getAccessToken.mockReturnValue('token')
    mocks.authStore.user = { must_change_password: false }
    mocks.workspaceStore.projects = [{ id: 'project-a' }]
    mocks.workspaceStore.currentProjectId = 'project-a'
    mocks.workspaceStore.currentProjectAccess = null
    mocks.workspaceStore.setProjectId.mockImplementation(async (projectId: string) => {
      mocks.workspaceStore.currentProjectId = projectId
      mocks.workspaceStore.currentProjectAccess = {
        project_id: projectId,
        permissions: ['project.member.read']
      }
    })
  })

  it('does not restrict workspace routes for a legacy password-change flag', async () => {
    mocks.authStore.user = { must_change_password: true }

    await expect(
      captureGuard()({ path: '/workspace/projects', fullPath: '/workspace/projects', query: {}, meta: {} })
    ).resolves.toBe(true)
  })

  it('keeps the security page available as a normal optional workspace route', async () => {
    mocks.authStore.user = { must_change_password: true }
    mocks.workspaceStore.projects = []

    await expect(
      captureGuard()({
        name: 'workspace-security',
        path: '/workspace/security',
        fullPath: '/workspace/security',
        query: {},
        meta: {}
      })
    ).resolves.toBe(true)
    expect(mocks.workspaceStore.hydrateContext).toHaveBeenCalledOnce()
  })

  it('loads route-scoped project access before evaluating project permission', async () => {
    const result = await captureGuard()({
      path: '/workspace/projects/project-b/members',
      fullPath: '/workspace/projects/project-b/members',
      query: {},
      params: { projectId: 'project-b' },
      meta: {
        requiredPermissions: ['project.member.read'],
        permissionProjectSource: 'route'
      }
    })

    expect(mocks.workspaceStore.setProjectId).toHaveBeenCalledWith('project-b')
    expect(result).toBe(true)
  })
})
