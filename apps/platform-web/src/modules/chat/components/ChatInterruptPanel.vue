<script setup lang="ts">
import type { Interrupt } from '@langchain/langgraph-sdk'
import { computed, reactive, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useUiStore } from '@/stores/ui'
import {
  type HitlDecision,
  type HitlDecisionType,
  type HitlRequest,
  isHitlInterruptSchema,
  prettifyInterruptLabel,
  stringifyInterruptValue
} from '../interrupt'

const props = defineProps<{
  interrupt: unknown
  submitting: boolean
  onResume: (resumePayload: unknown, interruptId?: string) => Promise<boolean>
  onResumeAll: (responsesById: Record<string, unknown>) => Promise<boolean>
}>()

const uiStore = useUiStore()
const genericExpanded = ref(false)
const activeInterruptIndex = ref(0)
const activeActionIndex = ref(0)
const savedDecisions = ref<Record<string, HitlDecision>>({})
const selectedMode = ref<HitlDecisionType | ''>('')
const rejectReason = ref('')
const editArgs = reactive<Record<string, string>>({})
const initialEditArgs = ref<Record<string, string>>({})

function normalizeInterruptValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeInterruptValue(item))
  }

  if (value && typeof value === 'object' && 'value' in value) {
    return (value as { value?: unknown }).value
  }

  return value
}

function decisionKey(interruptIndex: number, actionIndex: number) {
  return `${interruptIndex}:${actionIndex}`
}

function actionArgsToStrings(args: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(args).map(([key, value]) => [key, stringifyInterruptValue(value)])
  )
}

function replaceEditArgs(nextArgs: Record<string, string>) {
  for (const key of Object.keys(editArgs)) {
    delete editArgs[key]
  }

  Object.assign(editArgs, nextArgs)
}

function decisionsEqual(left: Record<string, string>, right: Record<string, string>) {
  const leftKeys = Object.keys(left)
  const rightKeys = Object.keys(right)

  if (leftKeys.length !== rightKeys.length) {
    return false
  }

  return leftKeys.every((key) => left[key] === right[key])
}

const hitlInterrupts = computed<Interrupt<HitlRequest>[]>(() => {
  if (!isHitlInterruptSchema(props.interrupt)) {
    return []
  }

  return (Array.isArray(props.interrupt) ? props.interrupt : [props.interrupt]).filter(
    (item): item is Interrupt<HitlRequest> => Boolean(item)
  )
})

const isHitl = computed(() => hitlInterrupts.value.length > 0)
const activeInterrupt = computed(() => hitlInterrupts.value[activeInterruptIndex.value] || null)
const actionRequests = computed(() => activeInterrupt.value?.value?.action_requests || [])
const reviewConfigs = computed(() => activeInterrupt.value?.value?.review_configs || [])
const hasMultipleActions = computed(() => actionRequests.value.length > 1)
const currentAction = computed(() => actionRequests.value[activeActionIndex.value] || null)
const currentConfig = computed(() => {
  if (!currentAction.value) {
    return null
  }

  return (
    reviewConfigs.value.find((item) => item.action_name === currentAction.value?.name) ||
    reviewConfigs.value[activeActionIndex.value] ||
    null
  )
})
const allowedDecisions = computed<HitlDecisionType[]>(() => currentConfig.value?.allowed_decisions || [])
const allowApprove = computed(() => allowedDecisions.value.includes('approve'))
const allowEdit = computed(() => allowedDecisions.value.includes('edit'))
const allowReject = computed(() => allowedDecisions.value.includes('reject'))
const currentDecisionKey = computed(() => decisionKey(activeInterruptIndex.value, activeActionIndex.value))
const currentSavedDecision = computed(() => savedDecisions.value[currentDecisionKey.value])
const editArgsChanged = computed(() => !decisionsEqual(editArgs, initialEditArgs.value))
const addressedCount = computed(
  () =>
    actionRequests.value.filter((_, index) => {
      return Boolean(savedDecisions.value[decisionKey(activeInterruptIndex.value, index)])
    }).length
)
const allAllowApprove = computed(() => {
  if (!hasMultipleActions.value) {
    return false
  }

  return actionRequests.value.every((action, index) => {
    const config =
      reviewConfigs.value.find((item) => item.action_name === action.name) || reviewConfigs.value[index]
    return Boolean(config?.allowed_decisions.includes('approve'))
  })
})
const genericPayload = computed(() => normalizeInterruptValue(props.interrupt))
const genericPayloadText = computed(() => stringifyInterruptValue(genericPayload.value))

function syncCurrentDraft() {
  if (!currentAction.value) {
    replaceEditArgs({})
    initialEditArgs.value = {}
    rejectReason.value = ''
    selectedMode.value = ''
    return
  }

  const baseArgs = actionArgsToStrings(currentAction.value.args)
  initialEditArgs.value = baseArgs

  const savedDecision = currentSavedDecision.value
  if (!savedDecision) {
    replaceEditArgs(baseArgs)
    rejectReason.value = ''
    if (allowApprove.value) {
      selectedMode.value = 'approve'
    } else if (allowReject.value) {
      selectedMode.value = 'reject'
    } else if (allowEdit.value) {
      selectedMode.value = 'edit'
    } else {
      selectedMode.value = ''
    }
    return
  }

  if (savedDecision.type === 'approve') {
    replaceEditArgs(baseArgs)
    rejectReason.value = ''
    selectedMode.value = 'approve'
    return
  }

  if (savedDecision.type === 'reject') {
    replaceEditArgs(baseArgs)
    rejectReason.value = savedDecision.message || ''
    selectedMode.value = 'reject'
    return
  }

  replaceEditArgs(actionArgsToStrings(savedDecision.edited_action.args))
  rejectReason.value = ''
  selectedMode.value = 'edit'
}

function buildCurrentDecision(): { decision?: HitlDecision; error?: string } {
  if (!currentAction.value) {
    return {
      error: '当前没有可处理的中断动作。'
    }
  }

  if (selectedMode.value === 'approve') {
    return {
      decision: {
        type: 'approve'
      }
    }
  }

  if (selectedMode.value === 'reject') {
    const message = rejectReason.value.trim()
    if (!message) {
      return {
        error: '拒绝时必须填写原因。'
      }
    }

    return {
      decision: {
        type: 'reject',
        message
      }
    }
  }

  if (selectedMode.value === 'edit') {
    if (allowApprove.value && !editArgsChanged.value) {
      return {
        decision: {
          type: 'approve'
        }
      }
    }

    return {
      decision: {
        type: 'edit',
        edited_action: {
          name: currentAction.value.name,
          args: { ...editArgs }
        }
      }
    }
  }

  return {
    error: '请先选择一个可提交的决策。'
  }
}

function saveCurrentDecision() {
  const { decision, error } = buildCurrentDecision()
  if (!decision) {
    uiStore.pushToast({
      type: 'error',
      title: '当前动作还不能保存',
      message: error || '决策构建失败'
    })
    return false
  }

  savedDecisions.value = {
    ...savedDecisions.value,
    [currentDecisionKey.value]: decision
  }

  uiStore.pushToast({
    type: 'success',
    title: '当前决策已暂存',
    message: currentAction.value?.name || '已保存'
  })
  return true
}

async function submitSingleDecision() {
  const { decision, error } = buildCurrentDecision()
  if (!decision) {
    uiStore.pushToast({
      type: 'error',
      title: '无法提交当前决策',
      message: error || '决策构建失败'
    })
    return
  }

  if (hitlInterrupts.value.length > 1) {
    savedDecisions.value = {
      ...savedDecisions.value,
      [currentDecisionKey.value]: decision
    }
    await submitAllInterrupts()
    return
  }

  const submitted = await props.onResume(
    { decisions: [decision] },
    activeInterrupt.value?.id
  )

  if (!submitted) {
    uiStore.pushToast({
      type: 'error',
      title: '决策提交失败',
      message: '运行恢复没有成功，请看页面上的错误提示。'
    })
  }
}

async function submitAllDecisions() {
  if (!saveCurrentDecision()) {
    return
  }

  const decisions = actionRequests.value.map((_, index) => {
    return savedDecisions.value[decisionKey(activeInterruptIndex.value, index)]
  })

  if (decisions.some((item) => !item)) {
    uiStore.pushToast({
      type: 'warning',
      title: '还有动作没有处理完',
      message: `当前只完成了 ${addressedCount.value}/${actionRequests.value.length} 个动作。`
    })
    return
  }

  if (hitlInterrupts.value.length > 1) {
    await submitAllInterrupts()
    return
  }

  const submitted = await props.onResume(
    { decisions },
    activeInterrupt.value?.id
  )

  if (!submitted) {
    uiStore.pushToast({
      type: 'error',
      title: '批量决策提交失败',
      message: '运行恢复没有成功，请看页面上的错误提示。'
    })
  }
}

async function approveAllDecisions() {
  if (!allAllowApprove.value) {
    return
  }

  const decisions = actionRequests.value.map(() => ({
    type: 'approve' as const
  }))

  if (hitlInterrupts.value.length > 1) {
    const nextDecisions = { ...savedDecisions.value }
    decisions.forEach((decision, index) => {
      nextDecisions[decisionKey(activeInterruptIndex.value, index)] = decision
    })
    savedDecisions.value = nextDecisions
    await submitAllInterrupts()
    return
  }

  const submitted = await props.onResume(
    { decisions },
    activeInterrupt.value?.id
  )

  if (!submitted) {
    uiStore.pushToast({
      type: 'error',
      title: '批量通过失败',
      message: '运行恢复没有成功，请看页面上的错误提示。'
    })
  }
}

async function submitAllInterrupts() {
  const responsesById: Record<string, unknown> = {}

  for (const [interruptIndex, interrupt] of hitlInterrupts.value.entries()) {
    if (!interrupt.id) {
      uiStore.pushToast({
        type: 'error',
        title: '中断缺少协议 ID',
        message: '无法安全批量恢复，请刷新线程后重试。'
      })
      return
    }

    const decisions = (interrupt.value?.action_requests || []).map((_, actionIndex) =>
      savedDecisions.value[decisionKey(interruptIndex, actionIndex)]
    )
    if (decisions.length === 0 || decisions.some((item) => !item)) {
      uiStore.pushToast({
        type: 'warning',
        title: '还有中断没有处理完',
        message: '请依次检查上方每个 Interrupt，再统一提交。'
      })
      return
    }

    responsesById[interrupt.id] = { decisions }
  }

  const submitted = await props.onResumeAll(responsesById)
  if (!submitted) {
    uiStore.pushToast({
      type: 'error',
      title: '批量决策提交失败',
      message: '运行恢复没有成功，请保留当前决策后重试。'
    })
  }
}

watch(
  () => props.interrupt,
  () => {
    activeInterruptIndex.value = 0
    activeActionIndex.value = 0
    savedDecisions.value = {}
    syncCurrentDraft()
  },
  { immediate: true }
)

watch([activeInterruptIndex, activeActionIndex, isHitl], () => {
  syncCurrentDraft()
})
</script>

<template>
  <div class="pw-panel-info mb-4 overflow-hidden p-0">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-sky-200/70 px-4 py-3 dark:border-primary-900/30">
      <div>
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-600 dark:text-primary-200">
          Interrupt
        </div>
        <div class="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
          {{ isHitl ? '等待人工决策' : '中断上下文' }}
        </div>
      </div>

      <div class="text-xs leading-6 text-slate-500 dark:text-dark-300">
        {{
          isHitl
            ? '运行已经暂停，先处理当前动作，再恢复 agent 执行。'
            : '当前运行被中断了，这里展示的是服务端返回的中断负载。'
        }}
      </div>
    </div>

    <div
      v-if="isHitl"
      class="space-y-4 px-4 py-4"
    >
      <div
        v-if="hitlInterrupts.length > 1"
        class="flex flex-wrap gap-2"
      >
        <button
          v-for="(item, index) in hitlInterrupts"
          :key="item.id || `interrupt-${index}`"
          type="button"
          class="pw-chip-toggle"
          :class="
            index === activeInterruptIndex
              ? 'pw-chip-toggle-active'
              : ''
          "
          @click="activeInterruptIndex = index"
        >
          {{ item.value?.action_requests?.[0]?.name || `Interrupt ${index + 1}` }}
        </button>
      </div>

      <div class="pw-panel">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="text-lg font-semibold text-slate-900 dark:text-white">
              {{ currentAction?.name || 'Unknown action' }}
            </div>
            <div
              v-if="currentAction?.description"
              class="mt-2 max-w-3xl text-sm leading-7 text-slate-500 dark:text-dark-300"
            >
              {{ currentAction.description }}
            </div>
          </div>

          <div class="flex flex-wrap gap-2">
            <span
              v-for="item in allowedDecisions"
              :key="item"
              class="pw-pill-soft pw-pill-soft-info uppercase tracking-[0.12em]"
            >
              {{ item }}
            </span>
          </div>
        </div>
      </div>

      <div
        v-if="hasMultipleActions"
        class="pw-panel"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="text-sm font-semibold text-slate-900 dark:text-white">
            批量动作
          </div>
          <div class="text-xs text-slate-500 dark:text-dark-300">
            已处理 {{ addressedCount }}/{{ actionRequests.length }}
          </div>
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          <button
            v-for="(action, index) in actionRequests"
            :key="`${action.name}-${index}`"
            type="button"
            class="pw-chip-toggle"
            :class="
              index === activeActionIndex
                ? 'pw-chip-toggle-active'
                : savedDecisions[decisionKey(activeInterruptIndex, index)]
                  ? 'pw-pill-soft-success'
                  : ''
            "
            @click="activeActionIndex = index"
          >
            {{ action.name }}
          </button>
        </div>
      </div>

      <div class="pw-panel">
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-dark-400">
          Decision
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          <button
            v-if="allowApprove"
            type="button"
            class="pw-chip-toggle"
            :class="
              selectedMode === 'approve'
                ? 'pw-chip-toggle-active'
                : ''
            "
            @click="selectedMode = 'approve'"
          >
            批准
          </button>
          <button
            v-if="allowEdit"
            type="button"
            class="pw-chip-toggle"
            :class="
              selectedMode === 'edit'
                ? 'pw-chip-toggle-active'
                : ''
            "
            @click="selectedMode = 'edit'"
          >
            编辑
          </button>
          <button
            v-if="allowReject"
            type="button"
            class="pw-chip-toggle"
            :class="
              selectedMode === 'reject'
                ? 'pw-chip-toggle-active'
                : ''
            "
            @click="selectedMode = 'reject'"
          >
            拒绝
          </button>
        </div>

        <div
          v-if="selectedMode === 'approve'"
          class="pw-panel-success mt-4 px-4 py-3 text-sm leading-7 text-emerald-800 dark:text-emerald-100"
        >
          当前动作会按“批准”提交，agent 将继续后续执行。
        </div>

        <div
          v-else-if="selectedMode === 'edit'"
          class="mt-4 space-y-3"
        >
          <div
            v-if="allowApprove && !editArgsChanged"
            class="pw-panel-warning px-4 py-3 text-sm leading-7 text-amber-800 dark:text-amber-100"
          >
            当前没有改动参数，提交时会按“批准”处理。
          </div>

          <label
            v-for="(_value, key) in editArgs"
            :key="key"
            class="block"
          >
            <span class="mb-2 block text-sm font-semibold text-slate-900 dark:text-white">
              {{ prettifyInterruptLabel(key) }}
            </span>
            <textarea
              v-model="editArgs[key]"
              rows="4"
              class="pw-input min-h-[120px] resize-y font-mono text-sm leading-6"
              :disabled="submitting"
              @input="selectedMode = 'edit'"
            />
          </label>
        </div>

        <div
          v-else-if="selectedMode === 'reject'"
          class="mt-4"
        >
          <label class="block">
            <span class="mb-2 block text-sm font-semibold text-slate-900 dark:text-white">
              拒绝原因
            </span>
            <textarea
              v-model="rejectReason"
              rows="4"
              class="pw-input min-h-[132px] resize-y text-sm leading-7"
              placeholder="说明为什么拒绝，或者希望 agent 如何修正。"
              :disabled="submitting"
              @input="selectedMode = 'reject'"
            />
          </label>
        </div>

        <div
          v-if="currentAction && Object.keys(currentAction.args || {}).length > 0"
          class="pw-panel-muted mt-4"
        >
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-dark-400">
            原始参数
          </div>
          <div class="mt-3 space-y-3">
            <div
              v-for="(value, key) in currentAction.args"
              :key="key"
              class="grid gap-1"
            >
              <div class="text-sm font-semibold text-slate-900 dark:text-white">
                {{ prettifyInterruptLabel(key) }}
              </div>
              <pre class="pw-panel mt-2 overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-6 text-slate-700 dark:text-dark-100">{{ stringifyInterruptValue(value) }}</pre>
            </div>
          </div>
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <BaseButton
            v-if="hasMultipleActions"
            variant="ghost"
            :disabled="submitting || activeActionIndex === 0"
            @click="activeActionIndex = Math.max(0, activeActionIndex - 1)"
          >
            上一个
          </BaseButton>
          <BaseButton
            v-if="hasMultipleActions"
            variant="ghost"
            :disabled="submitting || activeActionIndex === actionRequests.length - 1"
            @click="activeActionIndex = Math.min(actionRequests.length - 1, activeActionIndex + 1)"
          >
            下一个
          </BaseButton>
          <BaseButton
            v-if="hasMultipleActions"
            variant="secondary"
            :disabled="submitting"
            @click="saveCurrentDecision"
          >
            保存当前决策
          </BaseButton>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <BaseButton
            v-if="hasMultipleActions && allAllowApprove"
            variant="ghost"
            :disabled="submitting"
            @click="approveAllDecisions"
          >
            全部通过
          </BaseButton>
          <BaseButton
            v-if="hasMultipleActions"
            :disabled="submitting"
            @click="submitAllDecisions"
          >
            {{ submitting ? '提交中...' : `提交全部 ${actionRequests.length} 个决策` }}
          </BaseButton>
          <BaseButton
            v-else
            :disabled="submitting"
            @click="submitSingleDecision"
          >
            {{ submitting ? '提交中...' : '提交当前决策' }}
          </BaseButton>
        </div>
      </div>
    </div>

    <div
      v-else
      class="px-4 py-4"
    >
      <pre
        class="pw-panel overflow-auto whitespace-pre-wrap break-words px-4 py-4 text-xs leading-6 text-slate-700 dark:text-dark-100"
        :class="genericExpanded ? 'max-h-[480px]' : 'max-h-56'"
      >{{ genericPayloadText }}</pre>

      <div class="mt-3 flex justify-end">
        <BaseButton
          variant="ghost"
          @click="genericExpanded = !genericExpanded"
        >
          <BaseIcon
            :name="genericExpanded ? 'chevron-down' : 'chevron-right'"
            size="sm"
          />
          {{ genericExpanded ? '收起详情' : '展开详情' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>
