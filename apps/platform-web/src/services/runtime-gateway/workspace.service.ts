import type { Thread as LanggraphThread } from '@langchain/langgraph-sdk'
import { isAxiosError } from 'axios'
import { createLanggraphClient } from '@/services/langgraph/client'
import { platformHttpClient } from '@/services/http/client'
import type { ManagementThread, ThreadHistoryEntry } from '@/types/management'
import { getThreadListSearchText } from '@/utils/threads'

export type RuntimeGatewayErrorKind =
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'bad_request'
  | 'server_error'
  | 'unknown'

export type RuntimeGatewayErrorMeta = {
  kind: RuntimeGatewayErrorKind
  status: number | null
  code: string
  message: string
}

export type RuntimeGatewayTargetDescriptor = {
  targetType: 'assistant' | 'graph'
  resolvedTargetId: string
  displayName: string
  assistantId?: string
  assistantName?: string
  graphId?: string
  graphName?: string
}

export type RuntimeThreadsPage = {
  items: ManagementThread[]
  total: number
  limit: number
  offset: number
}

export type RuntimeThreadSnapshot = {
  detail: ManagementThread
  state: Record<string, unknown> | null
  history: ThreadHistoryEntry[]
  stateError: RuntimeGatewayErrorMeta | null
  historyError: RuntimeGatewayErrorMeta | null
}

export type RuntimeThreadCreateOptions = {
  sessionKind?: 'legacy_debug'
}

type CountResponse = {
  count?: number
  total?: number
}

export type ListRuntimeThreadsOptions = {
  limit?: number
  offset?: number
  query?: string
  threadId?: string
  assistantId?: string
  graphId?: string
  status?: string
}

function normalizeThread(thread: LanggraphThread<Record<string, unknown>>): ManagementThread {
  const runtimeThread = thread as LanggraphThread<Record<string, unknown>> & {
    error?: ManagementThread['error']
  }

  return {
    thread_id: runtimeThread.thread_id,
    status: runtimeThread.status,
    created_at: runtimeThread.created_at,
    updated_at: runtimeThread.updated_at,
    metadata: runtimeThread.metadata,
    values: runtimeThread.values,
    error: runtimeThread.error ?? null
  }
}

function buildThreadMetadata(target: RuntimeGatewayTargetDescriptor) {
  if (target.targetType === 'graph') {
    return {
      target_type: 'graph',
      target_display_name: target.displayName,
      assistant_id: target.resolvedTargetId,
      graph_id: target.graphId || target.resolvedTargetId,
      graph_name: target.graphName || target.displayName
    }
  }

  return {
    target_type: 'assistant',
    target_display_name: target.displayName,
    assistant_id: target.assistantId || target.resolvedTargetId,
    assistant_name: target.assistantName || target.displayName
  }
}

function extractErrorStatus(error: unknown): number | null {
  if (isAxiosError(error)) {
    return error.response?.status ?? null
  }

  if (error && typeof error === 'object') {
    const candidate = (error as { status?: unknown; statusCode?: unknown }).status
    if (typeof candidate === 'number') {
      return candidate
    }

    const statusCode = (error as { status?: unknown; statusCode?: unknown }).statusCode
    if (typeof statusCode === 'number') {
      return statusCode
    }

    const message = (error as { message?: unknown }).message
    if (typeof message === 'string') {
      const protocolStatus = message.match(/(?:Protocol request failed|HTTP)\s*:?\s*(\d{3})/i)
      if (protocolStatus) {
        return Number(protocolStatus[1])
      }
    }
  }

  return null
}

function extractErrorCode(error: unknown): string {
  if (isAxiosError(error)) {
    const data = error.response?.data
    if (data && typeof data === 'object' && typeof (data as { code?: unknown }).code === 'string') {
      return ((data as { code?: string }).code || '').trim()
    }
    if (
      data &&
      typeof data === 'object' &&
      (data as { error?: unknown }).error &&
      typeof (data as { error: unknown }).error === 'object'
    ) {
      const code = ((data as { error: { code?: unknown } }).error.code)
      if (typeof code === 'string' && code.trim()) {
        return code.trim()
      }
    }
  }

  if (error && typeof error === 'object' && typeof (error as { code?: unknown }).code === 'string') {
    return ((error as { code?: string }).code || '').trim()
  }

  if (error && typeof error === 'object') {
    const nested = (error as { error?: unknown }).error
    if (nested && typeof nested === 'object' && typeof (nested as { code?: unknown }).code === 'string') {
      return ((nested as { code: string }).code || '').trim()
    }
  }

  return ''
}

function extractErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const data = error.response?.data
    if (data && typeof data === 'object') {
      for (const key of ['message', 'detail', 'error']) {
        const candidate = (data as Record<string, unknown>)[key]
        if (typeof candidate === 'string' && candidate.trim()) {
          return candidate.trim()
        }
      }
      const nested = (data as { error?: unknown }).error
      if (nested && typeof nested === 'object') {
        const message = (nested as { message?: unknown }).message
        if (typeof message === 'string' && message.trim()) {
          return message.trim()
        }
      }
    }

    if (typeof error.message === 'string' && error.message.trim()) {
      return error.message.trim()
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message.trim()
  }

  if (error && typeof error === 'object') {
    for (const key of ['message', 'detail', 'error']) {
      const candidate = (error as Record<string, unknown>)[key]
      if (typeof candidate === 'string' && candidate.trim()) {
        return candidate.trim()
      }
    }
    const nested = (error as { error?: unknown }).error
    if (nested && typeof nested === 'object') {
      const message = (nested as { message?: unknown }).message
      if (typeof message === 'string' && message.trim()) {
        return message.trim()
      }
    }
  }

  return fallback
}

export function normalizeRuntimeGatewayMessage(error: unknown, message: string): string {
  const fields =
    error && typeof error === 'object'
      ? ['error', 'type', 'name', 'code']
          .map((key) => (error as Record<string, unknown>)[key])
          .filter((value): value is string => typeof value === 'string')
      : []

  if (/openaipermissiondeniederror|cloudflare|<!doctype html|<html[\s>]/i.test([...fields, message].join(' '))) {
    return '模型上游请求被拒绝：当前模型网关返回权限或 Cloudflare 拦截，请检查 base_url、API key、模型部署和网络。'
  }

  return message
}

function resolveRuntimeGatewayErrorKind(status: number | null): RuntimeGatewayErrorKind {
  if (status === 401) {
    return 'unauthorized'
  }
  if (status === 403) {
    return 'forbidden'
  }
  if (status === 404) {
    return 'not_found'
  }
  if (status === 409) {
    return 'conflict'
  }
  if (status === 400 || status === 422) {
    return 'bad_request'
  }
  if (typeof status === 'number' && status >= 500) {
    return 'server_error'
  }
  return 'unknown'
}

export function normalizeRuntimeGatewayError(
  error: unknown,
  fallbackMessage: string
): RuntimeGatewayErrorMeta {
  const status = extractErrorStatus(error)
  const code = extractErrorCode(error)
  const rawMessage = extractErrorMessage(error, fallbackMessage)
  let message = normalizeRuntimeGatewayMessage(error, rawMessage)
  if (code === 'thread_active_run_conflict') {
    message = '当前线程已有运行中的任务，请先处理待确认事项或点击“停止生成”后再发送。'
  } else if (code === 'run_start_in_progress') {
    message = '上一条消息仍在启动中，页面正在同步线程状态，请稍候。'
  } else if (code === 'idempotency_key_conflict') {
    message = '请求标识已被其他消息使用，请重新发送。'
  } else if (
    status === 409 &&
    (!message.trim() || /^protocol request failed:/i.test(message))
  ) {
    message = '当前线程已有运行中的任务，请先处理待确认事项或点击“停止生成”后再发送。'
  }
  return {
    kind: resolveRuntimeGatewayErrorKind(status),
    status,
    code,
    message
  }
}

export function resolveRuntimePermissionDescription(error: RuntimeGatewayErrorMeta | null): string {
  if (!error) {
    return ''
  }

  if (error.kind === 'unauthorized') {
    return '当前登录态已经失效，运行工作台无法继续访问。请重新登录后再试。'
  }

  if (error.kind === 'forbidden') {
    return '当前账号没有访问这个项目运行工作台的权限，线程、历史和运行上下文都不会返回。'
  }

  return ''
}

export function buildRuntimeSnapshotWarning(snapshot: RuntimeThreadSnapshot): string {
  const failedSections: string[] = []
  if (snapshot.stateError) {
    failedSections.push('状态')
  }
  if (snapshot.historyError) {
    failedSections.push('历史')
  }

  if (failedSections.length === 0) {
    return ''
  }

  return `线程基础信息已加载，但${failedSections.join('和')}刷新失败，当前页面展示的可能不是最新结果。`
}

export async function listRuntimeThreadsPage(
  projectId: string,
  options?: ListRuntimeThreadsOptions
): Promise<RuntimeThreadsPage> {
  const client = platformHttpClient
  const limit = options?.limit ?? 20
  const offset = options?.offset ?? 0

  if (!projectId) {
    return { items: [], total: 0, limit, offset }
  }

  const metadata: Record<string, unknown> = {}
  if (options?.assistantId?.trim()) {
    metadata.assistant_id = options.assistantId.trim()
  }
  if (options?.graphId?.trim()) {
    metadata.graph_id = options.graphId.trim()
  }

  const payload: Record<string, unknown> = {
    limit,
    offset,
    sort_by: 'updated_at',
    sort_order: 'desc',
    select: ['thread_id', 'metadata', 'status', 'created_at', 'updated_at']
  }

  if (Object.keys(metadata).length > 0) {
    payload.metadata = metadata
  }
  if (options?.status?.trim()) {
    payload.status = options.status.trim()
  }

  const headers = {
    'x-project-id': projectId
  }

  const [itemsResponse, countResponse] = await Promise.all([
    client
      .post('/api/langgraph/threads/search', payload, { headers })
      .then((response) => response.data as ManagementThread[] | { items?: ManagementThread[] })
      .catch(async () => {
        const fallbackPayload = { ...payload }
        delete fallbackPayload.select
        const response = await client.post('/api/langgraph/threads/search', fallbackPayload, {
          headers
        })
        return response.data as ManagementThread[] | { items?: ManagementThread[] }
      }),
    client
      .post('/api/langgraph/threads/count', payload, { headers })
      .then((response) => response.data as CountResponse)
      .catch(() => ({ count: 0 }))
  ])

  const rows = Array.isArray(itemsResponse)
    ? itemsResponse
    : Array.isArray(itemsResponse.items)
      ? itemsResponse.items
      : []

  const normalizedRows = rows.map((thread) => ({
    thread_id: thread.thread_id,
    metadata: thread.metadata,
    status: thread.status,
    created_at: thread.created_at,
    updated_at: thread.updated_at,
    values: thread.values,
    error: thread.error ?? null
  })) as ManagementThread[]

  const query = options?.query?.trim().toLowerCase() || ''
  const threadIdQuery = options?.threadId?.trim().toLowerCase() || ''

  const filtered = query
    ? normalizedRows.filter((thread) => getThreadListSearchText(thread).includes(query))
    : normalizedRows

  const filteredByThreadId = threadIdQuery
    ? filtered.filter((thread) => {
        const normalizedThreadId = typeof thread.thread_id === 'string' ? thread.thread_id.toLowerCase() : ''
        return normalizedThreadId.includes(threadIdQuery)
      })
    : filtered

  const total =
    query.length > 0 || threadIdQuery.length > 0
      ? filteredByThreadId.length
      : typeof countResponse.count === 'number'
        ? countResponse.count
        : typeof (countResponse as CountResponse).total === 'number'
          ? ((countResponse as CountResponse).total ?? filteredByThreadId.length)
          : filteredByThreadId.length

  return {
    items: filteredByThreadId,
    total,
    limit,
    offset
  }
}

export async function getRuntimeThreadDetail(projectId: string, threadId: string): Promise<ManagementThread> {
  const client = platformHttpClient
  const response = await client.get(`/api/langgraph/threads/${encodeURIComponent(threadId)}`, {
    headers: {
      'x-project-id': projectId
    }
  })
  return response.data as ManagementThread
}

export async function getRuntimeThreadHistoryPage(
  projectId: string,
  threadId: string,
  options?: { limit?: number; before?: string }
): Promise<ThreadHistoryEntry[]> {
  const client = platformHttpClient
  if (!projectId) {
    return []
  }

  const payload: Record<string, unknown> = {
    limit: options?.limit ?? 20
  }

  if (options?.before?.trim()) {
    payload.before = options.before.trim()
  }

  const response = await client.post(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/history`,
    payload,
    {
      headers: {
        'x-project-id': projectId
      }
    }
  )

  const data = response.data as ThreadHistoryEntry[] | { items?: ThreadHistoryEntry[] }
  return Array.isArray(data) ? data : Array.isArray(data.items) ? data.items : []
}

export async function getRuntimeThreadState(
  projectId: string,
  threadId: string
): Promise<Record<string, unknown>> {
  const client = platformHttpClient
  const response = await client.get(`/api/langgraph/threads/${encodeURIComponent(threadId)}/state`, {
    headers: {
      'x-project-id': projectId
    }
  })
  return response.data as Record<string, unknown>
}

export async function getRuntimeThreadSnapshot(
  projectId: string,
  threadId: string,
  options?: { summary?: ManagementThread | null; historyLimit?: number }
): Promise<RuntimeThreadSnapshot> {
  const detailPromise = options?.summary
    ? Promise.resolve(options.summary)
    : getRuntimeThreadDetail(projectId, threadId)

  const [detail, stateResult, historyResult] = await Promise.all([
    detailPromise,
    getRuntimeThreadState(projectId, threadId)
      .then((state) => ({
        state,
        error: null as RuntimeGatewayErrorMeta | null
      }))
      .catch((error) => ({
        state: null,
        error: normalizeRuntimeGatewayError(error, '线程状态加载失败')
      })),
    getRuntimeThreadHistoryPage(projectId, threadId, { limit: options?.historyLimit ?? 20 })
      .then((history) => ({
        history,
        error: null as RuntimeGatewayErrorMeta | null
      }))
      .catch((error) => ({
        history: [],
        error: normalizeRuntimeGatewayError(error, '线程历史加载失败')
      }))
  ])

  return {
    detail,
    state: stateResult.state,
    history: historyResult.history,
    stateError: stateResult.error,
    historyError: historyResult.error
  }
}

export async function createRuntimeThread(
  projectId: string,
  target: RuntimeGatewayTargetDescriptor,
  options: RuntimeThreadCreateOptions = {}
): Promise<ManagementThread> {
  const client = createLanggraphClient(projectId)
  const createdThread = (await client.threads.create({
    metadata: {
      ...buildThreadMetadata(target),
      ...(options.sessionKind ? { session_kind: options.sessionKind } : {})
    }
  })) as LanggraphThread<Record<string, unknown>>

  return normalizeThread(createdThread)
}

export async function cancelRuntimeRun(
  projectId: string,
  threadId: string,
  runId: string
): Promise<void> {
  const client = createLanggraphClient(projectId)
  await client.runs.cancel(threadId, runId, false, 'interrupt')
}

export async function getRuntimeRunStatus(
  projectId: string,
  threadId: string,
  runId: string
): Promise<string> {
  const client = createLanggraphClient(projectId)
  const run = await client.runs.get(threadId, runId) as { status?: unknown }
  return typeof run.status === 'string' ? run.status : ''
}

export async function updateRuntimeThreadState(
  projectId: string,
  threadId: string,
  values: Record<string, unknown>
): Promise<void> {
  const client = createLanggraphClient(projectId)
  await client.threads.updateState(threadId, { values })
}

export async function deleteRuntimeThread(projectId: string, threadId: string): Promise<void> {
  const client = createLanggraphClient(projectId)
  await client.threads.delete(threadId)
}
