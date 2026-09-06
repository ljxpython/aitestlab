<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { createAssistant, getAssistantParameterSchema } from '@/services/assistants/assistants.service'
import { listGraphsPage } from '@/services/graphs/graphs.service'
import { buildAssistantDraftPayload } from '@/services/runtime/runtime-contract'
import { listRuntimeModels } from '@/services/runtime/runtime.service'
import type { ManagementGraph, RuntimeModelItem } from '@/types/management'

type SchemaProperty = {
  type?: string
  required?: boolean
}

type SchemaSection = {
  key?: string
  title?: string
  type?: string
  properties?: Record<string, SchemaProperty>
}

type ParameterSchemaResponse = {
  graph_id?: string
  schema_version?: string
  sections?: SchemaSection[]
}

const router = useRouter()
const { activeProjectId, activeProject } = useWorkspaceProjectContext()
const currentProject = activeProject

const graphId = ref('assistant')
const graphOptions = ref<ManagementGraph[]>([])
const graphLoading = ref(false)
const name = ref('')
const description = ref('')
const config = ref('{}')
const context = ref('{}')
const metadata = ref('{}')
const schema = ref<ParameterSchemaResponse | null>(null)
const schemaLoading = ref(false)
const schemaError = ref('')
const configFields = ref<Record<string, string>>({})
const submitting = ref(false)
const error = ref('')
const notice = ref('')
const runtimeModels = ref<RuntimeModelItem[]>([])
const runtimeLoading = ref(false)
const runtimeError = ref('')
const runtimeModelId = ref('')

function parseObjectJson(raw: string, fieldName: string): Record<string, unknown> {
  const normalized = raw.trim()
  if (!normalized) {
    return {}
  }

  const parsed = JSON.parse(normalized)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${fieldName} 必须是 JSON object`)
  }

  return parsed as Record<string, unknown>
}

const sortedGraphOptions = computed(() =>
  [...graphOptions.value].sort((left, right) => left.graph_id.localeCompare(right.graph_id))
)

const configPropertyDefs = computed(() => {
  const sections = Array.isArray(schema.value?.sections) ? schema.value.sections : []
  const configSection = sections.find((section) => section?.key === 'config')
  const properties = configSection?.properties

  if (!properties || typeof properties !== 'object') {
    return [] as Array<{ key: string; type: string; required: boolean }>
  }

  return Object.entries(properties).map(([key, value]) => ({
    key,
    type: typeof value?.type === 'string' ? value.type : 'string',
    required: Boolean(value?.required)
  }))
})

const stats = computed(() => [
  {
    label: '当前项目',
    value: currentProject.value?.name || '未选择',
    hint: activeProjectId.value || '--',
    icon: 'project',
    tone: 'primary'
  },
  {
    label: '可选 Graph',
    value: sortedGraphOptions.value.length,
    hint: graphLoading.value ? '加载中...' : '图目录',
    icon: 'graph',
    tone: 'success'
  },
  {
    label: 'Runtime Models',
    value: runtimeModels.value.length,
    hint: runtimeLoading.value ? '加载中...' : '可选模型',
    icon: 'runtime',
    tone: 'warning'
  },
])

const requestBodyPreview = computed(() => {
  return buildAssistantDraftPayload({
    graphId: graphId.value,
    name: name.value,
    description: description.value,
    config: parseObjectJson(config.value, 'config'),
    context: parseObjectJson(context.value, 'context'),
    metadata: parseObjectJson(metadata.value, 'metadata'),
    runtimeModelId: runtimeModelId.value,
  })
})

function syncConfigFields() {
  try {
    const baseConfig = parseObjectJson(config.value, 'config')
    const nextFields: Record<string, string> = {}
    for (const field of configPropertyDefs.value) {
      const rawValue = baseConfig[field.key]
      nextFields[field.key] =
        rawValue === null || rawValue === undefined
          ? ''
          : typeof rawValue === 'string'
            ? rawValue
            : String(rawValue)
    }
    configFields.value = nextFields
  } catch {
    configFields.value = {}
  }
}

function applyConfigFieldValue(key: string, value: string, valueType: string) {
  configFields.value = { ...configFields.value, [key]: value }

  try {
    const currentConfig = parseObjectJson(config.value, 'config')

    if (!value.trim()) {
      delete currentConfig[key]
      config.value = JSON.stringify(currentConfig, null, 2)
      return
    }

    if (valueType === 'number') {
      const parsed = Number(value)
      if (!Number.isFinite(parsed)) {
        return
      }
      currentConfig[key] = parsed
      config.value = JSON.stringify(currentConfig, null, 2)
      return
    }

    if (valueType === 'boolean') {
      currentConfig[key] = value === 'true'
      config.value = JSON.stringify(currentConfig, null, 2)
      return
    }

    currentConfig[key] = value
    config.value = JSON.stringify(currentConfig, null, 2)
  } catch {
    // ignore invalid JSON draft while typing
  }
}

async function loadGraphs() {
  const projectId = activeProjectId.value
  if (!projectId) {
    graphOptions.value = []
    return
  }

  graphLoading.value = true
  try {
    const payload = await listGraphsPage(projectId, { limit: 500, offset: 0 })
    graphOptions.value = payload.items.filter(
      (item): item is ManagementGraph =>
        typeof item.graph_id === 'string' && item.graph_id.trim().length > 0
    )
  } catch {
    graphOptions.value = []
  } finally {
    graphLoading.value = false
  }
}

async function loadRuntime() {
  runtimeLoading.value = true
  runtimeError.value = ''

  try {
    const projectId = activeProjectId.value
    const modelsResponse = await listRuntimeModels(projectId).catch(() => null)

    runtimeModels.value =
      modelsResponse && Array.isArray(modelsResponse.models) ? modelsResponse.models : []
  } catch (loadError) {
    runtimeModels.value = []
    runtimeError.value =
      loadError instanceof Error ? loadError.message : '运行时目录加载失败'
  } finally {
    runtimeLoading.value = false
  }
}

async function loadSchema() {
  const projectId = activeProjectId.value
  const normalizedGraphId = graphId.value.trim()
  if (!projectId || !normalizedGraphId) {
    schema.value = null
    schemaError.value = ''
    return
  }

  schemaLoading.value = true
  schemaError.value = ''

  try {
    schema.value = (await getAssistantParameterSchema(
      normalizedGraphId,
      projectId
    )) as ParameterSchemaResponse
  } catch (loadError) {
    schema.value = null
    schemaError.value =
      loadError instanceof Error ? loadError.message : '参数 schema 加载失败'
  } finally {
    schemaLoading.value = false
  }
}

async function handleSubmit() {
  const projectId = activeProjectId.value
  const normalizedName = name.value.trim()
  const normalizedGraphId = graphId.value.trim()

  if (!projectId) {
    error.value = '请先选择项目'
    return
  }

  if (!normalizedName || !normalizedGraphId) {
    error.value = '名称和 Graph ID 不能为空'
    return
  }

  submitting.value = true
  error.value = ''
  notice.value = ''

  try {
    const payload = requestBodyPreview.value
    const created = await createAssistant(projectId, payload)

    notice.value = `已创建 Agent：${created.name}`
    void router.replace(`/workspace/assistants/${created.id}`)
  } catch (submitError) {
    error.value =
    submitError instanceof Error ? submitError.message : 'Agent 创建失败'
  } finally {
    submitting.value = false
  }
}

watch(
  () => activeProjectId.value,
  () => {
    void loadGraphs()
  },
  { immediate: true }
)

watch(
  () => sortedGraphOptions.value,
  (nextOptions) => {
    if (nextOptions.length === 0) {
      return
    }

    const normalizedGraphId = graphId.value.trim()
    if (normalizedGraphId && nextOptions.some((item) => item.graph_id === normalizedGraphId)) {
      return
    }

    graphId.value = nextOptions[0].graph_id
  },
  { immediate: true }
)

watch(
  () => graphId.value,
  () => {
    void loadSchema()
  },
  { immediate: true }
)

watch([configPropertyDefs, config], () => {
  syncConfigFields()
}, { immediate: true })

watch(
  () => activeProjectId.value,
  () => {
    void loadRuntime()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Agents"
      title="新建 Agent"
      description="按项目创建 Agent，并使用 graph 参数 schema 驱动配置。旧 Assistant 路由仅作为兼容入口。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/assistants')"
        >
          返回列表
        </BaseButton>
      </template>
    </PageHeader>

    <EmptyState
      v-if="!currentProject"
      icon="project"
      title="请先选择项目"
      description="Agent 创建页必须在项目上下文里工作。没有项目，graph 选择、参数校验和最终落库都不成立。"
    />

    <template v-else>
      <StateBanner
        v-if="error"
          title="Agent 创建失败"
        :description="error"
        variant="danger"
      />

      <StateBanner
        v-if="notice"
        title="操作已完成"
        :description="notice"
        variant="success"
      />

      <StateBanner
        v-if="runtimeError"
        title="运行时目录加载失败"
        :description="runtimeError"
        variant="warning"
      />

      <div class="grid gap-4 xl:grid-cols-4">
        <MetricCard
          v-for="itemStat in stats"
          :key="itemStat.label"
          :label="itemStat.label"
          :value="itemStat.value"
          :hint="itemStat.hint"
          :icon="itemStat.icon"
          :tone="itemStat.tone"
        />
      </div>

      <div class="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.95fr)]">
        <SurfaceCard class="space-y-5">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                创建表单
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                选择 graph，填写基础信息，再按 schema 配置参数。
              </div>
            </div>
            <BaseButton
              :disabled="submitting"
              @click="handleSubmit"
            >
              {{ submitting ? '创建中...' : '创建 Agent' }}
            </BaseButton>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <label class="block">
              <span class="pw-input-label">Graph ID</span>
              <BaseSelect
                v-model="graphId"
                :disabled="submitting || graphLoading || sortedGraphOptions.length === 0"
              >
                <option
                  v-if="sortedGraphOptions.length === 0"
                  value=""
                >
                  {{ graphLoading ? '加载图目录中...' : '当前没有可选 graph' }}
                </option>
                <option
                  v-for="option in sortedGraphOptions"
                  :key="option.graph_id"
                  :value="option.graph_id"
                >
                  {{ option.description?.trim() ? `${option.graph_id} - ${option.description}` : option.graph_id }}
                </option>
              </BaseSelect>
            </label>

            <label class="block">
              <span class="pw-input-label">名称</span>
              <input
                v-model="name"
                class="pw-input"
                :disabled="submitting"
              >
            </label>
          </div>

          <label class="block">
            <span class="pw-input-label">描述</span>
            <textarea
              v-model="description"
              rows="4"
              class="pw-input min-h-[120px] resize-y"
              :disabled="submitting"
            />
          </label>

          <div
            v-if="configPropertyDefs.length > 0"
            class="space-y-4 rounded-[24px] border border-gray-100 bg-gray-50/70 px-4 py-4 dark:border-dark-700 dark:bg-dark-900/50"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                Schema 驱动字段
              </div>
              <div class="text-xs text-gray-400 dark:text-dark-400">
                {{ schemaLoading ? '加载中...' : schema?.schema_version || 'dynamic-v1' }}
              </div>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <label
                v-for="field in configPropertyDefs"
                :key="field.key"
                class="block"
              >
                <span class="pw-input-label">
                  {{ field.key }} · {{ field.type }}
                  <span v-if="field.required"> *</span>
                </span>
                <input
                  :value="configFields[field.key] ?? ''"
                  class="pw-input"
                  :placeholder="field.type"
                  :disabled="submitting"
                  @input="applyConfigFieldValue(field.key, ($event.target as HTMLInputElement).value, field.type)"
                >
              </label>
            </div>
          </div>

          <div
            v-else-if="schemaError"
            class="rounded-2xl border border-amber-100 bg-amber-50/80 px-4 py-4 text-sm leading-7 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-100"
          >
            {{ schemaError }}
          </div>

          <div class="space-y-4 rounded-[24px] border border-gray-100 bg-gray-50/70 px-4 py-4 dark:border-dark-700 dark:bg-dark-900/50">
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              Runtime 配置
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="pw-input-label">默认模型</span>
                <BaseSelect
                  v-model="runtimeModelId"
                  :disabled="submitting || runtimeLoading"
                >
                  <option value="">使用默认模型</option>
                  <option
                    v-for="model in runtimeModels"
                    :key="model.id"
                    :value="model.model_id"
                  >
                    {{ model.display_name || model.model_id }}
                  </option>
                </BaseSelect>
              </label>
            </div>
          </div>

          <label class="block">
            <span class="pw-input-label">Config (JSON object)</span>
            <textarea
              v-model="config"
              rows="10"
              class="pw-input min-h-[220px] resize-y font-mono text-xs leading-6"
              :disabled="submitting"
            />
          </label>

          <label class="block">
            <span class="pw-input-label">Context (JSON object)</span>
            <textarea
              v-model="context"
              rows="10"
              class="pw-input min-h-[220px] resize-y font-mono text-xs leading-6"
              :disabled="submitting"
            />
          </label>

          <label class="block">
            <span class="pw-input-label">Metadata (JSON object)</span>
            <textarea
              v-model="metadata"
              rows="10"
              class="pw-input min-h-[220px] resize-y font-mono text-xs leading-6"
              :disabled="submitting"
            />
          </label>
        </SurfaceCard>

        <div class="space-y-6">
          <SurfaceCard class="space-y-4">
            <div class="text-lg font-semibold text-gray-900 dark:text-white">
              当前请求预览
            </div>
            <pre class="overflow-auto whitespace-pre-wrap break-words rounded-[24px] bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ JSON.stringify(requestBodyPreview, null, 2) }}</pre>
          </SurfaceCard>

          <SurfaceCard class="space-y-4">
            <div class="text-lg font-semibold text-gray-900 dark:text-white">
              创建说明
            </div>
            <div class="space-y-3 text-sm leading-7 text-gray-600 dark:text-dark-300">
              <div class="flex items-start gap-3">
                <BaseIcon
                  name="info"
                  size="sm"
                  class="mt-1 text-primary-500"
                />
                <span>创建页会把 graph、基础信息和动态参数统一提交给平台侧，由后端完成项目隔离和参数校验；GraphHarbor 只负责通用执行。</span>
              </div>
              <div class="flex items-start gap-3">
                <BaseIcon
                  name="check"
                  size="sm"
                  class="mt-1 text-emerald-500"
                />
                <span>如果当前 graph 没有 schema-driven 字段，仍然保留 JSON 编辑兜底，不会把页面卡死在“等后端完善”上。</span>
              </div>
            </div>
          </SurfaceCard>
        </div>
      </div>
    </template>
  </section>
</template>
