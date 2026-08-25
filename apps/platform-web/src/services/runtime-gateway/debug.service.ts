import { createLanggraphClient } from '@/services/langgraph/client'
import { buildLegacyDebugRunContext } from '@/services/runtime/runtime-contract'
import type { ChatResolvedTarget, ChatRunOptions } from '@/modules/chat/types'
import {
  createRuntimeThread,
  type RuntimeGatewayTargetDescriptor
} from './workspace.service'

export type RuntimeDebugBreakpointMode = 'tools' | 'none'

export type RuntimeDebugRunInput = {
  input: Record<string, unknown> | null
  runOptions: ChatRunOptions
  breakpointMode: RuntimeDebugBreakpointMode
  streamSubgraphs: boolean
  continueFromInterrupt?: boolean
  hasPendingTaskToolCall?: boolean
}

export function buildRuntimeDebugRunPayload(input: RuntimeDebugRunInput) {
  const useToolBreakpoint = input.breakpointMode === 'tools'
  const breakAfterTools =
    useToolBreakpoint &&
    input.continueFromInterrupt &&
    input.hasPendingTaskToolCall

  return {
    input: input.input,
    context: buildLegacyDebugRunContext(input.runOptions),
    ...(useToolBreakpoint && !breakAfterTools
      ? { interruptBefore: ['tools'] }
      : {}),
    ...(breakAfterTools ? { interruptAfter: ['tools'] } : {}),
    streamMode: ['values', 'updates', 'tasks'] as Array<
      'values' | 'updates' | 'tasks'
    >,
    version: 'v2' as const,
    streamSubgraphs: input.streamSubgraphs,
    streamResumable: true,
    onDisconnect: 'cancel' as const
  }
}

export async function createRuntimeDebugSession(
  projectId: string,
  target: RuntimeGatewayTargetDescriptor
) {
  return await createRuntimeThread(projectId, target, {
    sessionKind: 'legacy_debug'
  })
}

export function streamRuntimeDebugRun(options: {
  projectId: string
  threadId: string
  target: ChatResolvedTarget
  request: RuntimeDebugRunInput
  signal: AbortSignal
  onRunCreated: (runId: string) => void
}) {
  const client = createLanggraphClient(options.projectId)
  return client.runs.stream(options.threadId, options.target.resolvedTargetId, {
    ...buildRuntimeDebugRunPayload(options.request),
    signal: options.signal,
    onRunCreated: ({ run_id }) => options.onRunCreated(run_id)
  })
}
