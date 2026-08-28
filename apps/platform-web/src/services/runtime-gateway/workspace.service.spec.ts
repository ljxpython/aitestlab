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

import { listRuntimeThreadsPage, normalizeRuntimeGatewayError } from './workspace.service'

describe('workspace runtime gateway service', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses only supported fields in the first thread search request', async () => {
    platformHttpClientMock.post.mockImplementation((path: string) => {
      if (path === '/api/langgraph/threads/count') {
        return Promise.resolve({ data: { count: 0 } })
      }
      return Promise.resolve({ data: [] })
    })

    await listRuntimeThreadsPage('project-1', { graphId: 'assistant' })

    const searchCall = platformHttpClientMock.post.mock.calls.find(
      ([path]) => path === '/api/langgraph/threads/search'
    )
    expect(searchCall?.[1]).toMatchObject({
      metadata: { graph_id: 'assistant' },
      select: ['thread_id', 'metadata', 'status', 'created_at', 'updated_at']
    })
  })

  it('normalizes Cloudflare block pages returned by the model gateway', () => {
    expect(
      normalizeRuntimeGatewayError(
        new Error("OpenAIPermissionDeniedError('<!DOCTYPE html><html>Cloudflare</html>')"),
        '对话运行失败'
      ).message
    ).toBe('模型上游请求被拒绝：当前模型网关返回权限或 Cloudflare 拦截，请检查 base_url、API key、模型部署和网络。')
  })
})
