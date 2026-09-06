type RuntimeObject = Record<string, unknown>

type RuntimeToolsOverride = {
  modelId?: string
  enableTools?: boolean
  toolNames?: string[]
}

type RuntimeRunOptionsInput = {
  modelId: string
  systemPrompt: string
  enableTools: boolean
  toolNames: string[]
  temperature: string
  maxTokens: string
}

export type AssistantRuntimePayload = {
  graph_id?: string
  name?: string
  description?: string
  status?: 'active' | 'disabled'
  config?: RuntimeObject
  context?: RuntimeObject
  metadata?: RuntimeObject
}

type AssistantDraftPayloadInput = {
  graphId?: string
  name?: string
  description?: string
  status?: 'active' | 'disabled'
  config?: RuntimeObject
  context?: RuntimeObject
  metadata?: RuntimeObject
  runtimeModelId?: string
  runtimeEnableTools?: boolean
  runtimeToolNames?: string[]
}

const TRUSTED_RUNTIME_CONTEXT_KEYS = [
  'user_id',
  'tenant_id',
  'role',
  'permissions',
  'project_id',
  'projectId',
  'x-project-id'
] as const

const PROJECT_SCOPE_ALIAS_KEYS = ['project_id', 'projectId', 'x-project-id'] as const

const RUNTIME_CONTEXT_BUSINESS_KEYS = [
  'model_id',
  'system_prompt',
  'temperature',
  'max_tokens',
  'top_p',
  'enable_tools',
  'tools'
] as const

function stripKeys(payload: RuntimeObject, keys: readonly string[]): RuntimeObject {
  const nextPayload = { ...payload }
  for (const key of keys) {
    delete nextPayload[key]
  }
  return nextPayload
}

function moveRuntimeBusinessFieldsIntoContext(source: RuntimeObject, context: RuntimeObject) {
  const nextSource = { ...source }
  const nextContext = { ...context }

  for (const key of RUNTIME_CONTEXT_BUSINESS_KEYS) {
    if (!(key in nextSource)) {
      continue
    }

    const value = nextSource[key]
    delete nextSource[key]
    if (value === undefined || value === null || key in nextContext) {
      continue
    }

    nextContext[key] = value
  }

  return {
    config: nextSource,
    context: nextContext
  }
}

function parseNumericInput(raw: string, kind: 'float' | 'int'): number | undefined {
  const normalized = raw.trim()
  if (!normalized) {
    return undefined
  }

  const parsed = kind === 'float' ? Number.parseFloat(normalized) : Number.parseInt(normalized, 10)
  return Number.isFinite(parsed) ? parsed : undefined
}

function assignTrimmedString(
  target: AssistantRuntimePayload,
  key: 'graph_id' | 'name' | 'description',
  value: string | undefined,
  options: { omitBlank?: boolean } = {}
) {
  if (typeof value !== 'string') {
    return
  }

  const normalized = value.trim()
  if (options.omitBlank && !normalized) {
    return
  }

  target[key] = normalized
}

export function normalizeRuntimeContractSections(sections: {
  config?: RuntimeObject
  context?: RuntimeObject
  metadata?: RuntimeObject
}) {
  let nextConfig = stripKeys({ ...(sections.config || {}) }, PROJECT_SCOPE_ALIAS_KEYS)
  let nextContext = stripKeys({ ...(sections.context || {}) }, TRUSTED_RUNTIME_CONTEXT_KEYS)
  const nextMetadata = stripKeys({ ...(sections.metadata || {}) }, PROJECT_SCOPE_ALIAS_KEYS)

  const configNormalized = moveRuntimeBusinessFieldsIntoContext(nextConfig, nextContext)
  nextConfig = configNormalized.config
  nextContext = configNormalized.context

  const configurable = nextConfig.configurable
  const configurableSource =
    configurable && typeof configurable === 'object' && !Array.isArray(configurable)
      ? stripKeys(configurable as RuntimeObject, TRUSTED_RUNTIME_CONTEXT_KEYS)
      : {}
  const configurableNormalized = moveRuntimeBusinessFieldsIntoContext(configurableSource, nextContext)
  nextContext = configurableNormalized.context

  if (Object.keys(configurableNormalized.config).length > 0) {
    nextConfig.configurable = configurableNormalized.config
  } else {
    delete nextConfig.configurable
  }

  const configMetadata =
    nextConfig.metadata && typeof nextConfig.metadata === 'object' && !Array.isArray(nextConfig.metadata)
      ? stripKeys(nextConfig.metadata as RuntimeObject, PROJECT_SCOPE_ALIAS_KEYS)
      : {}
  if (Object.keys(configMetadata).length > 0) {
    nextConfig.metadata = configMetadata
  } else {
    delete nextConfig.metadata
  }

  return {
    config: nextConfig,
    context: nextContext,
    metadata: nextMetadata
  }
}

export function normalizeAssistantRuntimePayload(payload: AssistantRuntimePayload): AssistantRuntimePayload {
  const nextPayload: AssistantRuntimePayload = {}

  assignTrimmedString(nextPayload, 'graph_id', payload.graph_id)
  assignTrimmedString(nextPayload, 'name', payload.name)
  assignTrimmedString(nextPayload, 'description', payload.description)

  if (payload.status) {
    nextPayload.status = payload.status
  }

  const normalizedSections = normalizeRuntimeContractSections({
    config: payload.config,
    context: payload.context,
    metadata: payload.metadata
  })

  if (Object.keys(normalizedSections.config).length > 0) {
    nextPayload.config = normalizedSections.config
  }
  if (Object.keys(normalizedSections.context).length > 0) {
    nextPayload.context = normalizedSections.context
  }
  if (Object.keys(normalizedSections.metadata).length > 0) {
    nextPayload.metadata = normalizedSections.metadata
  }

  return nextPayload
}

export function applyAssistantRuntimeOverrides(context: RuntimeObject, overrides: RuntimeToolsOverride) {
  const nextContext: RuntimeObject = { ...context }
  const normalizedModelId = overrides.modelId?.trim() || ''

  if (normalizedModelId) {
    nextContext.model_id = normalizedModelId
  } else {
    delete nextContext.model_id
  }

  if (overrides.enableTools) {
    nextContext.enable_tools = true
    const cleanedTools = (overrides.toolNames || []).map((item) => item.trim()).filter(Boolean)
    if (cleanedTools.length > 0) {
      nextContext.tools = cleanedTools
    } else {
      delete nextContext.tools
    }
  } else {
    delete nextContext.enable_tools
    delete nextContext.tools
  }

  return nextContext
}

export function buildAssistantDraftPayload(input: AssistantDraftPayloadInput): AssistantRuntimePayload {
  const contextWithOverrides = applyAssistantRuntimeOverrides(input.context || {}, {
    modelId: input.runtimeModelId,
    enableTools: input.runtimeEnableTools,
    toolNames: input.runtimeToolNames
  })

  const normalizedPayload = normalizeAssistantRuntimePayload({
    graph_id: input.graphId,
    name: input.name,
    description: input.description,
    status: input.status,
    config: input.config,
    context: contextWithOverrides,
    metadata: input.metadata
  })

  const nextPayload: AssistantRuntimePayload = {}

  assignTrimmedString(nextPayload, 'graph_id', normalizedPayload.graph_id, { omitBlank: true })
  assignTrimmedString(nextPayload, 'name', normalizedPayload.name, { omitBlank: true })
  assignTrimmedString(nextPayload, 'description', normalizedPayload.description, { omitBlank: true })

  if (normalizedPayload.status) {
    nextPayload.status = normalizedPayload.status
  }
  if (normalizedPayload.config && Object.keys(normalizedPayload.config).length > 0) {
    nextPayload.config = normalizedPayload.config
  }
  if (normalizedPayload.context && Object.keys(normalizedPayload.context).length > 0) {
    nextPayload.context = normalizedPayload.context
  }
  if (normalizedPayload.metadata && Object.keys(normalizedPayload.metadata).length > 0) {
    nextPayload.metadata = normalizedPayload.metadata
  }

  return nextPayload
}

export function buildChatRunSubmitOptions(runOptions: RuntimeRunOptionsInput): {
  config?: RuntimeObject
} {
  const platformRuntime: RuntimeObject = {}

  const normalizedModelId = runOptions.modelId.trim()
  if (normalizedModelId) {
    platformRuntime.model_id = normalizedModelId
  }

  const temperature = parseNumericInput(runOptions.temperature, 'float')
  if (temperature !== undefined) {
    platformRuntime.temperature = temperature
  }

  const maxTokens = parseNumericInput(runOptions.maxTokens, 'int')
  if (maxTokens !== undefined) {
    platformRuntime.max_tokens = maxTokens
  }

  return Object.keys(platformRuntime).length > 0
    ? { config: { configurable: { platform_runtime: platformRuntime } } }
    : { config: {} }
}
