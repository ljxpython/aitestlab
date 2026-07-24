<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { createProject } from '@/services/projects/projects.service'

const router = useRouter()
const { workspaceStore, activeProjects } = useWorkspaceProjectContext()

const name = ref('')
const description = ref('')
const submitting = ref(false)
const error = ref('')
const notice = ref('')

const activeLoading = computed(() => workspaceStore.loading)
const normalizedName = computed(() => name.value.trim())
const requestPreview = computed(() => ({
  name: normalizedName.value,
  description: description.value.trim() || ''
}))
const stats = computed(() => [
  {
    label: '当前项目数',
    value: activeProjects.value.length,
    hint: '创建成功后会自动把新项目写入工作区上下文',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '名称长度',
    value: normalizedName.value.length,
    hint: '后端限制 1-128 个字符',
    icon: 'overview',
    tone: normalizedName.value.length > 0 ? 'success' : 'warning'
  }
])

async function handleSubmit() {
  if (!normalizedName.value) {
    error.value = '项目名称不能为空'
    return
  }

  submitting.value = true
  error.value = ''
  notice.value = ''

  try {
    const created = await createProject({
      name: normalizedName.value,
      description: description.value.trim() || undefined
    })

    await workspaceStore.setProjectId(created.id)
    await workspaceStore.hydrateContext()
    notice.value = `已创建项目：${created.name}`
    void router.replace('/workspace/projects')
  } catch (createError) {
    error.value = createError instanceof Error ? createError.message : '项目创建失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Projects"
      title="新建项目"
      description="创建一个新的项目工作区，并在创建成功后自动切换当前项目。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/projects')"
        >
          返回列表
        </BaseButton>
      </template>
    </PageHeader>

    <EmptyState
      v-if="!activeProjects.length && !activeLoading"
      icon="folder"
      title="当前还没有任何项目"
      description="可以直接在这里创建第一个项目。创建成功后会自动把你设为该项目的管理员成员。"
    />

    <StateBanner
      v-if="error"
      title="项目创建失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作已完成"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-4 xl:grid-cols-2">
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

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
      <SurfaceCard class="space-y-5">
        <div>
          <div class="text-lg font-semibold text-gray-900 dark:text-white">
            创建表单
          </div>
          <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
            项目创建链路已纳入正式工作区，可直接在这里完成创建并切换当前项目。
          </div>
        </div>

        <label class="block">
          <span class="pw-input-label">项目名称</span>
          <input
            v-model="name"
            class="pw-input"
            placeholder="请输入项目名称"
            :disabled="submitting"
            maxlength="128"
          >
        </label>

        <label class="block">
          <span class="pw-input-label">描述（可选）</span>
          <textarea
            v-model="description"
            rows="6"
            class="pw-input min-h-[160px] resize-y"
            placeholder="请输入项目描述"
            :disabled="submitting"
          />
        </label>

        <div class="flex justify-end">
          <BaseButton
            :disabled="submitting"
            @click="handleSubmit"
          >
            <BaseIcon
              name="folder"
              size="sm"
            />
            {{ submitting ? '创建中...' : '创建项目' }}
          </BaseButton>
        </div>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="text-lg font-semibold text-gray-900 dark:text-white">
          请求预览
        </div>
        <pre class="overflow-auto whitespace-pre-wrap break-words rounded-[24px] bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ JSON.stringify(requestPreview, null, 2) }}</pre>

        <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-4 text-sm leading-7 text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-200">
          创建成功后会自动：
          1. 落库项目
          2. 当前用户成为该项目管理员
          3. 切换工作区到新项目
          4. 返回项目列表页
        </div>
      </SurfaceCard>
    </div>
  </section>
</template>
