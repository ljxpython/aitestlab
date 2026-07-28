import type { Message } from '@langchain/langgraph-sdk'
import type { AnyStream } from '@langchain/vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { ChatDisplayMessage } from '../message-view-model'
import ChatMessageList from './ChatMessageList.vue'

function buildAiMessage(): Message {
  return {
    id: 'ai-1',
    type: 'ai',
    content: '这里是一次带工具调用的回复。',
    tool_calls: [
      {
        id: 'tool-1',
        function: {
          name: 'search_docs',
          arguments: JSON.stringify({
            query: 'langgraph streaming'
          })
        }
      }
    ]
  } as unknown as Message
}

function buildDisplayMessages(message: Message): ChatDisplayMessage[] {
  return [
    {
      id: 'assistant-1',
      originalIndex: 0,
      message,
      roleLabel: 'Agent',
      bubbleClass: '',
      wrapClass: 'items-start'
    }
  ]
}

describe('ChatMessageList', () => {
  it('keeps tool details collapsed by default even while running, and bubbles expand state upward', async () => {
    const aiMessage = buildAiMessage()
    const wrapper = mount(ChatMessageList, {
      props: {
        displayMessages: buildDisplayMessages(aiMessage),
        allMessages: [aiMessage],
        editingMessageId: '',
        editingMessageValue: '',
        isRunning: true,
        streamHandle: {} as AnyStream,
        toolCalls: [],
        getMessageMeta: () => undefined,
        getMessageBranchIndex: () => 0,
        hasBranchSwitcher: () => false,
        canEditMessage: () => false,
        canRetryMessage: () => false
      },
      global: {
        stubs: {
          ChatMessageRuntimeMetadata: {
            props: ['stream', 'messageId'],
            template: '<slot :metadata="undefined" />'
          }
        }
      }
    })

    expect(wrapper.text()).toContain('工具调用 1')
    expect(wrapper.text()).not.toContain('Args')

    const metaToggle = wrapper.get('button[aria-expanded="false"]')
    await metaToggle.trigger('click')

    expect(wrapper.text()).toContain('Args')
    expect(wrapper.emitted('message-meta-expanded-change')).toEqual([['assistant-1', true]])

    await wrapper.get('button[aria-expanded="true"]').trigger('click')
    expect(wrapper.emitted('message-meta-expanded-change')).toEqual([
      ['assistant-1', true],
      ['assistant-1', false]
    ])
  })
})
