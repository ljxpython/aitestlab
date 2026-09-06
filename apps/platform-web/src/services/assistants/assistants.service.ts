import { platformHttpClient } from '@/services/http/client'
import {
  submitOperation,
  waitForOperationTerminalState
} from '@/services/operations/operations.service'
import {
  normalizeAssistantRuntimePayload,
  type AssistantRuntimePayload
} from '@/services/runtime/runtime-contract'
import type {
  ManagementAssistant,
  ManagementAssistantListResponse,
  ManagementOperation
} from '@/types/management'

function getProjectHeaders(projectId?: string) {
  return projectId
    ? {
        'x-project-id': projectId
      }
    : undefined
}

export async function listAssistantsPage(
  projectId: string,
  options?: {
    limit?: number
    offset?: number
    query?: string
    graphId?: string
  }
): Promise<ManagementAssistantListResponse> {
  if (!projectId) {
    return { items: [], total: 0 }
  }

  const response = await platformHttpClient.get(`/api/projects/${projectId}/agents`, {
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined,
      graph_id: options?.graphId?.trim() || undefined
    }
  })

  return response.data as ManagementAssistantListResponse
}

export async function createAssistant(
  projectId: string,
  payload: AssistantRuntimePayload
): Promise<ManagementAssistant> {
  const response = await platformHttpClient.post(
    `/api/projects/${projectId}/agents`,
    normalizeAssistantRuntimePayload(payload)
  )
  return response.data as ManagementAssistant
}

export async function getAssistant(
  assistantId: string,
  projectId?: string
): Promise<ManagementAssistant> {
  const response = await platformHttpClient.get(`/api/agents/${assistantId}`, {
    headers: getProjectHeaders(projectId)
  })

  return response.data as ManagementAssistant
}

export async function updateAssistant(
  assistantId: string,
  payload: AssistantRuntimePayload,
  projectId?: string
): Promise<ManagementAssistant> {
  const response = await platformHttpClient.patch(
    `/api/agents/${assistantId}`,
    normalizeAssistantRuntimePayload(payload),
    {
      headers: getProjectHeaders(projectId)
    }
  )

  return response.data as ManagementAssistant
}

export async function resyncAssistant(
  assistantId: string,
  projectId?: string
): Promise<ManagementAssistant> {
  const response = await platformHttpClient.post(
    `/api/agents/${assistantId}/resync`,
    {},
    {
      headers: getProjectHeaders(projectId)
    }
  )

  return response.data as ManagementAssistant
}

export async function resyncAssistantByOperation(
  assistantId: string,
  projectId: string,
  options?: {
    idempotencyKey?: string
  }
): Promise<ManagementOperation> {
  const submitted = await submitOperation({
    kind: 'assistant.resync',
    project_id: projectId,
    idempotency_key: options?.idempotencyKey,
    input_payload: {
      assistant_id: assistantId
    }
  })
  return waitForOperationTerminalState(submitted.id, {
    pollMs: 1000,
    timeoutMs: 60000
  })
}

export async function deleteAssistant(
  assistantId: string,
  options?: {
    deleteRuntime?: boolean
    deleteThreads?: boolean
  },
  projectId?: string
): Promise<{ ok: boolean }> {
  const response = await platformHttpClient.delete(`/api/agents/${assistantId}`, {
    params: {
      delete_runtime: options?.deleteRuntime || undefined,
      delete_threads: options?.deleteThreads || undefined
    },
    headers: getProjectHeaders(projectId)
  })

  return response.data as { ok: boolean }
}

export async function getAssistantParameterSchema(
  graphId: string,
  projectId?: string
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.get(
    `/api/graphs/${encodeURIComponent(graphId)}/assistant-parameter-schema`,
    {
      headers: getProjectHeaders(projectId)
    }
  )

  return response.data as Record<string, unknown>
}

export async function findAssistantByTargetId(
  projectId: string,
  targetAssistantId: string
): Promise<ManagementAssistant | null> {
  const normalizedTargetId = targetAssistantId.trim()
  if (!projectId || !normalizedTargetId) {
    return null
  }

  const payload = await listAssistantsPage(
    projectId,
    {
      limit: 50,
      offset: 0,
      query: normalizedTargetId
    }
  )

  return (
    payload.items.find((item) => {
      const assistantId = item.id?.trim() || ''
      const langgraphAssistantId = item.langgraph_assistant_id?.trim() || ''
      return assistantId === normalizedTargetId || langgraphAssistantId === normalizedTargetId
    }) || null
  )
}

// Product-facing aliases. Keep the module path and wire format stable while
// the historical Assistant API is retired.
export const listAgentsPage = listAssistantsPage
export const createAgent = createAssistant
export const getAgent = getAssistant
export const updateAgent = updateAssistant
export const resyncAgent = resyncAssistant
export const deleteAgent = deleteAssistant
export const findAgentByTargetId = findAssistantByTargetId
