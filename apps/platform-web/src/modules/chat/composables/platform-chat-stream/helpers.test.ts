import { extractThreadFailureMessage } from './helpers'

describe('platform chat stream helpers', () => {
  it('会把线程顶层 APIConnectionError 显示成模型代理连接失败', () => {
    expect(
      extractThreadFailureMessage(null, 'error', {
        error: 'APIConnectionError',
        message: 'An internal error occurred'
      })
    ).toBe('模型上游连接失败：OpenAI 兼容模型代理连接异常，请检查当前模型的 base_url、API key、模型名和网络。')
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
})
