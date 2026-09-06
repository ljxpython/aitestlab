<script setup lang="ts">
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import type { ChatRunOptions } from '../types'
import type { RuntimeModelItem } from '@/types/management'

const props = defineProps<{
  show: boolean
  draftRunOptions: ChatRunOptions
  runtimeModels: RuntimeModelItem[]
}>()

const emit = defineEmits<{
  close: []
  'update:model-id': [value: string]
  'update:temperature': [value: string]
  'update:max-tokens': [value: string]
  restore: []
  apply: []
}>()

function getInputValue(event: Event) {
  return (event.target as HTMLInputElement | HTMLSelectElement | null)?.value || ''
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
