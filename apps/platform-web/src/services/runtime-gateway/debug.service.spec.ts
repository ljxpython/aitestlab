import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChatResolvedTarget, ChatRunOptions } from '@/modules/chat/types'

const { createLanggraphClientMock, createRuntimeThreadMock, runsStreamMock } =
  vi.hoisted(() => ({
    createLanggraphClientMock: vi.fn(),
    createRuntimeThreadMock: vi.fn(),
    runsStreamMock: vi.fn()
  }))

vi.mock('@/services/langgraph/client', () => ({
  createLanggraphClient: createLanggraphClientMock
}))

vi.mock('./workspace.service', () => ({
  createRuntimeThread: createRuntimeThreadMock
}))

import {
  buildRuntimeDebugRunPayload,
  createRuntimeDebugSession,
  streamRuntimeDebugRun
} from './debug.service'

const runOptions: ChatRunOptions = {
  modelId: 'gpt-4.1',
  systemPrompt: 'Inspect each tool call.',
  enableTools: true,
  toolNames: ['task', 'utc_now'],
  temperature: '0.2',
  maxTokens: '1024'
}

const target: ChatResolvedTarget = {
  targetType: 'assistant',
  assistantId: 'assistant-1',
  assistantName: 'Assistant',
  updatedAt: '',
  resolvedTargetId: 'assistant-1',
  displayName: 'Assistant',
  label: 'Assistant · Assistant'
}

describe('runtime debug gateway service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    createLanggraphClientMock.mockReturnValue({
      runs: { stream: runsStreamMock }
    })
  })

  it('creates an isolated legacy debug session', async () => {
    createRuntimeThreadMock.mockResolvedValue({ thread_id: 'debug-thread-1' })

    await createRuntimeDebugSession('project-1', target)

    expect(createRuntimeThreadMock).toHaveBeenCalledWith('project-1', target, {
      sessionKind: 'legacy_debug'
    })
  })

  it('starts with a tool breakpoint and preserves legacy runtime options', () => {
    expect(
      buildRuntimeDebugRunPayload({
        input: { messages: [] },
        runOptions,
        breakpointMode: 'tools',
        streamSubgraphs: false
      })
    ).toEqual({
      input: { messages: [] },
      context: {
        model_id: 'gpt-4.1',
        system_prompt: 'Inspect each tool call.',
        enable_tools: true,
        tools: ['task', 'utc_now'],
        temperature: 0.2,
        max_tokens: 1024
      },
      interruptBefore: ['tools'],
      streamMode: ['values', 'updates', 'tasks'],
      version: 'v2',
      streamSubgraphs: false,
      streamResumable: true,
      onDisconnect: 'cancel'
    })
  })

  it('breaks after tools when resuming a pending task call', () => {
    const payload = buildRuntimeDebugRunPayload({
      input: null,
      runOptions,
      breakpointMode: 'tools',
      streamSubgraphs: true,
      continueFromInterrupt: true,
      hasPendingTaskToolCall: true
    })

    expect(payload).toMatchObject({
      input: null,
      interruptAfter: ['tools'],
      streamSubgraphs: true
    })
    expect(payload).not.toHaveProperty('interruptBefore')
  })

  it('streams through the project-scoped legacy run client', () => {
    const controller = new AbortController()
    const onRunCreated = vi.fn()

    streamRuntimeDebugRun({
      projectId: 'project-1',
      threadId: 'debug-thread-1',
      target,
      request: {
        input: null,
        runOptions,
        breakpointMode: 'none',
        streamSubgraphs: true
      },
      signal: controller.signal,
      onRunCreated
    })

    expect(createLanggraphClientMock).toHaveBeenCalledWith('project-1')
    expect(runsStreamMock).toHaveBeenCalledWith(
      'debug-thread-1',
      'assistant-1',
      expect.objectContaining({
        input: null,
        version: 'v2',
        streamSubgraphs: true,
        signal: controller.signal,
        onRunCreated: expect.any(Function)
      })
    )

    const streamOptions = runsStreamMock.mock.calls[0]?.[2]
    streamOptions.onRunCreated({ run_id: 'run-1' })
    expect(onRunCreated).toHaveBeenCalledWith('run-1')
  })
})
