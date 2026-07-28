import type { Message } from '@langchain/langgraph-sdk'
import type { AssembledToolCall } from '@langchain/vue'
import { buildChatMessageMetaView, buildToolResultsByCallId } from './message-meta-view-model'

describe('chat message meta view model', () => {
  it('会把普通工具调用和 task 子代理调用分开整理', () => {
    const aiMessage = {
      id: 'ai-1',
      type: 'ai',
      content: 'working',
      tool_calls: [
        {
          id: 'tool-call-1',
          name: 'write_todos',
          args: {
            todos: ['a', 'b']
          }
        },
        {
          id: 'task-call-1',
          name: 'task',
          args: {
            subagent_type: 'researcher',
            task: '调研竞品'
          }
        }
      ]
    } as Message

    const allMessages: Message[] = [
      aiMessage,
      {
        id: 'tool-1',
        type: 'tool',
        tool_call_id: 'tool-call-1',
        content: 'todos updated'
      } as Message
    ]

    const view = buildChatMessageMetaView(aiMessage, allMessages)

    expect(view.toolCalls).toHaveLength(1)
    expect(view.toolCalls[0]).toMatchObject({
      key: 'tool-call-1',
      name: 'write_todos',
      idLabel: 'tool-call-1',
      status: 'completed',
      resultText: 'todos updated'
    })
    expect(view.toolCalls[0]?.argsEntries.map((item) => item.key)).toEqual(['todos'])

    expect(view.subAgentCards).toHaveLength(1)
    expect(view.subAgentCards[0]).toMatchObject({
      id: 'task-call-1',
      name: 'researcher',
      status: 'pending',
      input: '调研竞品'
    })
  })

  it('会为 tool result 建立按 call id 索引', () => {
    const toolMessage = {
      id: 'tool-1',
      type: 'tool',
      tool_call_id: 'call-1',
      content: 'done'
    } as Message

    const result = buildToolResultsByCallId([
      toolMessage,
      {
        id: 'human-1',
        type: 'human',
        content: 'hello'
      } as Message
    ])

    expect(result['call-1']).toBe(toolMessage)
  })

  it('优先使用 SDK tool lifecycle 并保留错误信息', () => {
    const message = {
      id: 'ai-1',
      type: 'ai',
      content: '',
      tool_calls: [{ id: 'call-1', name: 'utc_now', args: {} }]
    } as Message
    const toolCall = {
      id: 'call-1',
      callId: 'call-1',
      name: 'utc_now',
      namespace: [],
      input: {},
      args: {},
      output: null,
      status: 'error',
      error: 'tool failed'
    } as AssembledToolCall

    expect(buildChatMessageMetaView(message, [message], [toolCall]).toolCalls[0]).toMatchObject({
      status: 'error',
      errorText: 'tool failed'
    })
  })
})
