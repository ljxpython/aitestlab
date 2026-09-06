<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import {
  deleteAssistant,
  getAssistant,
  getAssistantParameterSchema,
  resyncAssistantByOperation,
  updateAssistant
} from '@/services/assistants/assistants.service'
import { getOperationFailureMessage } from '@/services/operations/operations.service'
import { normalizeAssistantRuntimePayload } from '@/services/runtime/runtime-contract'
import { useUiStore } from '@/stores/ui'
import type { ManagementAssistant } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { writeRecentChatTarget } from '@/utils/chatTarget'
import { formatDateTime, shortId } from '@/utils/format'

type SchemaProperty = {
  type?: string
  required?: boolean
}

type SchemaSection = {
  key?: string
  properties?: Record<string, SchemaProperty>
}

type ParameterSchemaResponse = {
  graph_id?: string
  schema_version?: string
  sections?: SchemaSection[]
}

const route = useRoute()
const router = useRouter()
const { activeProjectId, activeProject } = useWorkspaceProjectContext()
const uiStore = useUiStore()
const authorization = useAuthorization()
const currentProject = activeProject
const canManageAssistant = computed(() => authorization.currentProjectCan('project.assistant.write'))

const assistantId = computed(() =>
  typeof route.params.assistantId === 'string' ? route.params.assistantId.trim() : ''
)

const item = ref<ManagementAssistant | null>(null)
const schema = ref<ParameterSchemaResponse | null>(null)
const loading = ref(false)
const saving = ref(false)
const resyncing = ref(false)
const deleting = ref(false)
const schemaLoading = ref(false)
const error = ref('')
const notice = ref('')
const showDeleteDialog = ref(false)

const editName = ref('')
const editDescription = ref('')
const editGraphId = ref('')
const editStatus = ref<'active' | 'disabled'>('active')
const editConfig = ref('{}')
const editContext = ref('{}')
const editMetadata = ref('{}')
const configFields = ref<Record<string, string>>({})

function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2)
}

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

function fillForm(payload: ManagementAssistant) {
  item.value = payload
  editName.value = payload.name
  editDescription.value = payload.description || ''
  editGraphId.value = payload.graph_id
  editStatus.value = payload.status === 'disabled' ? 'disabled' : 'active'
  editConfig.value = stringifyJson(payload.config)
  editContext.value = stringifyJson(payload.context)
  editMetadata.value = stringifyJson(payload.metadata)
}

const stats = computed(() => {
  const assistant = item.value

  return [
    {
      label: '当前项目',
      value: currentProject.value?.name || '未选择',
      hint: assistant?.project_id || '--',
      icon: 'project',
      tone: 'primary'
    },
    {
      label: 'Graph',
      value: assistant?.graph_id || '--',
      hint: assistant?.langgraph_assistant_id ? shortId(assistant.langgraph_assistant_id) : '未同步',
      icon: 'graph',
      tone: 'success'
    },
    {
      label: '同步状态',
      value: assistant?.sync_status || '--',
      hint: assistant?.last_synced_at ? formatDateTime(assistant.last_synced_at) : '未同步',
      icon: 'activity',
      tone: assistant?.sync_status === 'ready' ? 'success' : 'warning'
    },
    {
      label: '运行状态',
      value: assistant?.status || '--',
      hint: assistant?.runtime_base_url || '未绑定 runtime',
      icon: 'assistant',
      tone: assistant?.status === 'active' ? 'danger' : 'neutral'
    }
  ]
})

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

function syncConfigFields() {
  try {
    const baseConfig = parseObjectJson(editConfig.value, 'config')
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
  configFields.value = {
    ...configFields.value,
    [key]: value
  }

  try {
    const currentConfig = parseObjectJson(editConfig.value, 'config')

    if (!value.trim()) {
      delete currentConfig[key]
      editConfig.value = stringifyJson(currentConfig)
      return
    }

    if (valueType === 'number') {
      const parsed = Number(value)
      if (!Number.isFinite(parsed)) {
        return
      }
      currentConfig[key] = parsed
      editConfig.value = stringifyJson(currentConfig)
      return
    }

    if (valueType === 'boolean') {
      currentConfig[key] = value === 'true'
      editConfig.value = stringifyJson(currentConfig)
      return
    }

    currentConfig[key] = value
    editConfig.value = stringifyJson(currentConfig)
  } catch {
    // ignore invalid draft JSON while typing
  }
}

async function loadAssistantDetail() {
  const projectId = activeProjectId.value
  if (!projectId || !assistantId.value) {
    item.value = null
    error.value = ''
    notice.value = ''
    return
  }

  loading.value = true
  error.value = ''
  notice.value = ''

  try {
    const payload = await getAssistant(assistantId.value, projectId)
    fillForm(payload)
  } catch (loadError) {
    item.value = null
    error.value = loadError instanceof Error ? loadError.message : '助手详情加载失败'
  } finally {
    loading.value = false
  }
}

async function loadSchema() {
  const projectId = activeProjectId.value
  const graphId = editGraphId.value.trim()

  if (!projectId || !graphId) {
    schema.value = null
    return
  }

  schemaLoading.value = true

  try {
    schema.value = (await getAssistantParameterSchema(graphId, projectId)) as ParameterSchemaResponse
  } catch {
    schema.value = null
  } finally {
    schemaLoading.value = false
  }
}

async function handleSave() {
  const projectId = activeProjectId.value
  if (!projectId || !assistantId.value) {
    return
  }
  if (!canManageAssistant.value) {
    error.value = '当前账号没有助手治理写权限'
    return
  }

  saving.value = true
  error.value = ''
  notice.value = ''

  try {
    const normalizedPayload = normalizeAssistantRuntimePayload({
      name: editName.value,
      description: editDescription.value,
      graph_id: editGraphId.value,
      status: editStatus.value,
      config: parseObjectJson(editConfig.value, 'config'),
      context: parseObjectJson(editContext.value, 'context'),
      metadata: parseObjectJson(editMetadata.value, 'metadata')
    })
    const updated = await updateAssistant(
      assistantId.value,
      normalizedPayload,
      projectId
    )

    fillForm(updated)
    notice.value = '助手配置已保存'
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : '助手保存失败'
  } finally {
    saving.value = false
  }
}

async function handleResync() {
  const projectId = activeProjectId.value
  if (!projectId || !assistantId.value) {
    return
  }
  if (!canManageAssistant.value) {
    error.value = '当前账号没有助手治理写权限'
    return
  }

  resyncing.value = true
  error.value = ''
  notice.value = ''

  try {
    const operation = await resyncAssistantByOperation(assistantId.value, projectId, {
      idempotencyKey: `assistant-resync:${assistantId.value}`
    })
    if (operation.status !== 'succeeded') {
      throw new Error(getOperationFailureMessage(operation))
    }
    await loadAssistantDetail()
    notice.value = '助手已完成上游重同步'
  } catch (resyncError) {
    error.value = resyncError instanceof Error ? resyncError.message : '助手重同步失败'
  } finally {
    resyncing.value = false
  }
}

function openDeleteDialog() {
  if (!item.value || !canManageAssistant.value) {
    return
  }

  showDeleteDialog.value = true
}

function cancelDelete() {
  showDeleteDialog.value = false
}

async function confirmDelete() {
  const projectId = activeProjectId.value
  const currentItem = item.value
  if (!projectId || !currentItem) {
    cancelDelete()
    return
  }

  deleting.value = true
  error.value = ''
  notice.value = ''

  try {
    await deleteAssistant(
      currentItem.id,
      {
        deleteRuntime: true,
        deleteThreads: false
      },
      projectId
    )

    uiStore.pushToast({
      type: 'success',
      title: '助手已删除',
      message: currentItem.name || currentItem.id
    })
    cancelDelete()
    await router.push('/workspace/assistants')
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : '助手删除失败'
  } finally {
    deleting.value = false
  }
}

async function handleCopyValue(label: string, value: string) {
  const copied = await copyText(value)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? `已复制${label}` : '复制失败',
    message: copied ? value : '当前环境不支持自动复制，请手动复制。'
  })
}

function openAssistantChat() {
  if (!item.value) {
    return
  }

  const targetAssistantId = item.value.langgraph_assistant_id?.trim() || item.value.id
  const projectId = activeProjectId.value
  if (projectId) {
    writeRecentChatTarget(projectId, {
      targetType: 'assistant',
      assistantId: targetAssistantId,
      assistantName: item.value.name || targetAssistantId
    })
  }

  void router.push({
    path: '/workspace/chat',
    query: {
      targetType: 'assistant',
      assistantId: targetAssistantId,
      assistantName: item.value.name || targetAssistantId,
      startNew: '1'
    }
  })
}

watch([() => assistantId.value, () => activeProjectId.value], () => {
  void loadAssistantDetail()
}, { immediate: true })

watch(
  () => editGraphId.value,
  () => {
    void loadSchema()
  },
  { immediate: true }
)

watch([configPropertyDefs, editConfig], () => {
  syncConfigFields()
}, { immediate: true })
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Agents"
      :title="item?.name || 'Agent 详情'"
      description="查看 Agent 档案、参数 schema 和运行配置。旧 Assistant 路由仅作为兼容入口。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/assistants')"
        >
          返回列表
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="!item"
          @click="openAssistantChat"
        >
          <BaseIcon
            name="chat"
            size="sm"
          />
          打开聊天
        </BaseButton>
        <BaseButton
          variant="danger"
          :disabled="!item || deleting || !canManageAssistant"
          @click="openDeleteDialog"
        >
          <BaseIcon
            name="alert"
            size="sm"
          />
          {{ canManageAssistant ? (deleting ? '删除中...' : '删除助手') : '当前账号只读' }}
        </BaseButton>
      </template>
    </PageHeader>

    <EmptyState
      v-if="!currentProject"
      icon="project"
      title="请先选择项目"
      description="助手详情页同样需要项目上下文。没有项目，权限校验和详情数据都不成立。"
    />

    <template v-else>
      <StateBanner
        v-if="error"
        title="助手详情加载失败"
        :description="error"
        variant="danger"
      />

      <StateBanner
        v-if="notice"
        title="操作已完成"
        :description="notice"
        variant="success"
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

      <EmptyState
        v-if="!loading && !item"
        icon="assistant"
        title="未找到这个助手"
        description="当前项目下没有这条助手记录，或者你没有访问它的权限。"
      />

      <div
        v-else
        class="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]"
      >
        <SurfaceCard class="space-y-5">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                基础配置
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                这里直接承接旧版 assistant detail 的编辑能力。
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <BaseButton
                variant="secondary"
                :disabled="resyncing || !item || !canManageAssistant"
                @click="handleResync"
              >
                {{ canManageAssistant ? (resyncing ? '同步中...' : '上游重同步') : '当前账号只读' }}
              </BaseButton>
              <BaseButton
                :disabled="saving || !item || !canManageAssistant"
                @click="handleSave"
              >
                {{ canManageAssistant ? (saving ? '保存中...' : '保存') : '当前账号只读' }}
              </BaseButton>
            </div>
          </div>

          <div
            v-if="item?.last_sync_error"
            class="rounded-2xl border border-amber-100 bg-amber-50/80 px-4 py-4 text-sm leading-7 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-100"
          >
            {{ item.last_sync_error }}
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <label class="block">
              <span class="pw-input-label">名称</span>
              <input
                v-model="editName"
                class="pw-input"
                :disabled="saving"
              >
            </label>

            <label class="block">
              <span class="pw-input-label">状态</span>
              <BaseSelect
                v-model="editStatus"
                :disabled="saving"
              >
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </BaseSelect>
            </label>
          </div>

          <label class="block">
            <span class="pw-input-label">描述</span>
            <textarea
              v-model="editDescription"
              rows="4"
              class="pw-input min-h-[120px] resize-y"
              :disabled="saving"
            />
          </label>

          <label class="block">
            <span class="pw-input-label">Graph ID</span>
            <input
              v-model="editGraphId"
              class="pw-input"
              :disabled="saving"
            >
          </label>

          <div
            v-if="configPropertyDefs.length > 0"
            class="space-y-4 rounded-[24px] border border-gray-100 bg-gray-50/70 px-4 py-4 dark:border-dark-700 dark:bg-dark-900/50"
          >
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              Schema 驱动字段
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
                  :disabled="saving"
                  @input="applyConfigFieldValue(field.key, ($event.target as HTMLInputElement).value, field.type)"
                >
              </label>
            </div>
          </div>

          <label class="block">
            <span class="pw-input-label">Config (JSON object)</span>
            <textarea
              v-model="editConfig"
              rows="10"
              class="pw-input min-h-[220px] resize-y font-mono text-xs leading-6"
              :disabled="saving"
            />
          </label>

          <label class="block">
            <span class="pw-input-label">Context (JSON object)</span>
            <textarea
              v-model="editContext"
              rows="10"
              class="pw-input min-h-[220px] resize-y font-mono text-xs leading-6"
              :disabled="saving"
            />
          </label>

          <label class="block">
            <span class="pw-input-label">Metadata (JSON object)</span>
            <textarea
              v-model="editMetadata"
              rows="10"
              class="pw-input min-h-[220px] resize-y font-mono text-xs leading-6"
              :disabled="saving"
            />
          </label>
        </SurfaceCard>

        <div class="space-y-6">
          <SurfaceCard class="space-y-4">
            <div class="text-lg font-semibold text-gray-900 dark:text-white">
              标识信息
            </div>

            <div class="space-y-3 text-sm leading-7 text-gray-600 dark:text-dark-300">
              <div class="flex items-start justify-between gap-3">
                <span>Assistant ID</span>
                <button
                  type="button"
                  class="break-all text-right font-semibold text-gray-900 transition hover:text-primary-600 dark:text-white"
                  @click="item && handleCopyValue('Assistant ID', item.id)"
                >
                  {{ item?.id || '--' }}
                </button>
              </div>
              <div class="flex items-start justify-between gap-3">
                <span>LangGraph ID</span>
                <button
                  type="button"
                  class="break-all text-right font-semibold text-gray-900 transition hover:text-primary-600 dark:text-white"
                  @click="item?.langgraph_assistant_id && handleCopyValue('LangGraph Assistant ID', item.langgraph_assistant_id)"
                >
                  {{ item?.langgraph_assistant_id || '--' }}
                </button>
              </div>
              <div class="flex items-start justify-between gap-3">
                <span>Runtime Base URL</span>
                <span class="break-all text-right font-semibold text-gray-900 dark:text-white">
                  {{ item?.runtime_base_url || '--' }}
                </span>
              </div>
              <div class="flex items-start justify-between gap-3">
                <span>创建时间</span>
                <span class="text-right font-semibold text-gray-900 dark:text-white">
                  {{ item?.created_at ? formatDateTime(item.created_at) : '--' }}
                </span>
              </div>
              <div class="flex items-start justify-between gap-3">
                <span>更新时间</span>
                <span class="text-right font-semibold text-gray-900 dark:text-white">
                  {{ item?.updated_at ? formatDateTime(item.updated_at) : '--' }}
                </span>
              </div>
            </div>
          </SurfaceCard>

          <SurfaceCard class="space-y-4">
            <div class="flex items-center justify-between gap-3">
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                参数 Schema
              </div>
              <div class="text-xs text-gray-400 dark:text-dark-400">
                {{ schemaLoading ? '加载中...' : schema?.schema_version || '未返回 schema' }}
              </div>
            </div>

            <div class="space-y-3 text-sm leading-7 text-gray-600 dark:text-dark-300">
              <div class="flex items-start justify-between gap-3">
                <span>Graph</span>
                <span class="text-right font-semibold text-gray-900 dark:text-white">
                  {{ schema?.graph_id || editGraphId || '--' }}
                </span>
              </div>
              <div class="flex items-start justify-between gap-3">
                <span>字段数</span>
                <span class="text-right font-semibold text-gray-900 dark:text-white">
                  {{ configPropertyDefs.length }}
                </span>
              </div>
            </div>

            <div
              v-if="configPropertyDefs.length === 0"
              class="rounded-2xl border border-dashed border-gray-200 px-4 py-5 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
            >
              当前 graph 没有返回 schema-driven config 字段，页面仍然保留 JSON 编辑兜底。
            </div>

            <div
              v-else
              class="space-y-2"
            >
              <div
                v-for="field in configPropertyDefs"
                :key="field.key"
                class="rounded-2xl border border-white/70 bg-white/80 px-4 py-3 text-sm dark:border-dark-700 dark:bg-dark-900/70"
              >
                <div class="font-semibold text-gray-900 dark:text-white">
                  {{ field.key }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                  type={{ field.type }} · required={{ field.required ? 'true' : 'false' }}
                </div>
              </div>
            </div>
          </SurfaceCard>
        </div>
      </div>
    </template>
  </section>

  <ConfirmDialog
    :show="showDeleteDialog"
    title="删除助手"
    :message="
      item
        ? `确认删除助手“${item.name}”吗？会同时删除 runtime 中的 assistant 记录，但保留 threads 历史。`
        : ''
    "
    confirm-text="删除"
    danger
    @cancel="cancelDelete"
    @confirm="confirmDelete"
  />
</template>
