<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { changeCurrentPassword } from '@/services/identity/identity.service'
import { setTokenSet } from '@/services/auth/token'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const notice = ref('')

async function submit() {
  if (newPassword.value.length < 8) {
    error.value = '新密码至少 8 位'
    return
  }

  if (newPassword.value !== confirmPassword.value) {
    error.value = '两次输入的新密码不一致'
    return
  }

  if (newPassword.value === oldPassword.value) {
    error.value = '新密码不能和当前密码相同'
    return
  }

  loading.value = true
  error.value = ''
  notice.value = ''

  try {
    const tokens = await changeCurrentPassword({
      oldPassword: oldPassword.value,
      newPassword: newPassword.value
    })
    setTokenSet({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      tokenType: tokens.token_type
    })
    await authStore.fetchCurrentUser()

    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    notice.value = '密码已更新'
  } catch (submitError) {
    error.value = submitError instanceof Error ? submitError.message : '密码更新失败'
  } finally {
    loading.value = false
  }
}

function handleSubmit(event: Event) {
  event.preventDefault()
  void submit()
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Account"
      title="安全设置"
      description="安全页只处理密码修改这种高风险动作。资料编辑和安全动作分开，后面维护起来不容易乱套。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="() => router.push('/workspace/me')"
        >
          <BaseIcon
            name="user"
            size="sm"
          />
          返回资料页
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="密码更新失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作成功"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <SurfaceCard>
        <form
          class="space-y-5"
          @submit="handleSubmit"
        >
          <input
            :value="authStore.user?.username || ''"
            type="text"
            autocomplete="username"
            class="hidden"
            tabindex="-1"
            aria-hidden="true"
            readonly
          >
          <label class="grid gap-2">
            <span class="pw-input-label">当前密码</span>
            <BaseInput
              v-model="oldPassword"
              type="password"
              placeholder="请输入当前密码"
              autocomplete="current-password"
            />
          </label>

          <label class="grid gap-2">
            <span class="pw-input-label">新密码</span>
            <BaseInput
              v-model="newPassword"
              type="password"
              placeholder="请输入新密码"
              autocomplete="new-password"
            />
          </label>

          <label class="grid gap-2">
            <span class="pw-input-label">确认新密码</span>
            <BaseInput
              v-model="confirmPassword"
              type="password"
              placeholder="请再次输入新密码"
              autocomplete="new-password"
            />
          </label>

          <div class="flex flex-wrap gap-3">
            <BaseButton
              type="submit"
              :disabled="loading"
            >
              {{ loading ? '提交中...' : '更新密码' }}
            </BaseButton>
          </div>
        </form>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="pw-page-eyebrow">
          Notes
        </div>
        <div class="space-y-3 text-sm leading-7 text-gray-500 dark:text-dark-300">
          <p>新密码至少 8 位，且不能和当前密码一致。</p>
          <p>如果你在多个终端登录，改密后最好重新登录其他会话，别留一堆过期状态在那恶心人。</p>
        </div>
      </SurfaceCard>
    </div>
  </section>
</template>
