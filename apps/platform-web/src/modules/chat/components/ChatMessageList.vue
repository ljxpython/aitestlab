<script setup lang="ts">
import type { Message } from '@langchain/langgraph-sdk'
import type { AssembledToolCall, AnyStream, MessageMetadata } from '@langchain/vue'
import { computed } from 'vue'
import MarkdownContent from '@/components/platform/MarkdownContent.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { getMessageAttachments, getMessageText } from '@/utils/threads'
import type { ChatMessageMetadata } from '../branching'
import type { ChatDisplayMessage } from '../message-view-model'
import { buildChatMessageMetaView } from '../message-meta-view-model'
import ChatAttachmentPreview from './ChatAttachmentPreview.vue'
import ChatMessageMeta from './ChatMessageMeta.vue'
import ChatMessageRuntimeMetadata from './ChatMessageRuntimeMetadata.vue'

const props = defineProps<{
  displayMessages: ChatDisplayMessage[]
  allMessages: Message[]
  editingMessageId: string
  editingMessageValue: string
  isRunning: boolean
  streamHandle: AnyStream
  toolCalls: AssembledToolCall[]
  getMessageMeta: (messageId: string) => ChatMessageMetadata | undefined
  getMessageBranchIndex: (messageId: string) => number
  hasBranchSwitcher: (messageId: string) => boolean
  canEditMessage: (message: Message, messageId: string, parentCheckpointId?: string) => boolean
  canRetryMessage: (message: Message, messageId: string, parentCheckpointId?: string) => boolean
}>()

const emit = defineEmits<{
  'update:editingMessageValue': [value: string]
  'copy-message': [message: Message]
  'cancel-edit': []
  'submit-edit': [message: Message, messageId: string, parentCheckpointId?: string]
  'start-edit': [message: Message, messageId: string]
  'retry-message': [messageId: string, parentCheckpointId?: string]
  'select-previous-branch': [messageId: string]
  'select-next-branch': [messageId: string]
  'message-meta-expanded-change': [messageId: string, expanded: boolean]
}>()

function handleEditingInput(event: Event) {
  emit('update:editingMessageValue', (event.target as HTMLTextAreaElement | null)?.value || '')
}

function hasMetaSummary(message: Message) {
  const metaView = buildChatMessageMetaView(message, props.allMessages, props.toolCalls)
  return metaView.toolCalls.length > 0 || metaView.subAgentCards.length > 0
}

function getParentCheckpointId(messageId: string, runtimeMetadata?: MessageMetadata) {
  return (
    runtimeMetadata?.parentCheckpointId?.trim() ||
    props.getMessageMeta(messageId)?.parentCheckpoint?.checkpoint_id?.trim() ||
    undefined
  )
}

const emptyPlaceholderSuppressedIds = computed(() => {
  return new Set(
    props.displayMessages
      .filter((entry) => entry.message.type === 'ai' && hasMetaSummary(entry.message))
      .map((entry) => entry.id)
  )
})
</script>

<template>
  <div class="space-y-5">
    <ChatMessageRuntimeMetadata
      v-for="displayEntry in displayMessages"
      :key="displayEntry.id"
      :stream="streamHandle"
      :message-id="displayEntry.id"
      v-slot="{ metadata }"
    >
      <div
        class="flex flex-col gap-2"
        :class="displayEntry.wrapClass"
      >
      <div class="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
        {{ displayEntry.roleLabel }}
      </div>
      <div
        class="pw-chat-bubble max-w-[860px]"
        :class="[
          displayEntry.bubbleClass,
          displayEntry.message.type === 'human' ? 'w-auto self-end' : 'w-full self-start'
        ]"
      >
        <div
          v-if="getMessageAttachments(displayEntry.message.content).length > 0"
          class="flex flex-wrap gap-3"
          :class="displayEntry.message.type === 'human' ? 'justify-end' : ''"
        >
          <ChatAttachmentPreview
            v-for="(attachment, attachmentIndex) in getMessageAttachments(displayEntry.message.content)"
            :key="`${displayEntry.id}-attachment-${attachmentIndex}`"
            :block="attachment"
            compact
          />
        </div>
        <textarea
          v-if="editingMessageId === displayEntry.id"
          :value="editingMessageValue"
          rows="5"
          class="pw-input resize-y border-0 bg-transparent px-0 py-0 text-sm leading-7 shadow-none focus:ring-0"
          :class="getMessageAttachments(displayEntry.message.content).length > 0 ? 'mt-3' : ''"
          @input="handleEditingInput"
        />
        <pre
          v-else-if="displayEntry.message.type !== 'ai' && getMessageText(displayEntry.message.content)"
          class="whitespace-pre-wrap break-words text-sm leading-7"
          :class="getMessageAttachments(displayEntry.message.content).length > 0 ? 'mt-3' : ''"
        >{{ getMessageText(displayEntry.message.content) }}</pre>
        <MarkdownContent
          v-else-if="getMessageText(displayEntry.message.content)"
          :content="getMessageText(displayEntry.message.content)"
          :class="getMessageAttachments(displayEntry.message.content).length > 0 ? 'mt-3' : ''"
        />
        <div
          v-else-if="
            getMessageAttachments(displayEntry.message.content).length === 0 &&
              !emptyPlaceholderSuppressedIds.has(displayEntry.id)
          "
          class="text-sm leading-7 text-gray-500 dark:text-dark-300"
        >
          当前消息没有可渲染的文本内容。
        </div>
        <div v-if="displayEntry.message.type === 'ai'">
          <ChatMessageMeta
            :message="displayEntry.message"
            :all-messages="allMessages"
            :tool-calls="toolCalls"
            @expanded-change="emit('message-meta-expanded-change', displayEntry.id, $event)"
          />
        </div>
      </div>

      <div
        class="flex max-w-[860px] flex-wrap items-center gap-2 text-xs"
        :class="
          displayEntry.message.type === 'human'
            ? 'w-auto justify-end self-end'
            : 'w-full justify-start self-start'
        "
      >
        <template v-if="editingMessageId === displayEntry.id">
          <button
            type="button"
            class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
            @click="emit('cancel-edit')"
          >
            取消编辑
          </button>
          <button
            type="button"
            class="pw-btn-primary inline-flex h-8 items-center justify-center rounded-lg px-3 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="isRunning"
            @click="emit('submit-edit', displayEntry.message, displayEntry.id, getParentCheckpointId(displayEntry.id, metadata))"
          >
            提交重发
          </button>
        </template>

        <template v-else>
          <button
            type="button"
            class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
            @click="emit('copy-message', displayEntry.message)"
          >
            复制
          </button>
          <button
            v-if="canEditMessage(displayEntry.message, displayEntry.id, getParentCheckpointId(displayEntry.id, metadata))"
            type="button"
            class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
            @click="emit('start-edit', displayEntry.message, displayEntry.id)"
          >
            编辑
          </button>
          <button
            v-if="canRetryMessage(displayEntry.message, displayEntry.id, getParentCheckpointId(displayEntry.id, metadata))"
            type="button"
            class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
            @click="emit('retry-message', displayEntry.id, getParentCheckpointId(displayEntry.id, metadata))"
          >
            重试
          </button>

          <div
            v-if="hasBranchSwitcher(displayEntry.id)"
            class="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-2 py-1 dark:border-dark-700 dark:bg-dark-900"
          >
            <button
              type="button"
              class="rounded-md p-1 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-white"
              :disabled="getMessageBranchIndex(displayEntry.id) <= 0 || isRunning"
              @click="emit('select-previous-branch', displayEntry.id)"
            >
              <BaseIcon
                name="chevron-left"
                size="xs"
              />
            </button>
            <span class="min-w-[64px] text-center font-medium text-gray-500 dark:text-dark-300">
              {{ getMessageBranchIndex(displayEntry.id) + 1 }} /
              {{ getMessageMeta(displayEntry.id)?.branchOptions?.length }}
            </span>
            <button
              type="button"
              class="rounded-md p-1 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-white"
              :disabled="
                getMessageBranchIndex(displayEntry.id) >=
                  ((getMessageMeta(displayEntry.id)?.branchOptions?.length ?? 1) - 1) || isRunning
              "
              @click="emit('select-next-branch', displayEntry.id)"
            >
              <BaseIcon
                name="chevron-right"
                size="xs"
              />
            </button>
          </div>
        </template>
      </div>

      <div
        v-if="displayEntry.timeText"
        class="max-w-[860px] text-[11px] leading-5 text-gray-400 dark:text-dark-400"
        :class="
          displayEntry.message.type === 'human'
            ? 'w-auto self-end text-right'
            : 'w-full self-start text-left'
        "
      >
        {{ displayEntry.timeText }}
      </div>
      </div>
    </ChatMessageRuntimeMetadata>

    <div
      v-if="isRunning"
      class="flex items-start"
    >
      <div class="pw-panel px-4 py-3">
        <div class="flex items-center gap-2 text-sm text-gray-500 dark:text-dark-300">
          <span class="h-2 w-2 animate-pulse rounded-full bg-primary-400" />
          <span class="h-2 w-2 animate-pulse rounded-full bg-primary-300 [animation-delay:120ms]" />
          <span class="h-2 w-2 animate-pulse rounded-full bg-primary-200 [animation-delay:240ms]" />
          <span>正在生成回复...</span>
        </div>
      </div>
    </div>
  </div>
</template>
