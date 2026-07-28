<script setup lang="ts">
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import type { ChatRunOptions } from '../types'
import type { RuntimeModelItem, RuntimeToolItem } from '@/types/management'

const props = defineProps<{
  show: boolean
  selectedToolsLabel: string
  draftRunOptions: ChatRunOptions
  runtimeModels: RuntimeModelItem[]
  runtimeTools: RuntimeToolItem[]
  loadingRuntime: boolean
}>()

const emit = defineEmits<{
  close: []
  'update:model-id': [value: string]
  'update:system-prompt': [value: string]
  'update:enable-tools': [value: boolean]
  'toggle-tool': [toolKey: string]
  'update:temperature': [value: string]
  'update:max-tokens': [value: string]
  restore: []
  apply: []
}>()

function getInputValue(event: Event) {
  return (event.target as HTMLInputElement | HTMLSelectElement | null)?.value || ''
}

function getCheckedValue(event: Event) {
  return Boolean((event.target as HTMLInputElement | null)?.checked)
}
</script>

<template>
  <BaseDialog
    :show="show"
    title="运行参数"
    width="wide"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <div class="pw-card-highlight px-4 py-4 text-sm leading-7 text-primary-900 dark:text-primary-100">
        这里的设置只影响后续发送、继续执行或新建出来的下一次运行，不会回改已经开始的这轮会话。
      </div>

      <div class="grid gap-4 md:grid-cols-2">
        <div class="pw-panel-muted p-4">
          <div class="text-xs text-gray-400 dark:text-dark-400">
            当前模型
          </div>
          <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
            {{ props.draftRunOptions.modelId || '默认模型' }}
          </div>
        </div>
        <div class="pw-panel-muted p-4">
          <div class="text-xs text-gray-400 dark:text-dark-400">
            工具策略
          </div>
          <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
            {{ selectedToolsLabel }}
          </div>
        </div>
      </div>

      <label class="block">
        <span class="pw-input-label">模型</span>
        <BaseSelect
          :model-value="props.draftRunOptions.modelId"
          @update:model-value="emit('update:model-id', $event)"
        >
          <option value="">
            使用默认模型
          </option>
          <option
            v-for="model in props.runtimeModels"
            :key="model.id"
            :value="model.model_id"
          >
            {{ model.display_name || model.model_id }}
          </option>
        </BaseSelect>
      </label>

      <label class="block">
        <span class="pw-input-label">System Prompt</span>
        <textarea
          :value="props.draftRunOptions.systemPrompt"
          rows="5"
          class="pw-input min-h-[132px] resize-y text-sm leading-7"
          @input="emit('update:system-prompt', getInputValue($event))"
        />
      </label>

      <div class="pw-panel p-4">
        <label class="flex items-center justify-between gap-3">
          <div>
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              工具开关
            </div>
            <div class="mt-1 text-xs leading-6 text-gray-500 dark:text-dark-300">
              {{ selectedToolsLabel }}
            </div>
          </div>
          <input
            :checked="props.draftRunOptions.enableTools"
            type="checkbox"
            class="pw-table-checkbox"
            @change="emit('update:enable-tools', getCheckedValue($event))"
          >
        </label>

        <div
          v-if="props.draftRunOptions.enableTools"
          class="mt-4 max-h-72 space-y-2 overflow-y-auto"
        >
          <label
            v-for="tool in props.runtimeTools"
            :key="tool.id"
            class="pw-panel-muted flex items-start gap-3 px-3 py-3 text-sm"
          >
            <input
              :checked="props.draftRunOptions.toolNames.includes(tool.tool_key)"
              type="checkbox"
              class="pw-table-checkbox mt-1"
              @change="emit('toggle-tool', tool.tool_key)"
            >
            <div class="min-w-0">
              <div class="font-semibold text-gray-900 dark:text-white">
                {{ tool.name || tool.tool_key }}
              </div>
              <div class="mt-1 text-xs leading-6 text-gray-500 dark:text-dark-300">
                {{ tool.description || tool.source || '暂无描述' }}
              </div>
            </div>
          </label>

          <div
            v-if="props.loadingRuntime"
            class="text-xs leading-6 text-gray-400 dark:text-dark-400"
          >
            正在加载运行时目录...
          </div>

          <div
            v-else-if="props.runtimeTools.length === 0"
            class="text-xs leading-6 text-gray-400 dark:text-dark-400"
          >
            当前没有可选工具目录。
          </div>
        </div>
      </div>

      <div class="grid gap-4 md:grid-cols-2">
        <label class="block">
          <span class="pw-input-label">Temperature</span>
          <input
            :value="props.draftRunOptions.temperature"
            class="pw-input"
            placeholder="例如 0.2"
            @input="emit('update:temperature', getInputValue($event))"
          >
        </label>
        <label class="block">
          <span class="pw-input-label">Max Tokens</span>
          <input
            :value="props.draftRunOptions.maxTokens"
            class="pw-input"
            placeholder="例如 4096"
            @input="emit('update:max-tokens', getInputValue($event))"
          >
        </label>
      </div>
    </div>

    <template #footer>
      <div class="flex flex-wrap justify-end gap-3">
        <BaseButton
          variant="ghost"
          @click="emit('restore')"
        >
          还原
        </BaseButton>
        <BaseButton
          variant="secondary"
          @click="emit('close')"
        >
          取消
        </BaseButton>
        <BaseButton @click="emit('apply')">
          确认
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>
