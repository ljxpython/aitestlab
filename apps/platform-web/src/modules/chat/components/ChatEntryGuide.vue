<script setup lang="ts">
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'

defineProps<{
  projectName?: string
}>()
</script>

<template>
  <div class="grid gap-4 xl:grid-cols-[minmax(0,1.18fr)_320px]">
    <SurfaceCard class="space-y-4">
      <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
        <BaseIcon
          name="chat"
          size="sm"
          class="text-primary-500"
        />
        首次进入引导
      </div>

      <div class="pw-panel-muted text-sm leading-7 text-gray-500 dark:text-dark-300">
        <p>
          当前项目
          <span class="font-semibold text-gray-900 dark:text-white">{{ projectName || '未选择' }}</span>
          还没有保存最近聊天目标。先去助手目录或图谱目录里选一个真实的目标，后面再回到 Chat 就会直接进入对话工作台。
        </p>
      </div>

      <div class="grid gap-4 md:grid-cols-2">
        <div class="pw-panel-muted">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="assistant"
              size="sm"
              class="text-primary-500"
            />
            从 Agents 进入
          </div>
          <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-300">
            适合已经确认具体 Agent 的场景。这里会把 `agent_key` 作为聊天目标保存下来。
          </p>
          <div class="mt-4">
            <router-link
              class="pw-btn pw-btn-secondary"
              to="/workspace/assistants"
            >
              去选 Agent
            </router-link>
          </div>
        </div>

        <div class="pw-panel-muted">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="graph"
              size="sm"
              class="text-primary-500"
            />
            从 Graphs 进入
          </div>
          <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-300">
            适合固定图谱对话，比如 `sql_agent` 或其他业务 graph。后面 Threads 和 Chat 都会复用这份目标绑定。
          </p>
          <div class="mt-4">
            <router-link
              class="pw-btn pw-btn-secondary"
              to="/workspace/graphs"
            >
              去选 Graph
            </router-link>
          </div>
        </div>
      </div>
    </SurfaceCard>

    <SurfaceCard class="space-y-4">
      <div class="pw-page-eyebrow">
        Shortcuts
      </div>
      <div class="space-y-3 text-sm leading-7 text-gray-500 dark:text-dark-300">
        <p>如果你是固定 SQL 问答流程，直接打开 SQL Agent 就行，它会把目标锁定在 `sql_agent`。</p>
        <p>后续 Testcase Generate 接入同一套聊天基座后，也会复用这份目标绑定，不会再单独维护第二套半成品实现。</p>
      </div>
    </SurfaceCard>
  </div>
</template>
