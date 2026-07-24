import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { createUserMock } = vi.hoisted(() => ({
  createUserMock: vi.fn()
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() })
}))

vi.mock('@/composables/useAuthorization', () => ({
  useAuthorization: () => ({ can: () => true })
}))

vi.mock('@/services/users/users.service', () => ({
  createUser: createUserMock
}))

import UserCreatePage from './UserCreatePage.vue'

describe('UserCreatePage', () => {
  beforeEach(() => {
    createUserMock.mockReset()
  })

  it('rejects passwords shorter than the API minimum before submitting', async () => {
    const wrapper = mount(UserCreatePage, {
      global: {
        stubs: {
          BaseButton: {
            props: ['disabled'],
            template: '<button :disabled="disabled"><slot /></button>'
          },
          BaseIcon: true,
          BaseSelect: true,
          MetricCard: true,
          PageHeader: { template: '<header><slot name="actions" /></header>' },
          StateBanner: {
            props: ['title', 'description'],
            template: '<div>{{ title }}：{{ description }}</div>'
          },
          SurfaceCard: { template: '<section><slot /></section>' }
        }
      }
    })

    await wrapper.get('input[placeholder="请输入用户名"]').setValue('test1')
    const passwordInput = wrapper.get('input[type="password"]')
    await passwordInput.setValue('test')
    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(passwordInput.attributes('minlength')).toBe('8')
    expect(wrapper.text()).toContain('密码至少需要 8 个字符')
    expect(createUserMock).not.toHaveBeenCalled()
  })
})
