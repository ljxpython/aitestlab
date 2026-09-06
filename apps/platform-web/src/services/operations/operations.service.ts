import { platformApiBaseUrl, platformHttpClient, resolveAuthorizedAccessToken } from '@/services/http/client'
import type {
  OperationArchiveScope,
  OperationArtifactCleanupResult,
  OperationBulkMutationResult,
  ManagementDownload,
  ManagementOperation,
  ManagementOperationPage,
  OperationStatus
} from '@/types/management'

export type ListOperationsOptions = {
  projectId?: string
  kind?: string
  kinds?: string[]
  status?: OperationStatus
  statuses?: OperationStatus[]
  requestedBy?: string
  archiveScope?: OperationArchiveScope
  limit?: number
  offset?: number
}

export type SubmitOperationPayload = {
  kind: string
  project_id?: string
  idempotency_key?: string
  input_payload?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export type OperationPageStreamEvent =
  | {
      event: 'page'
      data: ManagementOperationPage
    }
  | {
      event: 'heartbeat'
      data: { at?: string }
    }

export async function listOperations(options?: ListOperationsOptions): Promise<ManagementOperationPage> {
  const response = await platformHttpClient.get('/api/operations', {
    params: {
      project_id: options?.projectId?.trim() || undefined,
      kind: options?.kind?.trim() || undefined,
      kinds: options?.kinds?.filter((item) => item.trim()).map((item) => item.trim()) || undefined,
      status: options?.status || undefined,
      statuses: options?.statuses?.length ? options.statuses : undefined,
      requested_by: options?.requestedBy?.trim() || undefined,
      archive_scope: options?.archiveScope || 'exclude',
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0
    }
  })
  return response.data as ManagementOperationPage
}

export async function getOperationDetail(operationId: string): Promise<ManagementOperation> {
  const response = await platformHttpClient.get(`/api/operations/${encodeURIComponent(operationId)}`)
  return response.data as ManagementOperation
}

export async function submitOperation(payload: SubmitOperationPayload): Promise<ManagementOperation> {
  const projectId = payload.project_id?.trim()
  const response = await platformHttpClient.post('/api/operations', payload, {
    headers: projectId ? { 'x-project-id': projectId } : undefined
  })
  return response.data as ManagementOperation
}

export async function cancelOperation(operationId: string): Promise<ManagementOperation> {
  const response = await platformHttpClient.post(`/api/operations/${encodeURIComponent(operationId)}/cancel`)
  return response.data as ManagementOperation
}

export async function bulkCancelOperations(operationIds: string[]): Promise<OperationBulkMutationResult> {
  const response = await platformHttpClient.post('/api/operations/bulk/cancel', {
    operation_ids: operationIds
  })
  return response.data as OperationBulkMutationResult
}

export async function bulkArchiveOperations(operationIds: string[]): Promise<OperationBulkMutationResult> {
  const response = await platformHttpClient.post('/api/operations/bulk/archive', {
    operation_ids: operationIds
  })
  return response.data as OperationBulkMutationResult
}

export async function bulkRestoreOperations(operationIds: string[]): Promise<OperationBulkMutationResult> {
  const response = await platformHttpClient.post('/api/operations/bulk/restore', {
    operation_ids: operationIds
  })
  return response.data as OperationBulkMutationResult
}

export async function cleanupExpiredOperationArtifacts(limit = 100): Promise<OperationArtifactCleanupResult> {
  const response = await platformHttpClient.post('/api/operations/artifacts/cleanup', undefined, {
    params: {
      limit
    }
  })
  return response.data as OperationArtifactCleanupResult
}

function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) {
    return null
  }
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const plainMatch = header.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1] ?? null
}

export async function downloadOperationArtifact(operationId: string): Promise<ManagementDownload> {
  const response = await platformHttpClient.get(`/api/operations/${encodeURIComponent(operationId)}/artifact`, {
    responseType: 'blob'
  })
  return {
    blob: response.data as Blob,
    filename: parseContentDispositionFilename(String(response.headers['content-disposition'] || '')),
    contentType: String(response.headers['content-type'] || '')
  }
}

export async function* createOperationPageStream(
  options: ListOperationsOptions & {
    signal?: AbortSignal
  }
): AsyncIterable<OperationPageStreamEvent> {
  const accessToken = (await resolveAuthorizedAccessToken()).trim()
  if (!accessToken) {
    throw new Error('missing_platform_v2_session')
  }

  const searchParams = new URLSearchParams()
  if (options.projectId?.trim()) {
    searchParams.set('project_id', options.projectId.trim())
  }
  if (options.kind?.trim()) {
    searchParams.set('kind', options.kind.trim())
  }
  for (const item of options.kinds || []) {
    const normalized = item.trim()
    if (normalized) {
      searchParams.append('kinds', normalized)
    }
  }
  if (options.status) {
    searchParams.set('status', options.status)
  }
  for (const item of options.statuses || []) {
    searchParams.append('statuses', item)
  }
  if (options.requestedBy?.trim()) {
    searchParams.set('requested_by', options.requestedBy.trim())
  }
  searchParams.set('archive_scope', options.archiveScope || 'exclude')
  searchParams.set('limit', String(options.limit ?? 50))
  searchParams.set('offset', String(options.offset ?? 0))

  const response = await fetch(`${platformApiBaseUrl}/api/operations/stream?${searchParams.toString()}`, {
    method: 'GET',
    headers: {
      Accept: 'text/event-stream',
      Authorization: `Bearer ${accessToken}`
    },
    signal: options.signal
  })

  if (!response.ok) {
    throw await buildOperationStreamHttpError(response)
  }

  if (!response.body) {
    throw new Error('operation_stream_unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    buffer = buffer.replace(/\r\n/g, '\n')

    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const rawBlock = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const parsed = parseOperationStreamBlock(rawBlock)
      if (parsed) {
        yield parsed
      }
      boundary = buffer.indexOf('\n\n')
    }

    if (done) {
      const tail = parseOperationStreamBlock(buffer)
      if (tail) {
        yield tail
      }
      break
    }
  }
}

export function getOperationFailureMessage(operation: ManagementOperation): string {
  const errorMessage = operation.error_payload?.message
  if (typeof errorMessage === 'string' && errorMessage.trim()) {
    return errorMessage.trim()
  }
  if (operation.status === 'cancelled') {
    return '操作已取消'
  }
  return `操作 ${operation.kind} 执行失败`
}

async function buildOperationStreamHttpError(response: Response): Promise<{
  status: number
  message: string
}> {
  const contentType = response.headers.get('content-type') || ''

  if (contentType.includes('application/json')) {
    const payload = (await response.json().catch(() => null)) as Record<string, unknown> | null
    const detail = payload?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return { status: response.status, message: detail.trim() }
    }
    const message = payload?.message
    if (typeof message === 'string' && message.trim()) {
      return { status: response.status, message: message.trim() }
    }
  }

  const fallbackText = await response.text().catch(() => '')
  return {
    status: response.status,
    message: fallbackText.trim() || `operation_stream_request_failed:${response.status}`
  }
}

function parseOperationStreamBlock(rawBlock: string): OperationPageStreamEvent | null {
  const normalized = rawBlock.replace(/\r/g, '').trim()
  if (!normalized) {
    return null
  }

  let eventName = 'message'
  const dataLines: string[] = []

  for (const line of normalized.split('\n')) {
    if (!line || line.startsWith(':')) {
      continue
    }
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim() || 'message'
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  const rawData = dataLines.join('\n')
  const payload = JSON.parse(rawData) as ManagementOperationPage | { at?: string }

  if (eventName === 'heartbeat') {
    return {
      event: 'heartbeat',
      data: payload as { at?: string }
    }
  }

  return {
    event: 'page',
    data: payload as ManagementOperationPage
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function isTerminalStatus(status: OperationStatus) {
  return status === 'succeeded' || status === 'failed' || status === 'cancelled'
}

export async function waitForOperationTerminalState(
  operationId: string,
  options?: {
    pollMs?: number
    timeoutMs?: number
  }
): Promise<ManagementOperation> {
  const pollMs = options?.pollMs ?? 1000
  const timeoutMs = options?.timeoutMs ?? 60000
  const startedAt = Date.now()

  while (true) {
    const current = await getOperationDetail(operationId)
    if (isTerminalStatus(current.status)) {
      return current
    }

    if (Date.now() - startedAt >= timeoutMs) {
      throw new Error(`操作 ${operationId} 等待超时，请稍后到 operations 中心查看状态。`)
    }

    await sleep(pollMs)
  }
}
