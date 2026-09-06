import {
  submitOperation,
  waitForOperationTerminalState
} from '@/services/operations/operations.service'
import { platformHttpClient } from '@/services/http/client'
import type {
  ManagementOperation,
  RuntimeModelItem,
  RuntimeModelsResponse,
  RuntimeToolsResponse
} from '@/types/management'

export type RuntimeModelInput = {
  provider: string
  display_name: string
  base_url: string
  protocol: string
  model: string
  api_key?: string
  enabled?: boolean
}

function buildRuntimeHeaders(projectId?: string) {
  const normalizedProjectId = projectId?.trim()
  return normalizedProjectId
    ? {
        'x-project-id': normalizedProjectId
      }
    : undefined
}

function runtimeOperationKind(resource: 'models' | 'tools' | 'graphs') {
  return `runtime.${resource}.refresh`
}

export async function listRuntimeModels(projectId?: string): Promise<RuntimeModelsResponse> {
  const response = await platformHttpClient.get('/api/runtime/models', {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeModelsResponse
}

export async function createRuntimeModel(
  projectId: string,
  payload: RuntimeModelInput
): Promise<RuntimeModelItem> {
  const response = await platformHttpClient.post('/api/runtime/models', payload, {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeModelItem
}

export async function updateRuntimeModel(
  projectId: string,
  modelId: string,
  payload: Partial<RuntimeModelInput>
): Promise<RuntimeModelItem> {
  const response = await platformHttpClient.patch(`/api/runtime/models/${encodeURIComponent(modelId)}`, payload, {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeModelItem
}

export async function listRuntimeTools(projectId?: string): Promise<RuntimeToolsResponse> {
  const response = await platformHttpClient.get('/api/runtime/tools', {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeToolsResponse
}

export async function submitRuntimeRefreshOperation(
  resource: 'models' | 'tools' | 'graphs',
  projectId?: string
): Promise<ManagementOperation> {
  return submitOperation({
    kind: runtimeOperationKind(resource),
    project_id: projectId?.trim() || undefined,
    idempotency_key: `${runtimeOperationKind(resource)}:${projectId?.trim() || 'platform'}:${Date.now()}`,
    input_payload: {
      resource
    },
    metadata: {
      resource,
      source: 'platform-web'
    }
  })
}

export async function waitForRuntimeRefreshOperation(
  operationId: string,
  options?: {
    pollMs?: number
    timeoutMs?: number
  }
): Promise<ManagementOperation> {
  return waitForOperationTerminalState(operationId, options)
}
