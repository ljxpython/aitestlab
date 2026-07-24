<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { formatPlatformRoleLabel } from '@/services/auth/permissions'
import { createUser } from '@/services/users/users.service'
import type { PlatformRole } from '@/types/management'

const router = useRouter()
const authorization = useAuthorization()

const username = ref('')
const password = ref('')
const platformRole = ref<PlatformRole | ''>('')
const submitting = ref(false)
const error = ref('')
const notice = ref('')

const platformRoleOptions: Array<{ value: PlatformRole | ''; label: string }> = [
  { value: '', label: '无平台角色' },
  { value: 'platform_viewer', label: formatPlatformRoleLabel('platform_viewer') },
  { value: 'platform_operator', label: formatPlatformRoleLabel('platform_operator') },
  { value: 'platform_super_admin', label: formatPlatformRoleLabel('platform_super_admin') }
]

const normalizedUsername = computed(() => username.value.trim())
const requestPreview = computed(() => ({
  username: normalizedUsername.value,
  password: password.value ? '********' : '',
  platform_roles: platformRole.value ? [platformRole.value] : [],
  is_super_admin: platformRole.value === 'platform_super_admin'
}))
const stats = computed(() => [
  {
    label: '用户名长度',
    value: normalizedUsername.value.length,
    hint: '后端限制 1-64 个字符',
    icon: 'user',
    tone: normalizedUsername.value.length > 0 ? 'success' : 'warning'
  },
  {
    label: '密码长度',
    value: password.value.length,
    hint: '必须至少 8 位',
    icon: 'lock',
    tone: password.value.length >= 8 ? 'success' : 'danger'
  },
  {
    label: '平台角色',
    value: platformRole.value ? formatPlatformRoleLabel(platformRole.value) : '无平台角色',
    hint: '项目级权限仍需在项目成员页单独分配',
    icon: 'shield',
    tone: platformRole.value ? 'primary' : 'warning'
  }
])

async function handleSubmit() {
  if (!authorization.can('platform.user.create')) {
    error.value = '当前账号没有创建用户的权限'
    return
  }

  if (!normalizedUsername.value) {
    error.value = '用户名不能为空'
    return
  }

  if (password.value.length < 8) {
    error.value = '密码至少需要 8 个字符'
    return
  }

  submitting.value = true
  error.value = ''
  notice.value = ''

  try {
    const created = await createUser({
      username: normalizedUsername.value,
      password: password.value,
      platform_roles: platformRole.value ? [platformRole.value] : [],
      is_super_admin: platformRole.value === 'platform_super_admin'
    })

    notice.value = `已创建用户：${created.username}`
    void router.replace('/workspace/users')
  } catch (createError) {
    error.value = createError instanceof Error ? createError.message : '用户创建失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Users"
      title="新建用户"
      description="创建新的系统用户。提交后会返回用户列表，并保持统一的平台管理链路。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/users')"
        >
          返回列表
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="用户创建失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作已完成"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-4 xl:grid-cols-3">
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

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]">
      <SurfaceCard class="space-y-5">
        <div>
          <div class="text-lg font-semibold text-gray-900 dark:text-white">
            创建表单
          </div>
          <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
            当前页负责最小可用创建链路：用户名、密码、平台角色。
          </div>
        </div>

        <label class="block">
          <span class="pw-input-label">用户名</span>
          <input
            v-model="username"
            class="pw-input"
            placeholder="请输入用户名"
            :disabled="submitting || !authorization.can('platform.user.create')"
            maxlength="64"
          >
        </label>

        <label class="block">
          <span class="pw-input-label">密码</span>
          <input
            v-model="password"
            type="password"
            class="pw-input"
            placeholder="请输入至少 8 位密码"
            minlength="8"
            :disabled="submitting || !authorization.can('platform.user.create')"
          >
        </label>

        <label class="block">
          <span class="pw-input-label">平台角色</span>
          <BaseSelect
            v-model="platformRole"
            :disabled="submitting || !authorization.can('platform.user.role.write')"
            :options="platformRoleOptions"
          />
        </label>

        <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-4 text-sm leading-7 text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-200">
          用户是否能管理具体项目，不在这里定。项目访问和项目内写权限，统一去项目成员页分配。
        </div>

        <div class="flex justify-end">
          <BaseButton
            :disabled="submitting || !authorization.can('platform.user.create')"
            @click="handleSubmit"
          >
            <BaseIcon
              name="users"
              size="sm"
            />
            {{ authorization.can('platform.user.create') ? (submitting ? '创建中...' : '创建用户') : '当前账号只读' }}
          </BaseButton>
        </div>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="text-lg font-semibold text-gray-900 dark:text-white">
          请求预览
        </div>
        <pre class="overflow-auto whitespace-pre-wrap break-words rounded-[24px] bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ JSON.stringify(requestPreview, null, 2) }}</pre>

        <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-4 text-sm leading-7 text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-200">
          创建成功后会直接返回用户列表页。更复杂的邀请式流程暂不在当前页面支持范围内。
        </div>
      </SurfaceCard>
    </div>
  </section>
</template>
