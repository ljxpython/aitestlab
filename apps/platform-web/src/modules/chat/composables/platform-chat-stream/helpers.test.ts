import type { Message } from '@langchain/langgraph-sdk'
import {
  extractInterruptPayload,
  extractThreadFailureMessage,
  getMetadataCheckpointId,
  hasPendingTaskToolCall
} from './helpers'

describe('platform chat stream helpers', () => {
  it('preserves single and multiple protocol interrupts', () => {
    const single = [{ value: { action_request: { name: 'search' } } }]
    const multiple = [
      [{ value: { action_request: { name: 'search' } } }],
      [{ value: { action_request: { name: 'write' } } }]
    ]

    expect(extractInterruptPayload({ __interrupt__: single })).toBe(single)
    expect(
      extractInterruptPayload({
        tasks: multiple.map((interrupts) => ({ interrupts }))
      })
    ).toEqual(multiple)
  })

  it('会把线程顶层 APIConnectionError 显示成模型代理连接失败', () => {
    expect(
      extractThreadFailureMessage(null, 'error', {
        error: 'APIConnectionError',
        message: 'An internal error occurred'
      })
    ).toBe('模型上游连接失败：OpenAI 兼容模型代理连接异常，请检查当前模型的 base_url、API key、模型名和网络。')
  })

  it('会把模型网关的 HTML 拒绝页归一化为可读错误', () => {
    expect(
      extractThreadFailureMessage(null, 'error', {
        error: 'OpenAIPermissionDeniedError',
        message: '<!DOCTYPE html><html><body>Cloudflare blocked the request</body></html>'
      })
    ).toBe('模型上游请求被拒绝：当前模型网关返回权限或 Cloudflare 拦截，请检查 base_url、API key、模型部署和网络。')
  })

  it('会优先使用线程顶层的具体错误信息', () => {
    expect(
      extractThreadFailureMessage(null, 'error', {
        error: 'RuntimeError',
        message: '模型名称不存在'
      })
    ).toBe('模型名称不存在')
  })

  it('保留 task 错误优先级', () => {
    expect(
      extractThreadFailureMessage(
        {
          tasks: [
            {
              error: '工具执行失败'
            }
          ]
        },
        'error',
        {
          error: 'APIConnectionError',
          message: 'An internal error occurred'
        }
      )
    ).toBe('工具执行失败')
  })

  it('tracks a task tool call until its matching tool result arrives', () => {
    const taskCall = {
      type: 'ai',
      content: '',
      tool_calls: [{ id: 'task-1', name: 'task' }]
    } as Message
    const taskResult = {
      type: 'tool',
      content: '',
      tool_call_id: 'task-1'
    } as Message

    expect(hasPendingTaskToolCall([taskCall])).toBe(true)
    expect(hasPendingTaskToolCall([taskCall, taskResult])).toBe(false)
  })

  it('reads checkpoint ids only from message first-seen metadata', () => {
    expect(
      getMetadataCheckpointId({
        firstSeenState: { checkpoint: { checkpoint_id: ' checkpoint-1 ' } }
      })
    ).toBe('checkpoint-1')
    expect(getMetadataCheckpointId({ firstSeenState: { checkpoint_id: 'guessed' } })).toBe('')
  })
})
