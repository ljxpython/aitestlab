<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { CHAT_ATTACHMENT_ACCEPT, type ChatAttachmentBlock } from '@/utils/chat-content'
import ChatAttachmentPreview from './ChatAttachmentPreview.vue'
import ChatInterruptPanel from './ChatInterruptPanel.vue'

const props = defineProps<{
  modelValue: string
  attachments: ChatAttachmentBlock[]
  isRunning: boolean
  hasBlockingInterrupt: boolean
  interruptPayload: unknown
  canStartThread: boolean
  showContinueAction: boolean
  canSendFreshMessage: boolean
  cancelling: boolean
  sendButtonLabel: string
  lastEventAt: string
  onResumeInterruptedRun: (resumePayload: unknown, interruptId?: string) => Promise<boolean>
  onResumeAllInterruptedRuns: (responsesById: Record<string, unknown>) => Promise<boolean>
  compact?: boolean
  focusMode?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'send': []
  'cancel': []
  'continue-run': []
  'new-thread': []
  'file-input-change': [event: Event]
  'composer-paste': [event: ClipboardEvent]
  'remove-attachment': [index: number]
}>()

const fileInputRef = ref<HTMLInputElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const composerModel = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value)
})

const isDenseMode = computed(() => Boolean(props.compact))
const isFocusMode = computed(() => Boolean(props.focusMode))
const showSecondaryAction = computed(() => !isFocusMode.value)
const composerCollapsedHeight = computed(() => {
  if (isDenseMode.value) {
    return 28
  }

  return 32
})
const composerMinHeight = computed(() => composerCollapsedHeight.value)
const composerMaxHeight = computed(() => {
  if (isFocusMode.value) {
    return 132
  }

  if (isDenseMode.value) {
    return 112
  }

  return 120
})

const helperText = computed(() =>
  props.hasBlockingInterrupt
    ? '当前运行正在等待人工决策。你可以先编辑下一条消息草稿，处理完中断后再发送。'
    : props.isRunning
      ? 'Agent 正在实时输出。你可以继续编辑下一条消息草稿，或随时点击“停止生成”。'
      : ''
)

function handleComposerPaste(event: ClipboardEvent) {
  emit('composer-paste', event)
}

function openFilePicker() {
  fileInputRef.value?.click()
}

function applyTextareaHeight(nextHeight: number) {
  const textarea = textareaRef.value
  if (!textarea) {
    return
  }

  textarea.style.height = `${nextHeight}px`
}

function clampComposerHeight(nextHeight: number) {
  return Math.max(composerMinHeight.value, Math.min(nextHeight, composerMaxHeight.value))
}

async function syncTextareaHeight() {
  await nextTick()

  const textarea = textareaRef.value
  if (!textarea) {
    return
  }

  textarea.style.height = '0px'
  const nextHeight =
    composerModel.value.trim().length === 0
      ? composerCollapsedHeight.value
      : clampComposerHeight(Math.max(composerCollapsedHeight.value, textarea.scrollHeight))
  applyTextareaHeight(nextHeight)
}

watch(
  () => props.modelValue,
  async () => {
    await syncTextareaHeight()
  },
  { immediate: true }
)

watch(
  () => props.attachments.length,
  async () => {
    await syncTextareaHeight()
  }
)

watch(
  () => props.compact,
  async () => {
    await syncTextareaHeight()
  },
  { immediate: true }
)

watch(
  () => props.focusMode,
  async () => {
    await syncTextareaHeight()
  }
)

onMounted(async () => {
  await syncTextareaHeight()
})
</script>

<template>
  <div
    class="px-4 pb-3 pt-2 transition-all duration-200 md:px-5"
    :class="isFocusMode ? 'px-3 pb-2 pt-2 md:px-4' : props.compact ? 'px-4 pb-2 pt-2 md:px-5' : 'pb-3 pt-2'"
  >
    <div
      class="pw-panel mx-auto w-full border-gray-200/80 bg-white/96 shadow-md shadow-gray-200/70 transition-all duration-200 dark:border-dark-700/80 dark:bg-dark-900/94 dark:shadow-none"
      :class="isFocusMode ? 'max-w-[860px] rounded-2xl p-2.5' : 'max-w-[860px] rounded-2xl p-2.5'"
    >
      <ChatInterruptPanel
        v-if="hasBlockingInterrupt"
        :interrupt="interruptPayload"
        :submitting="isRunning"
        :on-resume="onResumeInterruptedRun"
        :on-resume-all="onResumeAllInterruptedRuns"
      />

      <div
        v-if="attachments.length > 0"
        class="mb-4 flex flex-wrap gap-3"
      >
        <ChatAttachmentPreview
          v-for="(attachment, index) in attachments"
          :key="`composer-attachment-${index}`"
          :block="attachment"
          removable
          @remove="emit('remove-attachment', index)"
        />
      </div>

      <textarea
        ref="textareaRef"
        v-model="composerModel"
        :rows="1"
        class="pw-input resize-none border-0 bg-transparent px-0 py-0 shadow-none focus:ring-0"
        :class="[
          isDenseMode
            ? 'min-h-[28px] max-h-[112px] overflow-y-auto text-sm leading-6'
            : 'min-h-[32px] max-h-[120px] overflow-y-auto text-sm leading-6',
          isFocusMode ? 'text-sm leading-6' : ''
        ]"
        placeholder="输入消息。只有点击发送按钮时才会真正提交。"
        @paste="handleComposerPaste"
      />

      <div class="mt-2 space-y-1.5 transition-all duration-200">
        <div
          class="flex items-center justify-between gap-3 transition-all duration-200"
          :class="isFocusMode || props.compact ? 'gap-2' : ''"
        >
          <div
            class="flex min-w-0 items-center gap-2 overflow-x-auto pb-1"
            :class="isFocusMode || props.compact ? 'gap-2' : 'gap-2.5'"
          >
            <button
              type="button"
              class="pw-table-tool-button h-8 shrink-0 rounded-lg px-3 text-xs"
              :disabled="isRunning || hasBlockingInterrupt"
              @click="openFilePicker"
            >
              <BaseIcon
                name="paperclip"
                size="sm"
              />
              <span>上传图片 / PDF</span>
            </button>
            <input
              ref="fileInputRef"
              type="file"
              class="hidden"
              multiple
              :accept="CHAT_ATTACHMENT_ACCEPT"
              @change="emit('file-input-change', $event)"
            >
          </div>

          <div
            class="flex shrink-0 items-center gap-2"
            :class="isFocusMode || props.compact ? 'gap-2' : 'gap-2.5'"
          >
            <BaseButton
              v-if="showSecondaryAction"
              variant="secondary"
              class="h-8 px-3 text-xs"
              :disabled="!canStartThread"
              @click="emit('new-thread')"
            >
              空白对话
            </BaseButton>
            <BaseButton
              v-if="showContinueAction"
              variant="secondary"
              class="h-8 px-3 text-xs"
              @click="emit('continue-run')"
            >
              <BaseIcon
                name="chevron-right"
                size="sm"
              />
              Continue
            </BaseButton>
            <BaseButton
              :variant="isRunning ? 'danger' : 'primary'"
              class="h-8 px-3 text-xs"
              :disabled="isRunning ? cancelling : !canSendFreshMessage"
              @click="isRunning ? emit('cancel') : emit('send')"
            >
              <BaseIcon
                :name="isRunning ? 'x' : 'chat'"
                size="sm"
              />
              {{
                isRunning
                  ? cancelling
                    ? '停止中...'
                    : '停止生成'
                  : sendButtonLabel
              }}
            </BaseButton>
          </div>
        </div>

        <p
          v-if="!isFocusMode && helperText"
          class="px-0.5 text-[11px] leading-5 text-gray-400 dark:text-dark-400"
        >
          {{ helperText }}
        </p>
      </div>
    </div>
  </div>
</template>
