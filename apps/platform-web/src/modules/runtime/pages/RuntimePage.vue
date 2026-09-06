<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import PageHeader from '@/components/layout/PageHeader.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { listRuntimeModels, listRuntimeTools } from '@/services/runtime/runtime.service'

type RuntimeEntryCard = {
  title: string
  icon: 'runtime' | 'shield' | 'activity'
  description: string
  primaryLabel: string
  primaryTo: string
  secondaryLabel: string
  secondaryTo: string
}

const { activeProjectId } = useWorkspaceProjectContext()

const loading = ref(false)
const error = ref('')
const modelCount = ref(0)
const toolCount = ref(0)
const modelSyncTime = ref<string | null>(null)
const toolSyncTime = ref<string | null>(null)

const stats = computed(() => [
  {
    label: '模型目录',
    value: modelCount.value,
    hint: modelSyncTime.value ? `最近同步：${modelSyncTime.value}` : '等待首次同步',
    icon: 'runtime',
    tone: 'primary'
  },
  {
    label: '工具目录',
    value: toolCount.value,
    hint: toolSyncTime.value ? `最近同步：${toolSyncTime.value}` : '等待首次同步',
    icon: 'activity',
    tone: 'success'
  },
  {
    label: '目录状态',
    value: error.value ? '需要排查' : '已接通',
    hint: error.value ? '至少有一个目录请求失败' : 'Runtime 基础目录已经纳入新工作台',
    icon: 'shield',
    tone: error.value ? 'warning' : 'danger'
  }
])

const entryCards = computed<RuntimeEntryCard[]>(() => [
  {
    title: '目录入口',
    icon: 'runtime',
    description: '这里负责看清 Runtime 当前暴露了哪些模型和工具，适合做目录核对、联调前检查和人工排障。',
    primaryLabel: '模型目录',
    primaryTo: '/workspace/runtime/models',
    secondaryLabel: '运行策略',
    secondaryTo: '/workspace/runtime/policies'
  },
  {
    title: '治理入口',
    icon: 'shield',
    description: '项目级覆盖、默认模型、工具启停和图策略都应该去治理页做，不该继续在 Runtime 首页堆表格和编辑动作。',
    primaryLabel: '运行策略',
    primaryTo: '/workspace/runtime/policies',
    secondaryLabel: '平台配置',
    secondaryTo: '/workspace/platform-config'
  },
  {
    title: '执行入口',
    icon: 'activity',
    description: '真正的执行、刷新和结果追踪应该回到 Chat、SQL Agent 或 Operations，不要把 Runtime 首页误当成操作台。',
    primaryLabel: '打开 Chat',
    primaryTo: '/workspace/chat',
    secondaryLabel: 'Operations',
    secondaryTo: '/workspace/operations'
  }
])

const recommendedSteps = [
  '先确认当前项目、模型目录和工具目录是否加载正常。',
  '如果要控制项目默认行为，进入运行策略页做项目级覆盖。',
  '如果要验证实际链路，回到 Chat、SQL Agent 或 Operations。'
]

async function loadRuntimeOverview() {
  const projectId = activeProjectId.value
  if (!projectId) {
    modelCount.value = 0
    toolCount.value = 0
    modelSyncTime.value = null
    toolSyncTime.value = null
    error.value = '当前还没有可用项目，Runtime 入口无法加载目录数据。'
    return
  }

  loading.value = true
  error.value = ''

  const results = await Promise.allSettled([
    listRuntimeModels(projectId),
    listRuntimeTools(projectId)
  ])
  const [modelsResult, toolsResult] = results
  const failedSections: string[] = []

  if (modelsResult.status === 'fulfilled') {
    modelCount.value = Array.isArray(modelsResult.value.models) ? modelsResult.value.models.length : 0
    modelSyncTime.value = modelsResult.value.last_synced_at
  } else {
    modelCount.value = 0
    modelSyncTime.value = null
    failedSections.push('模型目录')
  }

  if (toolsResult.status === 'fulfilled') {
    toolCount.value = Array.isArray(toolsResult.value.tools) ? toolsResult.value.tools.length : 0
    toolSyncTime.value = toolsResult.value.last_synced_at
  } else {
    toolCount.value = 0
    toolSyncTime.value = null
    failedSections.push('工具目录')
  }

  if (failedSections.length) {
    error.value = `Runtime 概览加载失败：${failedSections.join('、')}`
  }

  loading.value = false
}

watch(
  () => activeProjectId.value,
  () => {
    void loadRuntimeOverview()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Runtime"
      title="Runtime Hub"
      description="这里是 Runtime 的入口页，只负责目录可见性、治理入口和执行分流，不再和策略页做成一套长得差不多的治理表。"
    >
      <template #actions>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/runtime/models"
        >
          <BaseIcon
            name="runtime"
            size="sm"
          />
          模型目录
        </router-link>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/runtime/policies"
        >
          <BaseIcon
            name="shield"
            size="sm"
          />
          策略覆盖
        </router-link>
        <router-link
          class="pw-btn pw-btn-ghost"
          to="/workspace/operations"
        >
          <BaseIcon
            name="activity"
            size="sm"
          />
          Operations
        </router-link>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="Runtime 概览存在缺口"
      :description="error"
      variant="warning"
    />

    <StateBanner
      v-else
      title="当前页定位"
      description="Runtime 首页负责入口分流和健康概览；项目级策略修改去运行策略页，真实执行链路去 Chat、SQL Agent 或 Operations。"
      variant="info"
    />

    <div class="grid gap-4 xl:grid-cols-3">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
      <div class="grid gap-6 md:grid-cols-3">
        <SurfaceCard
          v-for="item in entryCards"
          :key="item.title"
          class="space-y-4"
        >
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              :name="item.icon"
              size="sm"
              class="text-primary-500"
            />
            {{ item.title }}
          </div>
          <p class="text-sm leading-7 text-gray-500 dark:text-dark-300">
            {{ item.description }}
          </p>
          <div class="flex flex-wrap gap-3">
            <router-link
              class="pw-btn pw-btn-secondary"
              :to="item.primaryTo"
            >
              {{ item.primaryLabel }}
            </router-link>
            <router-link
              class="pw-btn pw-btn-ghost"
              :to="item.secondaryTo"
            >
              {{ item.secondaryLabel }}
            </router-link>
          </div>
        </SurfaceCard>
      </div>

      <SurfaceCard class="space-y-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <BaseIcon
            name="overview"
            size="sm"
            class="text-primary-500"
          />
          推荐使用顺序
        </div>
        <ol class="space-y-3">
          <li
            v-for="(item, index) in recommendedSteps"
            :key="item"
            class="pw-card-glass flex items-start gap-3 p-4"
          >
            <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-50 text-xs font-semibold text-primary-700 dark:bg-primary-950/30 dark:text-primary-100">
              {{ index + 1 }}
            </span>
            <span class="text-sm leading-7 text-gray-600 dark:text-dark-300">
              {{ item }}
            </span>
          </li>
        </ol>
      </SurfaceCard>
    </div>
  </section>
</template>
