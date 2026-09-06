import { describe, expect, it } from 'vitest'
import {
  buildAssistantDraftPayload,
  buildChatRunSubmitOptions,
  normalizeAssistantRuntimePayload
} from './runtime-contract'

describe('runtime contract helper', () => {
  it('moves runtime business fields from config and configurable into context', () => {
    const payload = normalizeAssistantRuntimePayload({
      graph_id: ' assistant ',
      name: ' Demo Assistant ',
      config: {
        recursion_limit: 12,
        model_id: 'config-model',
        metadata: {
          trace: 'assistant-edit',
          project_id: 'legacy-project'
        },
        configurable: {
          thread_id: 'thread-1',
          enable_tools: true,
          tools: ['utc_now'],
          project_id: 'legacy-project'
        }
      },
      context: {
        system_prompt: 'context prompt',
        user_id: 'user-1'
      },
      metadata: {
        source: 'workspace',
        projectId: 'legacy-project'
      }
    })

    expect(payload).toEqual({
      graph_id: 'assistant',
      name: 'Demo Assistant',
      config: {
        recursion_limit: 12,
        metadata: {
          trace: 'assistant-edit'
        },
        configurable: {
          thread_id: 'thread-1'
        }
      },
      context: {
        system_prompt: 'context prompt',
        model_id: 'config-model',
        enable_tools: true,
        tools: ['utc_now']
      },
      metadata: {
        source: 'workspace'
      }
    })
  })

  it('builds assistant draft payload with runtime selections in context', () => {
    const payload = buildAssistantDraftPayload({
      graphId: ' assistant ',
      name: ' Demo ',
      description: '   ',
      config: {
        recursion_limit: 8
      },
      context: {
        system_prompt: 'runtime prompt',
        model_id: 'legacy-model',
        enable_tools: true,
        tools: ['legacy']
      },
      metadata: {
        source: 'workspace',
        project_id: 'legacy-project'
      },
      runtimeModelId: 'gpt-4o-mini',
      runtimeEnableTools: false,
      runtimeToolNames: ['utc_now']
    })

    expect(payload).toEqual({
      graph_id: 'assistant',
      name: 'Demo',
      config: {
        recursion_limit: 8
      },
      context: {
        system_prompt: 'runtime prompt',
        model_id: 'gpt-4o-mini'
      },
      metadata: {
        source: 'workspace'
      }
    })
  })

  it('builds chat submit options without client-owned prompt or tool policy', () => {
    const options = buildChatRunSubmitOptions({
      modelId: 'gpt-4.1',
      systemPrompt: 'Keep answers concise.',
      enableTools: false,
      toolNames: ['utc_now'],
      temperature: '0.3',
      maxTokens: '2048'
    })

    expect(options).toEqual({
      config: {
        configurable: {
          platform_runtime: {
            model_id: 'gpt-4.1',
            temperature: 0.3,
            max_tokens: 2048
          }
        }
      }
    })
  })
})
