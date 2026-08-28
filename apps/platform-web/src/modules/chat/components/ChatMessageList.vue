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
  <div class="space-y-8">
    <ChatMessageRuntimeMetadata
      v-for="displayEntry in displayMessages"
      :key="displayEntry.id"
      v-slot="{ metadata }"
      :stream="streamHandle"
      :message-id="displayEntry.id"
    >
      <article
        class="pw-chat-turn"
        :class="displayEntry.message.type === 'human' ? 'items-end' : 'items-start'"
      >
        <div
          class="pw-chat-turn-heading"
          :class="displayEntry.message.type === 'human' ? 'self-end' : 'self-start'"
        >
          <template v-if="displayEntry.message.type === 'ai'">
            <span class="pw-chat-agent-mark">
              <BaseIcon
                name="chat"
                size="sm"
              />
            </span>
            <span class="font-semibold text-gray-900 dark:text-white">Agent</span>
            <span v-if="displayEntry.timeText">{{ displayEntry.timeText }}</span>
          </template>
          <template v-else>
            <span class="font-medium text-gray-500 dark:text-dark-300">{{ displayEntry.roleLabel }}</span>
          </template>
        </div>

        <div
          class="pw-chat-bubble max-w-[780px]"
          :class="[
            displayEntry.message.type === 'human'
              ? 'pw-chat-user-message w-auto self-end'
              : displayEntry.message.type === 'ai'
                ? 'pw-chat-agent-message w-full self-start'
                : 'pw-chat-system-message w-full self-start'
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
        </div>

        <div
          v-if="displayEntry.message.type === 'ai'"
          class="pw-chat-run-rail w-full max-w-[780px] self-start"
        >
          <ChatMessageMeta
            :message="displayEntry.message"
            :all-messages="allMessages"
            :tool-calls="toolCalls"
            @expanded-change="emit('message-meta-expanded-change', displayEntry.id, $event)"
          />
        </div>

        <div
          class="flex max-w-[780px] flex-wrap items-center gap-2 text-xs"
          :class="displayEntry.message.type === 'human' ? 'w-auto justify-end self-end' : 'w-full justify-start self-start'"
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
          v-if="displayEntry.timeText && displayEntry.message.type !== 'ai'"
          class="max-w-[780px] text-[11px] leading-5 text-gray-400 dark:text-dark-400"
          :class="displayEntry.message.type === 'human' ? 'w-auto self-end text-right' : 'w-full self-start text-left'"
        >
          {{ displayEntry.timeText }}
        </div>
      </article>
    </ChatMessageRuntimeMetadata>

    <div
      v-if="isRunning"
      class="pw-chat-live-step"
    >
      <span class="pw-chat-live-dot animate-pulse" />
      <span>Agent 正在处理当前回合</span>
    </div>
  </div>
</template>
