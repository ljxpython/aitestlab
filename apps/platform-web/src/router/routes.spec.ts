import type { RouteRecordRaw } from 'vue-router'
import { describe, expect, it } from 'vitest'

import { routes } from './routes'

function getWorkspaceChildren(): RouteRecordRaw[] {
  const workspaceRoute = routes.find((route) => route.path === '/workspace')
  return (workspaceRoute?.children ?? []) as RouteRecordRaw[]
}

function getKnowledgeChildren(): RouteRecordRaw[] {
  const knowledgeRoute = getWorkspaceChildren().find(
    (route) => route.path === 'projects/:projectId/knowledge'
  )
  return (knowledgeRoute?.children ?? []) as RouteRecordRaw[]
}

describe('workspace knowledge routes', () => {
  it('redirects the base knowledge route to the documents tab for the active project', () => {
    const knowledgeIndexRoute = getKnowledgeChildren().find((route) => route.name === 'workspace-project-knowledge')

    expect(knowledgeIndexRoute).toBeDefined()
    expect(knowledgeIndexRoute?.path).toBe('')
    expect(knowledgeIndexRoute?.meta).toMatchObject({
      title: '知识库',
      eyebrow: 'Knowledge',
      requiredPermissions: ['project.knowledge.read'],
      permissionProjectSource: 'route'
    })

    const redirect = knowledgeIndexRoute?.redirect as ((to: { params: Record<string, unknown> }) => string)
    expect(redirect({ params: { projectId: '  project-42  ' } })).toBe(
      '/workspace/projects/project-42/knowledge/documents'
    )
  })

  it('registers the expected knowledge child tabs with route-scoped read permission metadata', () => {
    const knowledgeRoutes = getKnowledgeChildren().filter((route) => route.path !== '')

    expect(
      knowledgeRoutes.map((route) => ({
        path: route.path,
        name: route.name,
        title: route.meta?.title
      }))
    ).toEqual([
      {
        path: 'documents',
        name: 'workspace-project-knowledge-documents',
        title: '知识文档'
      },
      {
        path: 'retrieval',
        name: 'workspace-project-knowledge-retrieval',
        title: '知识检索'
      },
      {
        path: 'graph',
        name: 'workspace-project-knowledge-graph',
        title: '知识图谱'
      },
      {
        path: 'settings',
        name: 'workspace-project-knowledge-settings',
        title: '知识设置'
      }
    ])

    for (const route of knowledgeRoutes) {
      expect(route.meta).toMatchObject({
        eyebrow: 'Knowledge',
        requiredPermissions: ['project.knowledge.read'],
        permissionProjectSource: 'route'
      })
    }
  })
})

describe('workspace project governance routes', () => {
  it('allows project detail through platform governance or project membership', () => {
    const projectDetailRoute = getWorkspaceChildren().find(
      (route) => route.name === 'workspace-project-detail'
    )

    expect(projectDetailRoute?.meta).toMatchObject({
      requiredPermissions: ['platform.project.read', 'project.member.read'],
      permissionMode: 'any',
      permissionProjectSource: 'route'
    })
  })
})

describe('workspace account routes', () => {
  it('registers the password change route used by the first-login guard', () => {
    const securityRoute = getWorkspaceChildren().find(
      (route) => route.name === 'workspace-security'
    )

    expect(securityRoute?.path).toBe('security')
  })
})

describe('workspace primary navigation routes', () => {
  it('keeps Agent, Models, and Chat as distinct pages', () => {
    const primary = ['workspace-assistants', 'workspace-models', 'workspace-chat'].map((name) =>
      getWorkspaceChildren().find((route) => route.name === name)
    )

    expect(primary.map((route) => route?.path)).toEqual(['assistants', 'models', 'chat'])
    expect(new Set(primary.map((route) => route?.component)).size).toBe(3)
  })
})

describe('workspace runtime debug route', () => {
  it('does not expose the legacy debug surface', () => {
    const debugRoute = getWorkspaceChildren().find(
      (route) => route.name === 'workspace-chat-debug'
    )

    expect(debugRoute).toBeUndefined()
  })
})
